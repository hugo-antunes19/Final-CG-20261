# ===========================================================================
#  RETROVÍRUS  -  Computação Gráfica
#  Py5Script (PyScript + p5.js)  -  WEBGL + Shader GLSL (Raymarching SDF)
# ---------------------------------------------------------------------------
#  Fase 1: Túnel Epitelial — desvie dos cílios (Bézier 3D), infecte células
#  Fase 2: Tubo Sanguíneo  — endless runner com raymarching SDF
#
#  Controles: SETAS / WASD = mover   |   ESPAÇO = começar / reiniciar
# ===========================================================================

import math
import random
# from js import window as P5

try:
    _to_js = js_array            # helper fornecido pelo Py5Script
except NameError:
    from pyodide.ffi import to_js as _pyto_js
    def _to_js(x):
        return _pyto_js(x)

# ---------------------------------------------------------------------------
#  Constantes Fase 1
# ---------------------------------------------------------------------------
TUNNEL_RADIUS    = 220.0
SHIP_RADIUS_F1   = 18.0
SPEED_F1         = 3.5
MOVE_SPEED_F1    = 6.0
FWD_SPEED_F1  = 5.5

# CILIO_SPACING    = 120.0
# CILIOS_PER_RING  = 6
# CILIO_LEN        = 110.0
# CILIO_RADIUS_COL = 14.0

CELL_SPACING     = 250.0
CELL_RADIUS      = 22.0
CELL_COL_DIST    = SHIP_RADIUS_F1 + CELL_RADIUS

PONTOS_PARA_FASE2 = 5
VIEW_DIST        = 1200.0
SEED             = 42

# ---------------------------------------------------------------------------
#  Constantes cílio — substitua as existentes
# ---------------------------------------------------------------------------
CILIO_SPACING    = 120.0
CILIOS_PER_RING  = 4
CILIO_LEN        = 110.0
CILIO_RADIUS_COL = 14.0

WHIP_SEGS  = 4
WHIP_STIFF = 0.35
WHIP_DAMP  = 0.87
WHIP_FORCE = 0.5
WHIP_FREQ  = 1.2

# ---------------------------------------------------------------------------
#  Constantes Fase 2
# ---------------------------------------------------------------------------
MAX_OBS        = 8
TUNNEL_HALF    = 6.0
SHIP_RADIUS_F2 = 0.55
SPACING        = 16.0
OB_START       = 28.0
RIDGE_MOD      = 64.0

# ---------------------------------------------------------------------------
#  Shaders Fase 2
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

