# ===========================================================================
#  TRENCH RUN INFINITO  -  Computacao Grafica
#  py5 / Py5Script (PyScript + p5.js)  -  WEBGL + Shader GLSL (Raymarching SDF)
# ---------------------------------------------------------------------------
#  - Toda a cena 3D (tunel + obstaculos) e gerada por MATEMATICA dentro do
#    fragment shader, via Raymarching de SDFs (caixa do tunel, esferas, cubos
#    e toros que se transformam continuamente).
#  - O Python so cuida da LOGICA do jogo: movimento da nave, geracao
#    procedural dos obstaculos, deteccao de colisao e HUD. Os dados sao
#    enviados ao shader por uniforms, entao o que voce ve e exatamente o
#    que colide.
#
#  Controles:  SETAS ou WASD = mover a nave   |   ESPACO = comecar / reiniciar
# ===========================================================================

import math
import random

# --- ponte com JavaScript para enviar arrays a setUniform -------------------
try:
    _to_js = js_array            # helper fornecido pelo Py5Script
except NameError:
    from pyodide.ffi import to_js as _pyto_js
    def _to_js(x):
        return _pyto_js(x)

# ---------------------------------------------------------------------------
#  Constantes (devem casar com as do shader)
# ---------------------------------------------------------------------------
MAX_OBS      = 8        # tambem definido como #define no shader
TUNNEL_HALF  = 6.0      # meia-largura do tunel quadrado
SHIP_RADIUS  = 0.55     # "raio" de colisao da nave
SPACING      = 16.0     # distancia entre obstaculos ao longo de Z
OB_START     = 28.0     # Z do primeiro obstaculo (nunca em cima da camera)
RIDGE_MOD    = 64.0     # para manter camZ pequeno preservando a fase visual

# ---------------------------------------------------------------------------
#  VERTEX SHADER  -  quad de tela cheia
#  (truque classico p5.js: aPosition chega normalizado 0..1, mapeamos p/ clip)
# ---------------------------------------------------------------------------
VERT = """
precision highp float;
attribute vec3 aPosition;
void main() {
  vec4 p = vec4(aPosition, 1.0);
  p.xy = p.xy * 2.0 - 1.0;
  gl_Position = p;
}
"""

