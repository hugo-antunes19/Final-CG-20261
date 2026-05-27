# ===========================================================================
#  TUNEL ESPACIAL INFINITO  -  Computacao Grafica
#  py5 / Py5Script (PyScript + p5.js)  -  WEBGL + Shader GLSL (Raymarching SDF)
# ---------------------------------------------------------------------------
#  Estrutura do projeto:
#    sketch.py      -> logica do jogo (este arquivo)
#    raymarch.vert  -> vertex shader  (quad de tela cheia)
#    raymarch.frag  -> fragment shader (raymarching 3D dos SDFs + fundo)
#
#  - Toda a cena 3D (obstaculos + fundo/estrelas) e gerada por MATEMATICA
#    dentro do fragment shader: raymarching de SDFs (esferas, cubos e toros
#    que se transformam) sobre um campo de estrelas em "warp".
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
MAX_OBS      = 8        # tambem definido como #define no raymarch.frag
PLAY_HALF    = 7.0      # meia-extensao da area de movimento da nave
SHIP_RADIUS  = 0.55     # "raio" de colisao da nave
SPACING      = 15.0     # distancia entre obstaculos ao longo de Z
OB_START     = 30.0     # Z do primeiro obstaculo (nunca em cima da camera)

# ---------------------------------------------------------------------------
#  Estado do jogo
# ---------------------------------------------------------------------------
prog = None
shader_ready = False
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
    # carrega os shaders dos arquivos .vert/.frag (assincrono no p5)
    prog = P5.loadShader("raymarch.vert", "raymarch.frag",
                         _on_shader_loaded, _on_shader_error)
    _setup_hud()


def _on_shader_loaded(s):
    global shader_ready
    shader_ready = True


def _on_shader_error(err):
    print("Erro ao carregar shader:", err)


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
    # espera os shaders terminarem de carregar
    if not shader_ready:
        P5.background(2, 4, 12)
        return

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
