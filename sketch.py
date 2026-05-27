# ===========================================================================
#  TUNEL ESPACIAL INFINITO  -  Computacao Grafica
#  py5 / Py5Script (PyScript + p5.js)  -  WEBGL + Shader GLSL (Raymarching SDF)
# ---------------------------------------------------------------------------
#  - Toda a cena 3D (obstaculos + fundo/estrelas) e gerada por MATEMATICA
#    dentro do fragment shader: raymarching de SDFs (esferas, cubos e toros
#    que se transformam continuamente) sobre um campo de estrelas em "warp".
#  - O Python so cuida da LOGICA do jogo: movimento da nave, geracao
#    procedural dos obstaculos, deteccao de colisao e HUD. Os dados sao
#    enviados ao shader por uniforms, entao o que voce ve e exatamente o
#    que colide.
#
#  Controles:  SETAS ou WASD = mover a nave (qualquer uma comeca / reinicia)
# ===========================================================================

import math
import random
from js import document

# --- ponte com JavaScript para enviar arrays a setUniform -------------------
try:
    _to_js = js_array            # helper fornecido pelo Py5Script
except NameError:
    from pyodide.ffi import to_js as _pyto_js
    def _to_js(x):
        return _pyto_js(x)

# ---------------------------------------------------------------------------
#  Constantes
# ---------------------------------------------------------------------------
MAX_OBS      = 8        # tambem definido como #define no shader
PLAY_HALF    = 7.0      # meia-extensao da area de movimento da nave
SHIP_RADIUS  = 0.55     # "raio" de colisao da nave
SPACING      = 15.0     # distancia entre obstaculos ao longo de Z
OB_START     = 30.0     # Z do primeiro obstaculo (nunca em cima da camera)

# ---------------------------------------------------------------------------
#  VERTEX SHADER  -  quad de tela cheia
#  (aPosition chega normalizado 0..1; mapeamos direto para clip space)
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
#  FRAGMENT SHADER  -  Raymarching dos obstaculos + fundo espacial em warp
# ---------------------------------------------------------------------------
FRAG = """
precision highp float;
#define MAX_OBS 8

uniform vec2  uResolution;
uniform float uTime;
uniform float uWarp;           // fase continua [0,1) do campo de estrelas
uniform int   uObCount;
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

float mapScene(vec3 p, out float mat){
  float d = 1e9;
  mat = 0.0;
  for(int i = 0; i < MAX_OBS; i++){
    if(i >= uObCount) break;
    float od = obstacleSDF(p, uObRel[i], uObRad[i], uObType[i]);
    if(od < d){ d = od; mat = 1.0; }
  }
  return d;
}
float mapDist(vec3 p){ float m; return mapScene(p, m); }

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
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;
  vec3 ro = vec3(0.0);
  vec3 rd = normalize(vec3(uv, 1.45));

  vec3 bg = background(rd, uv);

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
"""

# ---------------------------------------------------------------------------
#  Estado do jogo
# ---------------------------------------------------------------------------
prog = None
hud_el = None
msg_el = None
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
prev_key = False


def make_obstacle(n):
    """Obstaculo deterministico para o indice n (mesmo resultado sempre)."""
    rng = random.Random((n * 2654435761) & 0xFFFFFFFF)
    rad = rng.uniform(1.9, 3.1)
    lim = PLAY_HALF * 0.62
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
    global prog, W, H
    P5.createCanvas(900, 600, P5.WEBGL)
    P5.pixelDensity(1)
    P5.noStroke()
    W = P5.width
    H = P5.height
    prog = P5.createShader(VERT, FRAG)
    _setup_hud()


def _setup_hud():
    """HUD em overlay HTML por cima do canvas (renderizacao garantida)."""
    global hud_el, msg_el
    cnv = P5.canvas
    if cnv is None:
        cnv = document.querySelector("canvas")
    parent = cnv.parentNode
    parent.style.position = "relative"

    hud_el = document.createElement("div")
    hud_el.setAttribute("style",
        "position:absolute;top:8px;left:12px;color:#7fe0ff;"
        "font-family:monospace;font-size:16px;text-shadow:0 0 4px #000;"
        "pointer-events:none;z-index:10;white-space:pre;")
    parent.appendChild(hud_el)

    msg_el = document.createElement("div")
    msg_el.setAttribute("style",
        "position:absolute;top:40%;left:0;width:100%;text-align:center;"
        "font-family:monospace;pointer-events:none;z-index:10;"
        "text-shadow:0 0 6px #000;line-height:1.5;")
    parent.appendChild(msg_el)