// cor do tunel: grade luminosa + linhas de velocidade ao longo de Z (rosa/nariz)
vec3 tunnelColor(vec3 p){
  float wx = p.x + uPlayer.x;
  float wy = p.y + uPlayer.y;
  float wz = p.z + uCamZ;
  float gx = smoothstep(0.06, 0.0, abs(fract(wz * 0.25) - 0.5) - 0.46);
  float gy = smoothstep(0.06, 0.0, abs(fract((wx + wy) * 0.5) - 0.5) - 0.46);
  vec3 base = vec3(0.75, 0.40, 0.30);  // Rosa/nariz
  vec3 glow = vec3(0.9, 0.6, 0.5) * (gx + gy);
  // pulso suave correndo pelo tunel (usa p.z local p/ evitar salto no wrap)
  glow += vec3(0.8, 0.4, 0.3) * smoothstep(0.9, 1.0, sin(p.z * 0.15 - uTime * 3.0) * 0.5 + 0.5) * 0.5;
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
FRAG = FRAG.replace("TUNNEL_HALF", "%.1f" % TUNNEL_HALF)


# ---------------------------------------------------------------------------
#  Cache global — adicione junto com os outros estados globais
# ---------------------------------------------------------------------------
cilio_cache = {}   # (ring, ci) → (base_z, angle, length, phase)
cilio_nodes = {}   # (ring, ci) → lista de dicts de nós com física

# ---------------------------------------------------------------------------
#  get_cilio — substitui make_cilio, nunca recria o que já existe
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
#  get_cilio — com distribuição em espiral
# ---------------------------------------------------------------------------
def get_cilio(ring_index, cilio_index):
    key = (ring_index, cilio_index)
    if key not in cilio_cache:
        rng    = random.Random((ring_index * 997 + cilio_index * 31 + SEED) & 0xFFFFFFFF)
        base_z = ring_index * CILIO_SPACING
        
        # --- O SEGREDO DO ESPAÇAMENTO ESPIRAL ---
        # Multiplicamos o número do aro por 30 graus (convertidos para radianos)
        # Aro 0 = 0°, Aro 1 = 30°, Aro 2 = 60°, etc...
        offset_anel = ring_index * math.radians(30)
        
        # O ângulo final é: A posição base (0, 90, 180...) + O giro do anel + Uma leve aleatoriedade natural
        angle  = (cilio_index / CILIOS_PER_RING) * math.tau + offset_anel + rng.uniform(-0.15, 0.15)
        
        length = rng.uniform(CILIO_LEN * 0.5, CILIO_LEN)
        phase  = rng.uniform(0, math.tau)
        cilio_cache[key] = (base_z, angle, length, phase)
    return cilio_cache[key]

# ---------------------------------------------------------------------------
#  init_cilio_nodes — cria a cadeia de física na primeira vez
# ---------------------------------------------------------------------------
def init_cilio_nodes(key, bx, by, bz, inx, iny, length):
    seg = length / WHIP_SEGS
    nodes = []
    for i in range(WHIP_SEGS + 1):
        nodes.append({
            'x':  bx + inx * seg * i,
            'y':  by + iny * seg * i,
            'vx': 0.0,
            'vy': 0.0,
            # rest_x/rest_y: posição de repouso ABSOLUTA do nó i
            'rx': bx + inx * seg * i,
            'ry': by + iny * seg * i,
        })
    cilio_nodes[key] = nodes

# ---------------------------------------------------------------------------
#  update_cilio_nodes — física de chicote, chamada 1x por frame por cílio
# ---------------------------------------------------------------------------
def update_cilio_nodes(key, bx, by, inx, iny, phase, t, dt):
    nodes = cilio_nodes[key]

    # Raiz sempre na parede — nunca se move
    nodes[0]['x'] = bx
    nodes[0]['y'] = by

    # Direção perpendicular ao eixo radial (plano XY)
    perp_x = -iny
    perp_y =  inx

    SUBSTEPS = 4
    sdt = dt / SUBSTEPS

    for _ in range(SUBSTEPS):
        for i in range(1, WHIP_SEGS + 1):
            n  = nodes[i]
            np = nodes[i - 1]

            # Mola: puxa de volta para posição de repouso relativa ao nó anterior
            # repouso relativo = nó i de repouso - nó i-1 de repouso
            rest_rel_x = nodes[i]['rx'] - nodes[i-1]['rx']
            rest_rel_y = nodes[i]['ry'] - nodes[i-1]['ry']

            target_x = np['x'] + rest_rel_x
            target_y = np['y'] + rest_rel_y

            dx = n['x'] - target_x
            dy = n['y'] - target_y

            # Força oscilatória cresce linearmente da base à ponta
            amp = WHIP_FORCE * (i / WHIP_SEGS)
            fx = -dx * WHIP_STIFF + perp_x * amp * math.sin(t * WHIP_FREQ       + phase + i * 0.5)
            fy = -dy * WHIP_STIFF + perp_y * amp * math.sin(t * WHIP_FREQ * 0.8 + phase + i * 0.4)

            n['vx'] = (n['vx'] + fx * sdt) * WHIP_DAMP
            n['vy'] = (n['vy'] + fy * sdt) * WHIP_DAMP
            n['x'] += n['vx']
            n['y'] += n['vy']

# ---------------------------------------------------------------------------
#  collect_visible_cilios — agora usa get_cilio (sem recriar)
# ---------------------------------------------------------------------------
def collect_visible_cilios():
    z0 = cam_z_f1 - 50.0
    z1 = cam_z_f1 + VIEW_DIST
    r0 = max(0, int(z0 // CILIO_SPACING))
    r1 = int(z1 // CILIO_SPACING) + 1
    return [
        ((ri, ci), *get_cilio(ri, ci))
        for ri in range(r0, r1)
        for ci in range(CILIOS_PER_RING)
    ]

# ---------------------------------------------------------------------------
#  draw_cilio — substitui a versão antiga inteira
# ---------------------------------------------------------------------------
def draw_cilio(key, base_z, angle, length, phase, t, dt):
    # 1. Posição da base na parede do túnel
    bx  = math.cos(angle) * TUNNEL_RADIUS
    by  = math.sin(angle) * TUNNEL_RADIUS
    
    # 2. Vetores de Direção
    # Vetor apontando para o centro (crescimento normal do cílio)
    inx = -math.cos(angle)
    iny = -math.sin(angle)
    # Vetor perpendicular (para fazer o cílio balançar de um lado para o outro)
    perp_x = -iny
    perp_y = inx

    # 3. A Mágica do Chicote: Atraso de Fase (Phase Delay)
    freq = 1.2 # Velocidade do chicote
    
    # Base (P0) - Fixa na parede
    p0x, p0y, p0z = bx, by, base_z
    
    # Ponto de Controle 1 (P1) - 1/3 do tamanho, balança um pouco
    sway1 = math.sin(t * freq + phase) * (length * 0.3)
    p1x = bx + inx * (length * 0.33) + perp_x * sway1
    p1y = by + iny * (length * 0.33) + perp_y * sway1
    p1z = base_z
    
    # Ponto de Controle 2 (P2) - 2/3 do tamanho. 
    # NOTE O "- 1.0" NO SENO: Ele faz o movimento atrasado em relação ao P1!
    sway2 = math.sin(t * freq + phase - 1.0) * (length * 0.5)
    p2x = bx + inx * (length * 0.66) + perp_x * sway2
    p2y = by + iny * (length * 0.66) + perp_y * sway2
    p2z = base_z
    
    # Ponta (P3) - Final do cílio. 
    # NOTE O "- 2.0": A ponta é a última a receber a onda do chicote!
    sway3 = math.sin(t * freq + phase - 2.0) * (length * 0.8)
    p3x = bx + inx * length + perp_x * sway3
    p3y = by + iny * length + perp_y * sway3
    p3z = base_z

    # 4. Renderização da Curva
    pulse = 0.6 + 0.4 * math.sin(t * 2.2 + phase)
    v = int(30 + pulse * 60)
    P5.stroke(v, v, v, 210)
    P5.strokeWeight(3.5)
    P5.noFill()

    P5.beginShape()
    P5.vertex(p0x, p0y, p0z)
    P5.bezierVertex(p1x, p1y, p1z, p2x, p2y, p2z, p3x, p3y, p3z)
    P5.endShape()

    # 5. Colisão (Checa se o vírus bateu na ponta do chicote)
    dz  = base_z - cam_z_f1
    if abs(dz) < CILIO_RADIUS_COL + SHIP_RADIUS_F1:
        if math.hypot(p3x - px_f1, p3y - py_f1) < CILIO_RADIUS_COL + SHIP_RADIUS_F1:
            return True
    return False

# ---------------------------------------------------------------------------
#  Estado global
# ---------------------------------------------------------------------------
prog = None
hud  = None   # createGraphics 2D — usado apenas na Fase 2
W = H = 0

state = "start"
prev_space = False

# Fase 1
cam_z_f1        = 0.0
px_f1           = 0.0
py_f1           = 0.0
pontos          = 0
best_f1         = 0
collected_cells = set()

# Fase 2
cam_z_f2  = 0.0
px_f2     = 0.0
py_f2     = 0.0
speed     = 18.0
score     = 0.0
best_f2   = 0.0
hit_flash = 0.0

# ---------------------------------------------------------------------------
#  Geração procedural
# ---------------------------------------------------------------------------

def make_cilio(ring_index, cilio_index):
    rng    = random.Random((ring_index * 997 + cilio_index * 31 + SEED) & 0xFFFFFFFF)
    base_z = ring_index * CILIO_SPACING
    angle  = (cilio_index / CILIOS_PER_RING) * math.tau + rng.uniform(-0.2, 0.2)
    length = rng.uniform(CILIO_LEN * 0.5, CILIO_LEN)
    phase  = rng.uniform(0, math.tau)
    return base_z, angle, length, phase

def make_cell(cell_index):
    rng = random.Random((cell_index * 1234567 + SEED) & 0xFFFFFFFF)
    z   = CELL_SPACING + cell_index * CELL_SPACING
    
    # Raio do sorteio de 20% a 70% da borda do túnel
    r   = rng.uniform(TUNNEL_RADIUS * 0.20, TUNNEL_RADIUS * 0.70)
    a   = rng.uniform(0, math.tau)
    
    return z, r * math.cos(a), r * math.sin(a)

# def collect_visible_cilios():
#     z0 = cam_z_f1 - 50.0
#     z1 = cam_z_f1 + VIEW_DIST
#     r0 = max(0, int(z0 // CILIO_SPACING))
#     r1 = int(z1 // CILIO_SPACING) + 1
#     return [make_cilio(ri, ci) for ri in range(r0, r1) for ci in range(CILIOS_PER_RING)]

def collect_visible_cells():
    z0 = cam_z_f1 - 50.0
    z1 = cam_z_f1 + VIEW_DIST
    i0 = max(0, int((z0 - CELL_SPACING) // CELL_SPACING))
    i1 = int((z1 - CELL_SPACING) // CELL_SPACING) + 2
    out = []
    for i in range(i0, i1 + 1):
        if i in collected_cells:
            continue
        z, cx, cy = make_cell(i)
        if z0 <= z <= z1:
            out.append((i, z, cx, cy))
    return out

def make_obstacle(n):
    rng = random.Random((n * 2654435761) & 0xFFFFFFFF)
    rad = rng.uniform(1.9, 3.1)
    lim = TUNNEL_HALF - rad - 0.4
    cx  = rng.uniform(-lim, lim)
    cy  = rng.uniform(-lim, lim)
    typ = rng.uniform(0.0, 6.28)
    return OB_START + n * SPACING, cx, cy, rad, typ

def collect_obstacles():
    base  = int((cam_z_f2 - OB_START) // SPACING)
    rel, rads, types = [], [], []
    count = 0
    n = max(0, base - 1)
    while count < MAX_OBS and n < base + MAX_OBS + 2:
        z, cx, cy, rad, typ = make_obstacle(n)
        relz = z - cam_z_f2
        n += 1
        if relz < -1.0 or relz > 150.0:
            continue
        rel.extend([cx - px_f2, cy - py_f2, relz])
        rads.append(rad)
        types.append(typ)
        count += 1
    while len(rads) < MAX_OBS:
        rel.extend([0.0, 0.0, 9999.0])
        rads.append(0.0)
        types.append(0.0)
    return rel, rads, types, count

# ---------------------------------------------------------------------------
#  Reset
# ---------------------------------------------------------------------------

def reset_fase_1():
    global cam_z_f1, px_f1, py_f1, pontos, collected_cells, state
    global cilio_cache, cilio_nodes   # ← adicione

    cilio_cache.clear()   # ← limpa ao reiniciar
    cilio_nodes.clear()
    
    P5.camera()
    P5.perspective()

    cam_z_f1 = px_f1 = py_f1 = 0.0
    pontos = 0
    collected_cells = set()
    state = "fase1"

def reset_fase_2():
    global cam_z_f2, px_f2, py_f2, speed, score, hit_flash, state

    P5.camera()
    P5.perspective()

    cam_z_f2 = px_f2 = py_f2 = 0.0
    speed = 18.0
    score = hit_flash = 0.0
    state = "fase2"

# ---------------------------------------------------------------------------
#  setup
# ---------------------------------------------------------------------------

def setup():
    global prog, hud, W, H
    P5.createCanvas(900, 600, P5.WEBGL)
    P5.pixelDensity(1)
    W, H = P5.width, P5.height
    prog = P5.createShader(VERT, FRAG)
    # hud é um buffer 2D separado — só usado na fase 2 (shader precisa de resetShader antes do image)
    hud = P5.createGraphics(W, H)

# ---------------------------------------------------------------------------
#  draw
# ---------------------------------------------------------------------------

def draw():

    P5.background(220, 180, 140)

    if state == "start":
        draw_menu("RETROVIRUS",
                  "Fase 1: O Tunel Epitelial",
                  "ESPACO para comecar")

    elif state == "fase1":
        push()
        draw_fase_1()
        pop()

    elif state == "fase2":
        push()
        draw_fase_2()
        pop()

    elif state == "over":
        draw_menu("COLISAO!",
                  "Infectou %d celulas" % pontos,
                  "ESPACO para reiniciar")

    elif state == "win":
        draw_menu("FASE 1 COMPLETA!",
                  "Infectou %d celulas" % pontos,
                  "ESPACO para a Fase 2")
    handle_space()
    

# ---------------------------------------------------------------------------
#  handle_space  — edge detection, só ESPAÇO
# ---------------------------------------------------------------------------

def handle_space():
    global prev_space
    # comeca/reinicia com ESPACO ou qualquer tecla de movimento
    down = (P5.keyIsDown(32)
            or P5.keyIsDown(P5.LEFT_ARROW) or P5.keyIsDown(65)
            or P5.keyIsDown(P5.RIGHT_ARROW) or P5.keyIsDown(68)
            or P5.keyIsDown(P5.UP_ARROW) or P5.keyIsDown(87)
            or P5.keyIsDown(P5.DOWN_ARROW) or P5.keyIsDown(83))
    if down and not prev_space:
        if state in ("start", "over"):
            reset_fase_1()
        elif state == "win":
            reset_fase_2()
    prev_space = down

# ---------------------------------------------------------------------------
#  Menu / telas estáticas — desenhadas direto no canvas WEBGL com texto 2D
#  Usamos ortho + translate para poder usar text() no modo WEBGL
# ---------------------------------------------------------------------------

# def draw_menu(title, line2, line3):
#     P5.background(10, 15, 25)
#     P5.resetShader()
#     P5.ortho()
#     P5.noLights()

#     # Caixa de fundo semitransparente
#     P5.noStroke()
#     P5.fill(0, 0, 0, 150)
#     P5.rectMode(P5.CENTER)
#     P5.rect(0, 0, W, 140)
#     P5.rectMode(P5.CORNER)

#     # Título
#     P5.textAlign(P5.CENTER, P5.CENTER)
#     P5.fill(255, 230, 120)
#     P5.textSize(34)
#     P5.text(title, 0, -28)

#     # Linha 2
#     P5.fill(220, 220, 220)
#     P5.textSize(18)
#     P5.text(line2, 0, 4)

#     # Linha 3
#     P5.fill(150, 230, 255)
#     P5.text(line3, 0, 34)

#     P5.textAlign(P5.LEFT, P5.BASELINE)

# def draw_menu(title, line2, line3):
#     P5.background(10, 15, 25)
#     P5.resetShader()
    
#     # Limpa o buffer 2D para desenhar o menu
#     hud.clear()
    
#     # Caixa de fundo semitransparente
#     hud.noStroke()
#     hud.fill(0, 0, 0, 150)
#     hud.rectMode(P5.CENTER)
#     hud.rect(W / 2, H / 2, W, 140)
#     hud.rectMode(P5.CORNER)

#     # Título
#     hud.textAlign(P5.CENTER, P5.CENTER)
#     hud.fill(255, 230, 120)
#     hud.textSize(34)
#     hud.text(title, W / 2, H / 2 - 28)

#     # Linha 2
#     hud.fill(220, 220, 220)
#     hud.textSize(18)
#     hud.text(line2, W / 2, H / 2 + 4)

#     # Linha 3
#     hud.fill(150, 230, 255)
#     hud.text(line3, W / 2, H / 2 + 34)

#     hud.textAlign(P5.LEFT, P5.BASELINE)
    
#     # Carimba o buffer na tela WEBGL
#     P5.image(hud, -W / 2, -H / 2, W, H)

def draw_menu(title, line2, line3):
    P5.background(220, 180, 140)
    P5.resetShader()
    
    # === A MÁGICA AQUI: Reseta a câmera 3D para o padrão ===
    P5.camera()
    P5.perspective()
    
    # Limpa o buffer 2D para desenhar o menu
    hud.clear()
    
    # Caixa de fundo semitransparente
    hud.noStroke()
    hud.fill(120, 80, 80, 180)
    hud.rectMode(P5.CENTER)
    hud.rect(W / 2, H / 2, W, 140)
    hud.rectMode(P5.CORNER)

    # Título
    hud.textAlign(P5.CENTER, P5.CENTER)
    hud.fill(255, 200, 100)
    hud.textSize(34)
    hud.text(title, W / 2, H / 2 - 28)

    # Linha 2
    hud.fill(255, 240, 180)
    hud.textSize(18)
    hud.text(line2, W / 2, H / 2 + 4)

    # Linha 3
    hud.fill(200, 100, 120)
    hud.text(line3, W / 2, H / 2 + 34)

    hud.textAlign(P5.LEFT, P5.BASELINE)
    
    # Carimba o buffer na tela WEBGL
    P5.image(hud, -W / 2, -H / 2, W, H)

# ---------------------------------------------------------------------------
#  Fase 1 — Túnel Epitelial (geometria 3D nativa p5.js)
# ---------------------------------------------------------------------------

def draw_fase_1():
    global cam_z_f1, px_f1, py_f1, pontos, best_f1, collected_cells, state

    t  = P5.millis() / 1000.0
    dt = min(0.05, P5.deltaTime / 1000.0)

    mv = MOVE_SPEED_F1

    # Lateral
    if P5.keyIsDown(P5.LEFT_ARROW)  or P5.keyIsDown(65): px_f1 += mv 
    if P5.keyIsDown(P5.RIGHT_ARROW) or P5.keyIsDown(68): px_f1 -= mv

    # Vertical
    if P5.keyIsDown(P5.UP_ARROW):    py_f1 -= mv
    if P5.keyIsDown(P5.DOWN_ARROW):  py_f1 += mv

    # Espaço = descer
    if P5.keyIsDown(32): py_f1 -= mv
    # Ctrl = descer
    if P5.keyIsDown(17): py_f1 += mv

    # Profundidade: W = acelera, S = freia/recua
    if P5.keyIsDown(87): cam_z_f1 += FWD_SPEED_F1
    if P5.keyIsDown(83): cam_z_f1 -= FWD_SPEED_F1 

    # Limita dentro do túnel
    dist = math.hypot(px_f1, py_f1)
    lim  = TUNNEL_RADIUS - SHIP_RADIUS_F1 - 10.0
    if dist > lim and dist > 0:
        px_f1 = px_f1 / dist * lim
        py_f1 = py_f1 / dist * lim

    P5.background(220, 180, 140)

    P5.camera(px_f1, py_f1,        cam_z_f1 - 250.0,
              px_f1, py_f1,        cam_z_f1 + 300.0,
              0, 1, 0)
    P5.perspective(P5.PI / 3.0, float(W) / float(H), 1.0, 5000.0)

    # Luzes acompanham a câmera
    # 1. Luz ambiente cor de vinho (elimina sombras pretas secas)
    P5.ambientLight(60, 20, 30) 
    
    # 2. Luz principal (da frente): Branca levemente amarelada (brilho molhado)
    P5.pointLight(255, 230, 200, px_f1, py_f1, cam_z_f1 + 100) 
    
    # 3. Luz de preenchimento (trás): Rosa choque/vermelho para dar subsurface scattering
    P5.pointLight(255, 50, 80, px_f1, py_f1, cam_z_f1 - 100)

    draw_tunnel(t)

    hit_cilio = False
    for item in collect_visible_cilios():
        key, base_z, angle, length, phase = item
        if draw_cilio(key, base_z, angle, length, phase, t, dt):
            hit_cilio = True

    for cell in collect_visible_cells():
        idx, z, base_cx, base_cy = cell
        amp   = 45.0
        vel_x = 1.3 + (idx % 3) * 0.2
        vel_y = 1.1 + (idx % 2) * 0.3
        dinamico_cx = base_cx + math.sin(t * vel_x + idx) * amp
        dinamico_cy = base_cy + math.cos(t * vel_y + idx * 0.8) * amp
        draw_cell(idx, z, dinamico_cx, dinamico_cy, t)
        dz = z - cam_z_f1
        if abs(dz) < CELL_COL_DIST and math.hypot(dinamico_cx - px_f1, dinamico_cy - py_f1) < CELL_COL_DIST:
            collected_cells.add(idx)
            pontos += 1
            if pontos > best_f1:
                best_f1 = pontos

    # Vírus
    P5.push()
    P5.translate(px_f1, py_f1, cam_z_f1)   # ← vírus também no z absoluto
    P5.noStroke()
    P5.fill(180, 30, 60)
    P5.sphere(SHIP_RADIUS_F1)
    for i in range(8):
        a = (i / 8.0) * math.tau
        P5.push()
        P5.translate(math.cos(a) * SHIP_RADIUS_F1 * 0.85,
                     math.sin(a) * SHIP_RADIUS_F1 * 0.85, 0)
        P5.fill(220, 60, 80)
        P5.sphere(5)
        P5.pop()
    P5.pop()

    draw_hud_f1_inline()

    if P5.keyIsDown(13):
        reset_fase_2()
        return

    if hit_cilio:
        state = "over"
    elif pontos >= PONTOS_PARA_FASE2:
        state = "win"


def draw_tunnel(t):
    SEGS  = 32
    RINGS = 20
    STEP  = VIEW_DIST / RINGS

    for ri in range(RINGS):
        # ← z absoluto: parte de cam_z_f1 - 50 em vez de -50
        z1_local = cam_z_f1 - 50.0 + ri * STEP
        z2_local = cam_z_f1 - 50.0 + (ri + 1) * STEP

        pulse1 = 0.5 + 0.5 * math.sin(z1_local * 0.012 - t * 2.5)
        pulse2 = 0.5 + 0.5 * math.sin(z2_local * 0.012 - t * 2.5)

        r1 = int(220 + pulse1 * 35)
        g1 = int(140 + pulse1 * 25)
        b1 = int(140 + pulse1 * 20)
        
        r2 = int(220 + pulse2 * 35)
        g2 = int(140 + pulse2 * 25)
        b2 = int(140 + pulse2 * 20)

        P5.noStroke()
        P5.beginShape(P5.TRIANGLE_STRIP)
        for si in range(SEGS + 1):
            a = (si / SEGS) * math.tau
            x = math.cos(a) * TUNNEL_RADIUS
            y = math.sin(a) * TUNNEL_RADIUS
            P5.fill(r1, g1, b1, 120)
            P5.vertex(x, y, z1_local)
            P5.fill(r2, g2, b2, 120)
            P5.vertex(x, y, z2_local)
        P5.endShape()

    P5.stroke(40, 180, 120, 100)
    P5.strokeWeight(0.8)
    P5.noFill()
    for li in range(8):
        a  = (li / 8.0) * math.tau
        xv = math.cos(a) * TUNNEL_RADIUS
        yv = math.sin(a) * TUNNEL_RADIUS
        P5.line(xv, yv, cam_z_f1 - 50.0, xv, yv, cam_z_f1 + VIEW_DIST)


# def draw_cilio(base_z, angle, length, phase, t):
#     z_local  = base_z - cam_z_f1
#     bx       = math.cos(angle) * TUNNEL_RADIUS
#     by       = math.sin(angle) * TUNNEL_RADIUS
#     inx      = -math.cos(angle)
#     iny      = -math.sin(angle)
#     sway     = math.sin(t * 1.8 + phase) * 0.35
#     sway2    = math.cos(t * 1.3 + phase + 1.0) * 0.2

#     p0x, p0y, p0z = bx, by, z_local
#     p1x = bx + inx * length * 0.33 + sway  * 60
#     p1y = by + iny * length * 0.33 + sway2 * 40
#     p1z = z_local + sway * 20
#     p2x = bx + inx * length * 0.66 + sway  * 100
#     p2y = by + iny * length * 0.66 + sway2 * 70
#     p2z = z_local + sway * 35
#     p3x = bx + inx * length + sway  * 120
#     p3y = by + iny * length + sway2 * 90
#     p3z = z_local + sway * 50

#     pulse = 0.6 + 0.4 * math.sin(t * 2.2 + phase)
#     P5.stroke(int(20+pulse*20), int(20+pulse*20), int(20+pulse*20), 200)
#     P5.strokeWeight(3.5)
#     P5.noFill()
#     P5.beginShape()
#     P5.vertex(p0x, p0y, p0z) # Nasce aqui
#     P5.bezierVertex(p1x, p1y, p1z, p2x, p2y, p2z, p3x, p3y, p3z) # Curva
#     P5.endShape()

#     if abs(p3z) < CILIO_RADIUS_COL + SHIP_RADIUS_F1:
#         if math.hypot(p3x - px_f1, p3y - py_f1) < CILIO_RADIUS_COL + SHIP_RADIUS_F1:
#             return True
#     return False


def draw_cell(idx, z, cx, cy, t):
    # z absoluto — câmera já posicionada em cam_z_f1
    pulse = 0.85 + 0.15 * math.sin(idx * 0.7 + t * 1.2)
    r     = CELL_RADIUS * pulse
    P5.push()
    P5.translate(cx, cy, z)   # ← era z - cam_z_f1
    P5.noStroke()
    P5.fill(255, 220, 100)
    P5.sphere(r)
    P5.fill(255, 240, 150, 100)
    P5.sphere(r * 1.35)
    P5.pop()


# def draw_hud_f1_inline():
#     """HUD desenhado direto no canvas WEBGL usando projeção ortográfica."""
#     P5.noLights()
#     P5.ortho(-W/2, W/2, -H/2, H/2, -1, 1)

#     # Fundo da caixa de HUD (canto superior esquerdo)
#     P5.noStroke()
#     P5.fill(30, 30, 50, 180)
#     P5.rectMode(P5.CORNER)
#     P5.rect(-W/2 + 10, -H/2 + 10, 220, 65, 8)

#     # Barra de progresso
#     bw = 190.0 * (pontos / PONTOS_PARA_FASE2)
#     P5.fill(60, 200, 100)
#     P5.rect(-W/2 + 18, -H/2 + 38, bw, 14, 4)

#     # Texto
#     P5.textSize(14)
#     P5.fill(80, 220, 120)
#     P5.textAlign(P5.LEFT, P5.TOP)
#     P5.text("CELULAS INFECTADAS", -W/2 + 20, -H/2 + 12)
#     P5.fill(200, 200, 200)
#     P5.text("%d / %d" % (pontos, PONTOS_PARA_FASE2), -W/2 + 20, -H/2 + 54)

#     P5.fill(120, 180, 255, 200)
#     P5.textSize(13)
#     P5.textAlign(P5.CENTER, P5.BOTTOM)
#     P5.text("WASD / setas: mover  |  desvie dos cilios!", 0, H/2 - 6)

#     P5.textAlign(P5.LEFT, P5.BASELINE)

#     # Restaura perspectiva para o próximo frame
#     P5.perspective(P5.PI / 3.0, float(W) / float(H), 1.0, 5000.0)

def draw_hud_f1_inline():
    # Limpa o buffer 2D
    hud.clear()

    # Fundo da caixa de HUD (canto superior esquerdo) — cor semi-transparente
    hud.noStroke()
    hud.fill(150, 100, 100, 180)
    hud.rectMode(P5.CORNER)
    hud.rect(10, 10, 220, 65, 8)

    # Barra de progresso (amarelo claro)
    bw = 190.0 * (pontos / PONTOS_PARA_FASE2)
    hud.fill(255, 220, 100)
    hud.rect(18, 38, bw, 14, 4)

    # Texto
    hud.textSize(14)
    hud.fill(255, 240, 150)
    hud.textAlign(P5.LEFT, P5.TOP)
    hud.text("CELULAS INFECTADAS", 20, 12)
    hud.fill(255, 240, 180)
    hud.text("%d / %d" % (pontos, PONTOS_PARA_FASE2), 20, 54)

    hud.fill(200, 100, 120, 200)
    hud.textSize(13)
    hud.textAlign(P5.CENTER, P5.BOTTOM)
    hud.text("WASD / setas: mover  |  desvie dos cilios!", W / 2, H - 6)

    hud.textAlign(P5.LEFT, P5.BASELINE)

    # Carimba na tela sem afetar o 3D
    P5.resetShader()
    P5.image(hud, -W / 2, -H / 2, W, H)

    # ← NOVO: restaura perspectiva 3D para o próximo frame
    P5.perspective(P5.PI / 3.0, float(W) / float(H), 1.0, 5000.0)

# ---------------------------------------------------------------------------
#  Fase 2 — Tubo Sanguíneo (shader raymarching)
# ---------------------------------------------------------------------------

def draw_fase_2():
    global cam_z_f2, px_f2, py_f2, speed, score, best_f2, hit_flash, state

    dt = min(0.05, P5.deltaTime / 1000.0)

    mv = 14.0 * dt
    if P5.keyIsDown(P5.LEFT_ARROW)  or P5.keyIsDown(65): px_f2 -= mv
    if P5.keyIsDown(P5.RIGHT_ARROW) or P5.keyIsDown(68): px_f2 += mv
    if P5.keyIsDown(P5.UP_ARROW)    or P5.keyIsDown(87): py_f2 += mv
    if P5.keyIsDown(P5.DOWN_ARROW)  or P5.keyIsDown(83): py_f2 -= mv

    lim   = TUNNEL_HALF - SHIP_RADIUS_F2
    px_f2 = max(-lim, min(lim, px_f2))
    py_f2 = max(-lim, min(lim, py_f2))

    speed     = min(60.0, 18.0 + cam_z_f2 * 0.02)
    cam_z_f2 += speed * dt
    score     = cam_z_f2
    if score > best_f2:
        best_f2 = score

    base = int((cam_z_f2 - OB_START) // SPACING)
    for n in range(base - 1, base + MAX_OBS + 1):
        if n < 0: continue
        z, cx, cy, rad, _ = make_obstacle(n)
        relz = z - cam_z_f2
        if -rad < relz < rad:
            if math.hypot(cx - px_f2, cy - py_f2) < rad * 0.85 + SHIP_RADIUS_F2:
                state     = "over"
                hit_flash = 1.0
                break

    if hit_flash > 0.0:
        hit_flash = max(0.0, hit_flash - dt * 1.5)

    rel, rads, types, count = collect_obstacles()
    P5.shader(prog)
    prog.setUniform("uResolution", _to_js([float(W), float(H)]))
    prog.setUniform("uTime",       float(P5.millis()) / 1000.0)
    prog.setUniform("uCamZ",       float(cam_z_f2 % RIDGE_MOD))
    prog.setUniform("uPlayer",     _to_js([float(px_f2), float(py_f2)]))
    prog.setUniform("uObCount",    int(count))
    prog.setUniform("uObRel",      _to_js([float(v) for v in rel]))
    prog.setUniform("uObRad",      _to_js([float(v) for v in rads]))
    prog.setUniform("uObType",     _to_js([float(v) for v in types]))
    prog.setUniform("uHit",        float(hit_flash))
    P5.rect(0, 0, W, H)

    # HUD fase 2 via buffer 2D (necessário porque o shader ocupa tudo)
    draw_hud_f2()


def draw_hud_f2():
    hud.clear()
    
    # Cores temáticas (nariz/pele)
    hud.fill(255, 200, 100)
    hud.textSize(18)
    
    # Lembre-se que agora usamos best_f2 em vez de best
    hud.text("DISTANCIA: %d m" % int(score), 16, 28)
    hud.text("RECORDE:   %d m" % int(best_f2), 16, 50) 
    hud.text("VEL: %d" % int(speed), W - 110, 28)
    
    P5.resetShader()
    P5.image(hud, -W / 2, -H / 2, W, H)