# ---------------------------------------------------------------------------
#  FRAGMENT SHADER  -  Raymarching da cena inteira
# ---------------------------------------------------------------------------
FRAG = """
precision highp float;
#define MAX_OBS 8

uniform vec2  uResolution;
uniform float uTime;
uniform float uCamZ;          // avanco da camera (mod RIDGE_MOD)
uniform vec2  uPlayer;        // deslocamento lateral da nave (x,y)
uniform int   uObCount;
uniform vec3  uObRel[MAX_OBS];// posicao do obstaculo relativa a camera
uniform float uObRad[MAX_OBS];
uniform float uObType[MAX_OBS];
uniform float uHit;           // 1.0 quando bateu

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
  float ph = typ + uTime * 0.6;             // fase de animacao por obstaculo
  rp.xy = rot(ph * 0.7) * rp.xy;            // rotaciona p/ dar vida
  rp.xz = rot(ph * 0.5) * rp.xz;

  float es = sdSphere(rp, r);
  float cu = sdBox(rp, vec3(r * 0.78));
  float to = sdTorus(rp, vec2(r * 0.70, r * 0.32));

  float a = 0.5 + 0.5 * sin(ph);            // peso esfera/cubo
  float b = 0.5 + 0.5 * sin(ph * 0.73 + 2.1); // peso (mix) / toro
  float m = mix(es, cu, a);
  return mix(m, to, b);
}

// Tunel quadrado infinito (distancia interna ate as paredes)
float tunnelSDF(vec3 p){
  float wx = p.x + uPlayer.x;
  float wy = p.y + uPlayer.y;
  return TUNNEL_HALF - max(abs(wx), abs(wy));
}

// material: 0 = tunel, 1 = obstaculo
float mapScene(vec3 p, out float mat){
  float d = tunnelSDF(p);
  mat = 0.0;
  for(int i = 0; i < MAX_OBS; i++){
    if(i >= uObCount) break;
    float od = obstacleSDF(p, uObRel[i], uObRad[i], uObType[i]);
    if(od < d){ d = od; mat = 1.0; }
  }
  return d;
}

float mapDist(vec3 p){
  float m;
  return mapScene(p, m);
}

vec3 calcNormal(vec3 p){
  vec2 e = vec2(0.0025, 0.0);
  return normalize(vec3(
    mapDist(p + e.xyy) - mapDist(p - e.xyy),
    mapDist(p + e.yxy) - mapDist(p - e.yxy),
    mapDist(p + e.yyx) - mapDist(p - e.yyx)));
}

// cor do tunel: grade luminosa + linhas de velocidade ao longo de Z
vec3 tunnelColor(vec3 p){
  float wx = p.x + uPlayer.x;
  float wy = p.y + uPlayer.y;
  float wz = p.z + uCamZ;
  float gx = smoothstep(0.06, 0.0, abs(fract(wz * 0.25) - 0.5) - 0.46);
  float gy = smoothstep(0.06, 0.0, abs(fract((wx + wy) * 0.5) - 0.5) - 0.46);
  vec3 base = vec3(0.02, 0.05, 0.10);
  vec3 glow = vec3(0.1, 0.8, 1.0) * (gx + gy);
  // pulso suave correndo pelo tunel (usa p.z local p/ evitar salto no wrap)
  glow += vec3(0.6, 0.2, 0.9) * smoothstep(0.9, 1.0, sin(p.z * 0.15 - uTime * 3.0) * 0.5 + 0.5) * 0.5;
  return base + glow;
}

void main(){
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;

  vec3 ro = vec3(0.0);                          // camera na origem (espaco local)
  vec3 rd = normalize(vec3(uv, 1.45));          // olhando para +Z

  float t = 0.0;
  float mat = 0.0;
  bool hit = false;
  for(int i = 0; i < 90; i++){
    vec3 p = ro + rd * t;
    float d = mapScene(p, mat);
    if(d < 0.002){ hit = true; break; }
    t += d;
    if(t > 170.0) break;
  }

  vec3 col;
  if(hit){
    vec3 p = ro + rd * t;
    vec3 n = calcNormal(p);
    vec3 lig = normalize(vec3(0.4, 0.7, -0.5));
    float dif = clamp(dot(n, lig), 0.0, 1.0);
    float amb = 0.25 + 0.25 * n.y;
    float fre = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 3.0);

    if(mat < 0.5){
      col = tunnelColor(p) * (amb + dif * 0.5);
    } else {
      // obstaculo: cor abstrata pulsante por posicao + fresnel quente
      vec3 oc = 0.5 + 0.5 * cos(vec3(0.0, 2.1, 4.2) + p.z * 0.15 + uTime);
      col = oc * (amb + dif * 0.9) + fre * vec3(1.0, 0.5, 0.2);
    }
    // nevoa por distancia (sensacao de profundidade/velocidade)
    float fog = 1.0 - exp(-t * 0.018);
    col = mix(col, vec3(0.01, 0.02, 0.05), fog);
  } else {
    // espaco profundo + estrelas
    col = vec3(0.01, 0.02, 0.05);
    vec2 sc = floor(rd.xy * 90.0);
    float h = fract(sin(dot(sc, vec2(12.9898, 78.233))) * 43758.5453);
    col += smoothstep(0.995, 1.0, h) * vec3(0.9);
  }

  // flash vermelho ao colidir
  col = mix(col, vec3(0.9, 0.05, 0.05), uHit * 0.6);

  col = pow(col, vec3(0.4545));   // gamma
  gl_FragColor = vec4(col, 1.0);
}
"""

# o shader usa TUNNEL_HALF e RIDGE_MOD como literais; injetamos os valores
FRAG = FRAG.replace("TUNNEL_HALF", "%.1f" % TUNNEL_HALF)

# ---------------------------------------------------------------------------
#  Estado do jogo
# ---------------------------------------------------------------------------
prog = None
hud = None
W = 0
H = 0

state = "start"          # "start" | "play" | "over"
cam_z = 0.0              # distancia percorrida
px = 0.0                 # posicao lateral da nave
py = 0.0
speed = 18.0
score = 0.0
best = 0.0
hit_flash = 0.0
prev_space = False


def make_obstacle(n):
    """Obstaculo deterministico para o indice n (mesmo resultado sempre)."""
    rng = random.Random((n * 2654435761) & 0xFFFFFFFF)
    rad = rng.uniform(1.9, 3.1)
    lim = TUNNEL_HALF - rad - 0.4
    cx = rng.uniform(-lim, lim)
    cy = rng.uniform(-lim, lim)
    typ = rng.uniform(0.0, 6.28)
    return OB_START + n * SPACING, cx, cy, rad, typ   # z, cx, cy, rad, typ


def reset_game():
    global cam_z, px, py, speed, score, hit_flash, state
    cam_z = 0.0
    px = 0.0
    py = 0.0
    speed = 18.0
    score = 0.0
    hit_flash = 0.0
    state = "play"


def setup():
    global prog, hud, W, H
    P5.createCanvas(900, 600, P5.WEBGL)
    P5.pixelDensity(1)
    P5.noStroke()
    W = P5.width
    H = P5.height
    prog = P5.createShader(VERT, FRAG)
    hud = P5.createGraphics(W, H)     # buffer 2D para texto/HUD