def update(dt):
    global cam_z, px, py, speed, score, state, hit_flash

    mv = 16.0 * dt
    if P5.keyIsDown(P5.LEFT_ARROW) or P5.keyIsDown(65):   px -= mv   # A
    if P5.keyIsDown(P5.RIGHT_ARROW) or P5.keyIsDown(68):  px += mv   # D
    if P5.keyIsDown(P5.UP_ARROW) or P5.keyIsDown(87):     py += mv   # W
    if P5.keyIsDown(P5.DOWN_ARROW) or P5.keyIsDown(83):   py -= mv   # S

    px = max(-PLAY_HALF, min(PLAY_HALF, px))
    py = max(-PLAY_HALF, min(PLAY_HALF, py))

    speed = min(62.0, 18.0 + cam_z * 0.02)
    cam_z += speed * dt
    score = cam_z

    base = int((cam_z - OB_START) // SPACING)
    for n in range(base - 1, base + MAX_OBS + 1):
        if n < 0:
            continue
        z, cx, cy, rad, _ = make_obstacle(n)
        relz = z - cam_z
        if -rad < relz < rad:
            if math.hypot(cx - px, cy - py) < rad * 0.85 + SHIP_RADIUS:
                state = "over"
                hit_flash = 1.0
                break

    if hit_flash > 0.0:
        hit_flash = max(0.0, hit_flash - dt * 1.5)


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

    rel, rads, types, count = collect_obstacles()
    warp = (cam_z * 0.04) % 1.0

    P5.shader(prog)
    prog.setUniform("uResolution", _to_js([float(W), float(H)]))
    prog.setUniform("uTime", float(P5.millis()) / 1000.0)
    prog.setUniform("uWarp", float(warp))
    prog.setUniform("uObCount", int(count))
    prog.setUniform("uObRel", _to_js([float(v) for v in rel]))
    prog.setUniform("uObRad", _to_js([float(v) for v in rads]))
    prog.setUniform("uObType", _to_js([float(v) for v in types]))
    prog.setUniform("uHit", float(hit_flash))
    P5.rect(0, 0, W, H)

    update_hud()
    handle_keys()


def update_hud():
    hud_el.innerText = ("DISTANCIA: %d m\nRECORDE:   %d m\nVELOCIDADE: %d"
                        % (int(score), int(best), int(speed)))
    if state == "start":
        msg_el.innerHTML = (
            "<div style='font-size:32px;color:#ffe070'>TUNEL ESPACIAL INFINITO</div>"
            "<div style='font-size:18px;color:#cfeeff'>Desvie das formas que mudam</div>"
            "<div style='font-size:16px;color:#8fd6ff'>SETAS / WASD para voar</div>")
    elif state == "over":
        msg_el.innerHTML = (
            "<div style='font-size:32px;color:#ff8060'>VOCE COLIDIU</div>"
            "<div style='font-size:18px;color:#cfeeff'>Distancia: %d m</div>"
            "<div style='font-size:16px;color:#8fd6ff'>Mova para reiniciar</div>"
            % int(score))
    else:
        msg_el.innerHTML = ""


def handle_keys():
    """Comeca/reinicia ao pressionar qualquer tecla de movimento ou espaco."""
    global prev_key
    down = (P5.keyIsDown(32)
            or P5.keyIsDown(P5.LEFT_ARROW) or P5.keyIsDown(65)
            or P5.keyIsDown(P5.RIGHT_ARROW) or P5.keyIsDown(68)
            or P5.keyIsDown(P5.UP_ARROW) or P5.keyIsDown(87)
            or P5.keyIsDown(P5.DOWN_ARROW) or P5.keyIsDown(83))
    if down and not prev_key and state in ("start", "over"):
        reset_game()
    prev_key = down
