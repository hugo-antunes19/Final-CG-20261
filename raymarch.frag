// ===========================================================================
//  FRAGMENT SHADER  -  Raymarching 3D de SDFs + Fundo Galático Realista
//
//  Fundo:
//   - Via Láctea: banda gaussiana com estrutura FBM interna
//   - Nebulosas: emissão Hα (vermelho), OIII (ciano), reflexão (azul-púrpura)
//   - Campo estelar multicamada com cores por temperatura (O→M) e glow
//   - Streaks de warp alongados radialmente para sensação de velocidade
//
//  Os obstáculos chegam do Python por uniforms — código de gameplay inalterado.
// ===========================================================================
precision highp float;
#define MAX_OBS 8

uniform vec2  uResolution;
uniform float uTime;
uniform float uWarp;
uniform vec3  uObRel[MAX_OBS];
uniform float uObRad[MAX_OBS];
uniform float uObType[MAX_OBS];
uniform float uHit;

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

// Obstáculo que muda de forma: mistura esfera <-> cubo <-> toro no tempo
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

// Loop desenrolado com índices constantes (GLSL ES 1.00)
#define OBS(i) ob = min(ob, obstacleSDF(p, uObRel[i], uObRad[i], uObType[i]))
float mapScene(vec3 p, out float mat){
  mat = 1.0;
  float ob = obstacleSDF(p, uObRel[0], uObRad[0], uObType[0]);
  OBS(1); OBS(2); OBS(3); OBS(4); OBS(5); OBS(6); OBS(7);
  return ob;
}
float mapDist(vec3 p){ float m; return mapScene(p, m); }

// Normal por diferenças finitas
vec3 calcNormal(vec3 p){
  vec2 e = vec2(0.0025, 0.0);
  return normalize(vec3(
    mapDist(p + e.xyy) - mapDist(p - e.xyy),
    mapDist(p + e.yxy) - mapDist(p - e.yxy),
    mapDist(p + e.yyx) - mapDist(p - e.yyx)));
}

// ===========================================================================
//  FUNDO GALÁTICO — helpers
// ===========================================================================

float hash11(float n){
    return fract(sin(n * 127.1) * 43758.5453);
}
float hash21(vec2 p){
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}
vec2 hash22(vec2 p){
    vec2 q = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(q) * 43758.5453);
}

// Ruído suavizado (bilinear sobre grade hash)
float smoothNoise(vec2 p){
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);                // curva suave
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// FBM (Fractional Brownian Motion) — 5 oitavas para nuvens de gás
float fbm(vec2 p){
    float v = 0.0, a = 0.5;
    for(int i = 0; i < 5; i++){
        v += a * smoothNoise(p);
        p  = p * 2.13 + vec2(31.41, 27.18);
        a *= 0.5;
    }
    return v;
}

// Cor estelar pelo tipo espectral (t=0 → azul-quente O/B, t=1 → vermelho-frio M)
vec3 starColor(float t){
    vec3 ob = vec3(0.55, 0.68, 1.00);   // O/B : azul-branca
    vec3 af = vec3(1.00, 1.00, 0.96);   // A/F : branca
    vec3 g  = vec3(1.00, 0.88, 0.50);   // G   : amarela (tipo Sol)
    vec3 km = vec3(1.00, 0.42, 0.12);   // K/M : laranja-vermelha
    vec3 c  = mix(ob, af, smoothstep(0.0,  0.30, t));
         c  = mix(c,  g,  smoothstep(0.30, 0.60, t));
         c  = mix(c,  km, smoothstep(0.60, 1.00, t));
    return c;
}

// Camada de estrelas: posição sub-célula com glow gaussiano + cintilação
vec3 starLayer(vec2 dir, float scale, float thresh){
    vec2 g = floor(dir * scale);
    vec2 f = fract(dir * scale);

    float h    = hash21(g);
    float brt  = max(0.0, (h - thresh) / (1.0 - thresh));
    brt        = brt * brt;                                  // contraste

    // Posição aleatória da estrela dentro da célula
    vec2 pos   = hash22(g + 0.5);
    float d    = length(f - pos) * scale;

    // Cintilação temporal suave
    float twinkle = 1.0 + 0.07 * sin(uTime * 2.5 + hash21(g) * 47.3);

    float core = exp(-d * d * 1400.0);
    float glow = exp(-d * d *   55.0) * 0.13;

    float temp = hash21(g + vec2(37.1, 91.3));
    return (core + glow) * brt * twinkle * starColor(temp);
}