def update(dt):
    global cam_z, px, py, speed, score, state, hit_flash

    # input lateral
    mv = 14.0 * dt
    if P5.keyIsDown(P5.LEFT_ARROW) or P5.keyIsDown(65):   px -= mv   # A
    if P5.keyIsDown(P5.RIGHT_ARROW) or P5.keyIsDown(68):  px += mv   # D
    if P5.keyIsDown(P5.UP_ARROW) or P5.keyIsDown(87):     py += mv   # W
    if P5.keyIsDown(P5.DOWN_ARROW) or P5.keyIsDown(83):   py -= mv   # S

    lim = TUNNEL_HALF - SHIP_RADIUS
    px_c = max(-lim, min(lim, px))
    py_c = max(-lim, min(lim, py))
    _set_player(px_c, py_c)

    # avanco + dificuldade crescente
    speed = min(60.0, 18.0 + cam_z * 0.02)
    cam_z += speed * dt
    score = cam_z

    # colisao com obstaculos proximos
    base = int((cam_z - OB_START) // SPACING)
    for n in range(base - 1, base + MAX_OBS + 1):
        if n < 0:
            continue
        z, cx, cy, rad, _ = make_obstacle(n)
        relz = z - cam_z
        if -rad < relz < rad:
            dx = cx - px_c
            dy = cy - py_c
            if math.hypot(dx, dy) < rad * 0.85 + SHIP_RADIUS:
                state = "over"
                hit_flash = 1.0
                break

    if hit_flash > 0.0:
        hit_flash = max(0.0, hit_flash - dt * 1.5)


def _set_player(x, y):
    """Guarda a posicao clampeada para uso no shader e no HUD."""
    global px, py
    px, py = x, y


def collect_obstacles():
    """Monta os arrays de uniforms (relativos a camera, padded ate MAX_OBS)."""
    base = int((cam_z - OB_START) // SPACING)
    rel = []
    rads = []
    types = []
    count = 0
    n = max(0, base - 1)
    while count < MAX_OBS and n < base + MAX_OBS + 2:
        z, cx, cy, rad, typ = make_obstacle(n)
        relz = z - cam_z
        n += 1
        if relz < -1.0 or relz > 150.0:
            continue
        rel.extend([cx - px, cy - py, relz])
        rads.append(rad)
        types.append(typ)
        count += 1
    # padding
    while len(rads) < MAX_OBS:
        rel.extend([0.0, 0.0, 9999.0])
        rads.append(0.0)
        types.append(0.0)
    return rel, rads, types, count


def draw():
    global best
    dt = min(0.05, P5.deltaTime / 1000.0)

    if state == "play":
        update(dt)
        if score > best:
            best = score

    # --- renderiza a cena via shader (raymarching) ---
    rel, rads, types, count = collect_obstacles()
    P5.shader(prog)
    prog.setUniform("uResolution", _to_js([float(W), float(H)]))
    prog.setUniform("uTime", float(P5.millis()) / 1000.0)
    prog.setUniform("uCamZ", float(cam_z % RIDGE_MOD))
    prog.setUniform("uPlayer", _to_js([float(px), float(py)]))
    prog.setUniform("uObCount", int(count))
    prog.setUniform("uObRel", _to_js([float(v) for v in rel]))
    prog.setUniform("uObRad", _to_js([float(v) for v in rads]))
    prog.setUniform("uObType", _to_js([float(v) for v in types]))
    prog.setUniform("uHit", float(hit_flash))
    P5.rect(0, 0, W, H)        # quad de tela cheia

    # --- HUD por cima (buffer 2D texturizado) ---
    draw_hud()
    P5.resetShader()
    P5.image(hud, -W / 2, -H / 2, W, H)

    handle_space()


def draw_hud():
    hud.clear()
    hud.textFont("monospace")
    hud.fill(120, 240, 255)
    hud.textSize(18)
    hud.text("DISTANCIA: %d m" % int(score), 16, 28)
    hud.text("RECORDE:   %d m" % int(best), 16, 50)
    hud.text("VEL: %d" % int(speed), W - 110, 28)

    if state == "start":
        _center_msg("TRENCH RUN INFINITO",
                    "Desvie das formas que mudam",
                    "ESPACO para comecar  -  SETAS/WASD para mover")
    elif state == "over":
        _center_msg("VOCE COLIDIU",
                    "Distancia: %d m" % int(score),
                    "ESPACO para reiniciar")


def _center_msg(title, line2, line3):
    hud.fill(0, 0, 0, 150)
    hud.rect(0, H / 2 - 70, W, 140)
    hud.textAlign(P5.CENTER, P5.CENTER)
    hud.fill(255, 230, 120)
    hud.textSize(34)
    hud.text(title, W / 2, H / 2 - 28)
    hud.fill(220)
    hud.textSize(18)
    hud.text(line2, W / 2, H / 2 + 4)
    hud.fill(150, 230, 255)
    hud.text(line3, W / 2, H / 2 + 34)
    hud.textAlign(P5.LEFT, P5.BASELINE)


def handle_space():
    global prev_space
    down = P5.keyIsDown(32)
    if down and not prev_space:
        if state in ("start", "over"):
            reset_game()
    prev_space = down
