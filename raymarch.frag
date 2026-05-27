// ===========================================================================
//  FRAGMENT SHADER  -  Raymarching 3D de SDFs + fundo espacial em "warp"
//
//  Toda a cena 3D e gerada por matematica aqui dentro:
//   - obstaculos = SDFs (esfera / cubo / toro) que se transformam no tempo;
//   - fundo = nebulosa + estrelas + streaks radiais (sensacao de velocidade).
//
//  Os obstaculos chegam do Python por uniforms (posicao relativa a camera,
//  raio e "tipo"), entao o que aparece na tela e exatamente o que colide.
// ===========================================================================
precision highp float;
#define MAX_OBS 8

uniform vec2  uResolution;
uniform float uTime;
uniform float uWarp;           // fase continua [0,1) do campo de estrelas
uniform vec3  uObRel[MAX_OBS]; // posicao do obstaculo relativa a camera
uniform float uObRad[MAX_OBS];
uniform float uObType[MAX_OBS];
uniform float uHit;            // 1.0 quando bateu

// ---------- SDFs primitivas ----------
float sdSphere(vec3 p, float r){ return length(p) - r; }

float sdBox(vec3 p, vec3 b){
  vec3 q = abs(p) - b;
  return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float sdTorus(vec3 p, vec2 t){
  vec2 q = vec2(length(p.xz) - t.x, p.y);
  return length(q) - t.y;
}

mat2 rot(float a){ float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

// Obstaculo que muda de forma: mistura esfera <-> cubo <-> toro no tempo
float obstacleSDF(vec3 p, vec3 center, float r, float typ){
  vec3 rp = p - center;
  float ph = typ + uTime * 0.6;
  rp.xy = rot(ph * 0.7) * rp.xy;
  rp.xz = rot(ph * 0.5) * rp.xz;
  float es = sdSphere(rp, r);
  float cu = sdBox(rp, vec3(r * 0.78));
  float to = sdTorus(rp, vec2(r * 0.70, r * 0.32));
  float a = 0.5 + 0.5 * sin(ph);
  float b = 0.5 + 0.5 * sin(ph * 0.73 + 2.1);
  float m = mix(es, cu, a);
  return mix(m, to, b);
}

// SDF da cena: o obstaculo mais proximo. O loop e desenrolado com indices
// CONSTANTES porque indexar array de uniform com indice dinamico nao e
// suportado de forma confiavel em GLSL ES 1.00 (quebra em varios drivers).
// Obstaculos nao usados vem com raio 0 e z=9999, logo nunca entram na cena.
// A cena so tem obstaculos, entao mat=1 (so lido quando ha colisao do raio).
#define OBS(i) ob = min(ob, obstacleSDF(p, uObRel[i], uObRad[i], uObType[i]))
float mapScene(vec3 p, out float mat){
  mat = 1.0;
  float ob = obstacleSDF(p, uObRel[0], uObRad[0], uObType[0]);
  OBS(1); OBS(2); OBS(3); OBS(4); OBS(5); OBS(6); OBS(7);
  return ob;
}
float mapDist(vec3 p){ float m; return mapScene(p, m); }

// Normal por diferencas finitas do campo de distancia
vec3 calcNormal(vec3 p){
  vec2 e = vec2(0.0025, 0.0);
  return normalize(vec3(
    mapDist(p + e.xyy) - mapDist(p - e.xyy),
    mapDist(p + e.yxy) - mapDist(p - e.yxy),
    mapDist(p + e.yyx) - mapDist(p - e.yyx)));
}

// Fundo: nebulosa + estrelas distantes + streaks radiais de "warp"
vec3 background(vec3 rd, vec2 uv){
  float v = clamp(uv.y * 0.5 + 0.5, 0.0, 1.0);
  vec3 col = mix(vec3(0.03, 0.02, 0.07), vec3(0.02, 0.05, 0.12), v);
  float neb = sin(rd.x * 2.5 + uTime * 0.05) * sin(rd.y * 2.5 - uTime * 0.03);
  col += vec3(0.06, 0.03, 0.11) * (0.5 + 0.5 * neb) * 0.5;

  // estrelas distantes fixas
  vec2 g = floor(rd.xy * 130.0);
  float h = fract(sin(dot(g, vec2(12.9898, 78.233))) * 43758.5453);
  col += smoothstep(0.987, 1.0, h) * vec3(0.9, 0.95, 1.0);

  // streaks radiais que jorram do centro -> sensacao de velocidade
  float br = 0.0;
  for(int i = 0; i < 40; i++){
    float fi = float(i);
    float seed = fract(sin(fi * 127.1) * 43758.5453);
    float ang = seed * 6.28318;
    float t = fract(uWarp + seed);
    vec2 sp = vec2(cos(ang), sin(ang)) * t * 1.5;
    float d = length(uv - sp);
    br += smoothstep(0.012, 0.0, d) * t * t;
  }
  col += br * vec3(0.6, 0.8, 1.0);
  return col;
}

void main(){
  // coordenada de tela normalizada (centro = 0), independente do quad
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;

  vec3 ro = vec3(0.0);                  // camera na origem
  vec3 rd = normalize(vec3(uv, 1.45));  // raio olhando para +Z

  vec3 bg = background(rd, uv);

  // ---- Raymarching ----
  float t = 0.0;
  float mat = 0.0;
  bool hit = false;
  for(int i = 0; i < 80; i++){
    vec3 p = ro + rd * t;
    float d = mapScene(p, mat);
    if(d < 0.002){ hit = true; break; }
    t += d;
    if(t > 160.0) break;
  }

  vec3 col;
  if(hit){
    vec3 p = ro + rd * t;
    vec3 n = calcNormal(p);
    vec3 lig = normalize(vec3(0.4, 0.7, -0.5));
    float dif = clamp(dot(n, lig), 0.0, 1.0);
    float amb = 0.3 + 0.2 * n.y;
    float fre = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 3.0);
    vec3 oc = 0.5 + 0.5 * cos(vec3(0.0, 2.1, 4.2) + p.z * 0.15 + uTime);
    col = oc * (amb + dif * 0.9) + fre * vec3(1.0, 0.5, 0.2);
    float fog = 1.0 - exp(-t * 0.02);     // funde no espaco com a distancia
    col = mix(col, bg, fog);
  } else {
    col = bg;
  }

  col = mix(col, vec3(0.9, 0.05, 0.05), uHit * 0.6);  // flash ao colidir
  col = pow(col, vec3(0.4545));                       // gamma
  gl_FragColor = vec4(col, 1.0);
}