// ===========================================================================
//  background() — monta a cena galáctica pixel a pixel
// ===========================================================================
vec3 background(vec3 rd, vec2 uv){

    // 1. Espaço profundo
    vec3 col = vec3(0.005, 0.003, 0.014);

    // 2. Faixa da Via Láctea (plano galáctico ligeiramente inclinado)
    float gp      = rd.y * 0.82 - rd.x * 0.22;
    float mwBand  = exp(-gp * gp * 5.5);
    float mwFbm   = fbm(rd.xz * 1.7 + vec2(uTime * 0.003, 0.0));
    float mw      = mwBand * (0.30 + 0.70 * mwFbm);

    // Cor da faixa: azul-pérola difuso + leve amarelado no núcleo
    col += mw * vec3(0.09, 0.07, 0.17);
    col += mw * mwBand * vec3(0.06, 0.04, 0.02);   // núcleo mais quente

    // 3. Nebulosas de gás
    vec2 nb = rd.xy * 2.0 + rd.z * 0.30;

    // Emissão Hα — hidrogênio ionizado (vermelho/magenta)
    float em  = pow(max(0.0, fbm(nb * 1.1 + vec2(uTime * 0.004, 1.7))), 2.2);
    col += em  * vec3(0.30, 0.03, 0.10);

    // OIII — oxigênio ionizado, gás mais quente (ciano/teal)
    float oiii = pow(max(0.0, fbm(nb * 0.80 + vec2(3.4, uTime * 0.003))), 2.8);
    col += oiii * vec3(0.02, 0.16, 0.24);

    // Reflexão — poeira espalhando luz estelar (azul-púrpura frio)
    float ref  = pow(max(0.0, fbm(nb * 1.45 + vec2(-1.9, 0.8))), 3.0);
    col += ref  * vec3(0.04, 0.05, 0.22) * 0.65;

    // 4. Campo estelar — quatro camadas (densidade × brilho crescentes)
    vec2 sd = rd.xy + rd.z * 0.10;
    float mwBoost = 1.0 + mwBand * 1.8;  // mais estrelas na Via Láctea

    col += starLayer(sd, 145.0, 0.922) * 0.28 * mwBoost;   // fundo: denso, fraco
    col += starLayer(sd,  88.0, 0.942) * 0.58 * mwBoost;   // médias
    col += starLayer(sd,  42.0, 0.960) * 1.00;              // brilhantes
    col += starLayer(sd,  19.0, 0.974) * 1.70;              // muito brilhantes (raras)

    // 5. Streaks de warp — alongados radialmente, sensação de velocidade
    float br = 0.0;
    for(int i = 0; i < 60; i++){
        float fi   = float(i);
        float seed = hash11(fi * 0.3183);
        float ang  = seed * 6.28318;
        float spd  = 0.7 + hash11(fi * 0.3183 + 100.0) * 0.6;
        float t    = fract(uWarp * spd + seed);

        vec2 sdir  = vec2(cos(ang), sin(ang));
        vec2 spos  = sdir * t * 1.8;
        vec2 dv    = uv - spos;

        // Distância perpendicular (largura) e paralela (comprimento) ao streak
        float dPerp = abs(dot(dv, vec2(-sdir.y, sdir.x)));
        float dPara = dot(dv, sdir);
        float slen  = 0.025 + hash11(fi * 0.3183 + 200.0) * 0.055;

        float s = smoothstep(0.0040, 0.0, dPerp) *
                  smoothstep(slen,   0.0, abs(dPara));
        br += s * t * t;
    }
    col += br * vec3(0.50, 0.72, 1.00);

    return col;
}

// ===========================================================================
//  main
// ===========================================================================
void main(){
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;

  vec3 ro = vec3(0.0);
  vec3 rd = normalize(vec3(uv, 1.45));

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
    float fog = 1.0 - exp(-t * 0.02);
    col = mix(col, bg, fog);
  } else {
    col = bg;
  }

  col = mix(col, vec3(0.9, 0.05, 0.05), uHit * 0.6);
  col = pow(col, vec3(0.4545));
  gl_FragColor = vec4(col, 1.0);
}
