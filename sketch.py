# ===========================================================================
#  RETROVÍRUS  -  Computação Gráfica
#  Py5Script (PyScript + p5.js)  -  WEBGL + Shader GLSL (Raymarching SDF)
# ---------------------------------------------------------------------------
#  Fase 1: Túnel Epitelial — desvie dos cílios (Bézier 3D), infecte células
#  Fase 2: Tubo Sanguíneo  — endless runner com raymarching SDF
#  Fase 3: Cérebro - sistema nervoso sendo colonizado pelo vírus (WIP)
#
#  Controles: SETAS / WASD = mover   |   ESPAÇO = começar / reiniciar
# ===========================================================================

import math
import random

try:
    _to_js = js_array            # helper fornecido pelo Py5Script
except NameError:
    from pyodide.ffi import to_js as _pyto_js
    def _to_js(x):
        return _pyto_js(x)

# ---------------------------------------------------------------------------
#  Constantes Fase 1 — Túnel Epitelial
# ---------------------------------------------------------------------------
TUNNEL_RADIUS    = 220.0    # Raio do cilindro do túnel (pixels)
SHIP_RADIUS_F1   = 12.0     # Raio da hitbox do vírus na Fase 1 (pixels)
MOVE_SPEED_F1    = 6.0      # Velocidade lateral do vírus (pixels/frame)
FWD_SPEED_F1     = 5.5      # Velocidade de avanço/recuo no eixo Z (pixels/frame)

CELL_RADIUS      = 22.0     # Raio visual da esfera de cada célula
CELL_COL_DIST    = SHIP_RADIUS_F1 + CELL_RADIUS  # Distância de colisão vírus↔célula

VIEW_DIST        = 1000.0   # Distância máxima de renderização à frente da câmera
SEED             = 42       # Semente global para geração procedural determinística

CILIO_RADIUS_COL = 14.0     # Raio de colisão da ponta do cílio

BOOGER_CLUSTER_SPACING = 190.0  # Distância média entre regiões com melecas
BOOGER_RADIUS_MIN      = 14.0   # Tamanho mínimo visual da meleca
BOOGER_RADIUS_MAX      = 32.0   # Tamanho máximo visual da meleca
BOOGER_CLUSTER_MIN     = 0      # Algumas regiões ficam limpas para parecer natural
BOOGER_CLUSTER_MAX     = 3      # Máximo de melecas por região procedural

# ---------------------------------------------------------------------------
#  Constantes Fase 2 — Corrente Sanguínea (Raymarching SDF)
# ---------------------------------------------------------------------------
MAX_OBS        = 8          # Máximo de obstáculos simultâneos enviados ao shader
TUNNEL_HALF    = 6.0        # Meio-raio do vaso sanguíneo (unidades do shader)
SHIP_RADIUS_F2 = 0.55       # Raio do vírus na Fase 2 (= VIRUS_R no shader)
SPACING        = 16.0       # Distância em Z entre obstáculos consecutivos
OB_START       = 28.0       # Posição Z do primeiro obstáculo
RIDGE_MOD      = 64.0       # Módulo para wrap de Z (evita perda de precisão float)
META_F2        = 1000.0     # Posição Z absoluta onde o cilindro acaba e a fase termina

# ---------------------------------------------------------------------------
#  Constantes do Vírus
# ---------------------------------------------------------------------------
VIRUS_SCALE_F2   = 40.0   # 1 unidade shader ≈ 22 pixels da Fase 1
VIRUS_R_BASE     = 12.0   # Raio inicial
VIRUS_R_MAX_MULT = 1.55   # Multiplicador máximo
VIRUS_SPIKES_MIN = 3      # Espinhos no início
VIRUS_SPIKES_MAX = 10     # Espinhos ao completar a Fase 1

# ---------------------------------------------------------------------------
#  Sistema de Dificuldade
# ---------------------------------------------------------------------------
DIFFICULTY_PRESETS = {
    0: {"nome": "Facil",   
        "fase1": {
            "cilios_ring": 2, "cilio_spc": 180.0, "cilio_max_len": 110.0, "cell_spacing": 150.0, "pontos": 3
            },
        "fase2": {
            "speed_ini": 12.0
            }},
    1: {"nome": "Normal",  
        "fase1": {
            "cilios_ring": 4, "cilio_spc": 120.0, "cilio_max_len": 130.0, "cell_spacing": 200.0, "pontos": 5
            },
        "fase2": {
            "speed_ini": 18.0
            }},
    2: {"nome": "Dificil", 
        "fase1": {
            "cilios_ring": 6, "cilio_spc":  100.0, "cilio_max_len": 140.0, "cell_spacing": 250.0, "pontos": 7
            },
        "fase2": {
            "speed_ini": 24.0
            }},
}

# ---------------------------------------------------------------------------
#  Conteúdo do Tutorial
# ---------------------------------------------------------------------------
TUTORIAL_SLIDES = [
    {
        "titulo": "FASE 1 - Tunel Epitelial",
        "corpo": [
            "Voce e um retrovirus tentando infectar",
            "as celulas do tecido nasal do hospedeiro.",
            "",
            "  > Infecte as celulas para avancar",
            "  > Desvie dos cilios ou e game over",
            "  > Mova-se com WASD ou setas",
        ],
        "dica": "Dica: os cilios balancam — antecipe o movimento!",
    },
    {
        "titulo": "FASE 2 - Corrente Sanguinea",
        "corpo": [
            "Voce penetrou na corrente sanguinea!",
            "",
            "  > Desvie de hemacias e globulos brancos",
            "  > A velocidade aumenta com o tempo",
            "  > Sobreviva ate chegar no sistema nervoso!",
            "",
        ],
        "dica": "Dica: globulos brancos sao maiores — use as bordas!",
    },
    {
        "titulo": "CONTROLES",
        "corpo": [
            "  Mover:             WASD  /  Setas",
            "  Pausar:            ESC",
            "  Confirmar/Iniciar: ESPACO ou ENTER",
            "  Avancar (debug):   ENTER  (na Fase 1)",
            "",
            "  Fase 2: L = toggle LOD  |  [ ] = intensidade",
        ],
        "dica": "",
    },
]

# ---------------------------------------------------------------------------
#  Shaders Fase 2
# ---------------------------------------------------------------------------
VERT = """
precision highp float;
attribute vec3 aPosition;
void main() {
  vec4 p = vec4(aPosition, 1.0);
  p.xy = p.xy * 2.0 - 1.0;
  gl_Position = vec4(p.xy, 0.9999, 1.0);
}
"""

FRAG = """
precision highp float;
#define MAX_OBS 8

#define TUNNEL_BEAT_AMP 0.24   
#define TUNNEL_BEAT_LAG 0.05   

#define BEAT_ZOOM      0.12    
#define BEAT_EXPOSURE  0.16    
#define BEAT_REDDEN    0.06    
#define VIGN_BASE      0.16    
#define VIGN_BEAT      0.55    

uniform vec2  uResolution;     
uniform float uTime;           
uniform float uCamZ;           
uniform float uAbsZ;           // Z absoluto para os cálculos da Meta F2
uniform vec2  uPlayer;         
uniform int   uObCount;        
uniform vec3  uObRel[MAX_OBS];
uniform float uObRad[MAX_OBS]; 
uniform float uObType[MAX_OBS];
uniform float uHit;            
uniform float uMetaZ;          // Posição de fim do túnel

uniform float uVirusR;          
uniform float uVirusNSpikes;    
uniform float uVirusSpikeLen;   
uniform float uVirusSpikeW;     
uniform vec3  uVirusBodyCol;    
uniform vec3  uVirusSpikeCol;   

uniform float uLodEnable;       
uniform float uLodStrength;     
uniform float uHeartHz;         
uniform float uPulsePhase;      

float sdSphere(vec3 p, float r){ 
  return length(p) - r; 
}

float sdCapsule(vec3 p, vec3 a, vec3 b, float r){
  vec3 pa = p - a, ba = b - a;
  float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h) - r;
}

mat2 rot(float a){ 
  float c = cos(a), s = sin(a); 
  return mat2(c, -s, s, c); 
}

float hash1(float n){
  float s = mod(floor(abs(n) * 100.0), 65537.0) + 1.0; 
  s = mod(75.0 * s + 74.0, 65537.0);                   
  s = mod(75.0 * s + 74.0, 65537.0);                   
  s = mod(75.0 * s + 74.0, 65537.0);
  return s / 65537.0;
}

float sdHemacia(vec3 p, float r){
  float disc = max(abs(p.y) - r * 0.09, length(p.xz) - r * 0.52);
  vec2 q = vec2(length(p.xz) - r * 0.52, p.y);
  float edge  = length(q) - r * 0.28;
  return min(disc, edge);
}

#define N_MICRO_MAX 24

float sdGlobuloBranco(vec3 p, float r, float seed, float lod){
  float d = sdSphere(p, r * 0.68);
  float lp = length(p);
  float lodMix = uLodEnable * uLodStrength;

  if(lp < r * 0.52) return d;
  if(lodMix > 0.001 && lod < 0.08) return d;
  if(lp > r * 1.08) return d;

  float hairT = mix(1.0, smoothstep(0.12, 0.82, lod), lodMix);
  int nHair = int(mix(float(N_MICRO_MAX), mix(5.0, float(N_MICRO_MAX), hairT), lodMix));

  for(int i = 0; i < N_MICRO_MAX; i++){
    if(i >= nHair) break;

    float fi = float(i);
    float y = 1.0 - (fi + 0.5) * (2.0 / float(N_MICRO_MAX));
    float w = sqrt(max(0.0, 1.0 - y * y));
    float theta = fi * 2.399963 + seed * 1.37;
    float h0 = hash1(seed + fi * 19.17);
    float h1 = hash1(seed + fi * 41.23);
    
    vec3 dir = normalize(vec3(cos(theta) * w, y, sin(theta) * w)
      + (vec3(h0, h1, fract(h0 + h1)) - 0.5) * 0.22);

    float surf = r * (0.66 + 0.05 * fract(h0 * 7.1));
    float hLen = r * (0.09 + 0.06 * fract(h1 * 11.3));
    float hRad = r * (0.030 + 0.018 * fract(h0 * 13.7));
    vec3 base = dir * surf;
    
    d = min(d, sdCapsule(p, base, base + dir * hLen, hRad));
  }
  return d;
}

float obstacleSDF(vec3 p, vec3 center, float r, float typ){
  vec3 rp = p - center;
  float ph = typ + uTime * 0.7;
  if(typ < 3.14){
    rp.xz = rot(ph * 0.22) * rp.xz;
    rp.yz = rot(ph * 0.14) * rp.yz;
    return sdHemacia(rp, r);
  }
  rp.xy = rot(ph * 0.4) * rp.xy;
  rp.xz = rot(ph * 0.3) * rp.xz;
  float lod = clamp(1.0 - center.z / 65.0, 0.0, 1.0);
  return sdGlobuloBranco(rp, r * 1.2, typ, lod);
}

float heartPulse(float phase);

float tunnelSDF(vec3 p){
  float wx = p.x + uPlayer.x;
  float wy = p.y + uPlayer.y;
  float wz = p.z + uCamZ;

  float beat = heartPulse(uPulsePhase - wz * TUNNEL_BEAT_LAG);
  float r    = TUNNEL_HALF - TUNNEL_BEAT_AMP * beat;

  // 1. Distância para a parede interna do tubo
  float dWall = r - length(vec2(wx, wy));
  
  // 2. Distância para o plano de corte (fim da fase usando o Z absoluto real)
  float absoluteZ = p.z + uAbsZ;
  float dEnd  = absoluteZ - uMetaZ; 

  // 3. CSG Intersection: O tecido só existe se bater nas duas condições
  float exactDist = max(dWall, dEnd);

  return exactDist * 0.9;
}
 
#define VIRUS_Z    8.0
#define MAX_SPIKES 12
 
float sdVirus(vec3 p){
  vec3 vp = p - vec3(0.0, 0.0, VIRUS_Z);
  vp.xy = rot(uTime * 0.18) * vp.xy;
 
  float R   = uVirusR;
  float sL  = uVirusSpikeLen;
  float sW  = uVirusSpikeW;
  float N   = uVirusNSpikes;
  float TAU = 6.28318530718;
 
  float d = sdSphere(vp, R);
 
  for(int i = 0; i < MAX_SPIKES; i++){
    if(float(i) >= N) break;
 
    float a_base = (float(i) / N) * TAU + uTime * 0.12;
    float sway   = sin(uTime * 1.8 + float(i) * 0.9) * 0.18;
    float tip_a  = a_base + sway;
 
    vec3 base_pt = vec3(cos(a_base) * R * 0.88, sin(a_base) * R * 0.88, 0.0);
    vec3 mid_pt  = vec3(cos(a_base + sway*0.5) * (R + sL*0.6),
                        sin(a_base + sway*0.5) * (R + sL*0.6), 0.0);
    vec3 tip_pt  = vec3(cos(tip_a) * (R + sL), sin(tip_a) * (R + sL), 0.0);
 
    vec3 ab, ap; float h;
    ab = mid_pt - base_pt; ap = vp - base_pt;
    h = clamp(dot(ap,ab)/dot(ab,ab), 0.0, 1.0);
    d = min(d, length(ap - h*ab) - sW*0.55);
 
    ab = tip_pt - mid_pt; ap = vp - mid_pt;
    h = clamp(dot(ap,ab)/dot(ab,ab), 0.0, 1.0);
    d = min(d, length(ap - h*ab) - sW*0.55);
 
    d = min(d, sdSphere(vp - tip_pt, sW));
  }
  return d;
}

vec3 virusColor(vec3 p, vec3 n, float dif, float amb, float fre){
  vec3 vp  = p - vec3(0.0, 0.0, VIRUS_Z);
  float distN = clamp((length(vp) - uVirusR) / uVirusSpikeLen, 0.0, 1.0);
  vec3 base   = mix(uVirusBodyCol, uVirusSpikeCol, distN);
  vec3 col    = base * (amb + dif * 0.9) + fre * uVirusSpikeCol * 0.5;
  return col;
}

float mapScene(vec3 p, out float mat){
  float d = tunnelSDF(p);
  mat = 0.0;
  
  float vd = sdVirus(p);
  if(vd < d){ d = vd; mat = 3.0; }
  
  for(int i = 0; i < MAX_OBS; i++){
    if(i >= uObCount) break;
    float od = obstacleSDF(p, uObRel[i], uObRad[i], uObType[i]);
    if(od < d){ 
      d = od; 
      mat = uObType[i] < 3.14 ? 1.0 : 2.0; 
    }
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

float thump(float cyc, float center, float w){
  float d = cyc - center;
  return exp(-d * d / (w * w));
}

float heartPulse(float phase){
  float cyc = fract(phase / 6.28318530718);
  float s1 = thump(cyc, 0.10, 0.052);          
  float s2 = thump(cyc, 0.27, 0.048) * 0.55;   
  return clamp(s1 + s2, 0.0, 1.0);
}

float vnoise(vec2 p){
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash1(dot(i + vec2(0.0, 0.0), vec2(1.0, 57.0)));
  float b = hash1(dot(i + vec2(1.0, 0.0), vec2(1.0, 57.0)));
  float c = hash1(dot(i + vec2(0.0, 1.0), vec2(1.0, 57.0)));
  float d = hash1(dot(i + vec2(1.0, 1.0), vec2(1.0, 57.0)));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec3 tunnelColor(vec3 p){
  float wx = p.x + uPlayer.x;
  float wy = p.y + uPlayer.y;
  float wz = p.z + uCamZ;
  float ang = atan(wy, wx);

  const float TISSUE_STRENGTH = 0.45; 
  const float FLOW_STRENGTH   = 0.18; 
  const float PULSE_STRENGTH  = 0.26; 

  float tissue = vnoise(vec2(ang * 11.0, wz * 2.4)) * 0.5
               + vnoise(vec2(ang * 23.0, wz * 5.2)) * 0.3
               + vnoise(vec2(ang * 47.0, wz * 10.5)) * 0.2;

  float flow = vnoise(vec2(ang * 8.0, wz * 0.12 - uTime * 0.6));

  float lag    = wz * 0.16 + ang * 0.22;
  float hrNorm = clamp((uHeartHz - 1.10) / 0.90, 0.0, 1.0);
  float pulse  = heartPulse(uPulsePhase - lag) * (0.85 + 0.15 * hrNorm);

  vec3 deep  = vec3(0.32, 0.050, 0.046); 
  vec3 flesh = vec3(0.44, 0.078, 0.058); 
  vec3 col   = mix(deep, flesh, clamp(tissue * TISSUE_STRENGTH + flow * FLOW_STRENGTH + 0.25, 0.0, 1.0));
  col += vec3(0.28, 0.06, 0.045) * (pulse * PULSE_STRENGTH);
  return col;
}

void main(){
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;

  float beatCam = heartPulse(uPulsePhase);

  vec3 ro = vec3(0.0);                                   
  vec3 rd = normalize(vec3(uv, 1.45 + BEAT_ZOOM * beatCam)); 

  float t = 0.0;        
  float mat = 0.0;      
  bool hit = false;     
  
  for(int i = 0; i < 150; i++){
    vec3 p = ro + rd * t;        
    float d = mapScene(p, mat);  
    if(d < 0.005){               
      hit = true; 
      break; 
    }
    t += d;                      
    if(t > 1000.0) break;         
  }

  vec3 col;
  vec3 brainLight = vec3(0.85, 0.95, 1.0); 
  vec3 darkRed = vec3(0.16, 0.025, 0.025);

  if(hit){
    vec3 p = ro + rd * t;        
    vec3 n = calcNormal(p);      
    
    // Luz apontando direto para frente (eixo Z)
    vec3 lig = normalize(vec3(0.0, 0.0, -1.0)); 
    
    float dif = clamp(dot(n, lig), 0.0, 1.0);  
    // Luz ambiente mais uniforme, dependendo menos do teto/chão
    float amb = 0.4 + 0.1 * n.y;              
    float fre = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 3.0);

    if(mat < 0.5){
      col = tunnelColor(p) * (amb + dif * 0.5);
    } else if(mat < 1.5){
      vec3 oc = vec3(0.85, 0.12, 0.08); 
      float sss = pow(clamp(dot(rd, n), 0.0, 1.0), 2.0) * 0.3;
      col = oc * (amb + dif * 0.8 + sss) + fre * vec3(0.9, 0.2, 0.1);
    } else if(mat < 2.5){
      vec3 oc = vec3(0.86, 0.88, 0.91);
      float rim = pow(fre, 1.4);
      float lodMix = uLodEnable * uLodStrength;
      float tex = sin(p.x * 15.0 + p.y * 19.0) * sin(p.y * 17.0 + p.z * 21.0) * 0.5 + 0.5;
      float texAmt = lodMix * 0.10;
      col = oc * (1.0 - texAmt + texAmt * tex) * (amb + dif * 0.92) + rim * vec3(0.95, 0.97, 1.0) * 0.45;
    } else {
      col = virusColor(p, n, dif, amb, fre);
    }
    
    // Efeito de Névoa normal quando bate em algo
    float fog = 1.0 - exp(-t * 0.05);
    col = mix(col, darkRed, fog);
  } else {
    // Se o raio não bateu em nada, ele escapou pelo FIM DO TÚNEL!
    float distToHole = max(0.0, (uMetaZ - uAbsZ) / max(rd.z, 0.001));
    float fog = 1.0 - exp(-distToHole * 0.022);
    
    // Fundo revela o brilho do cérebro
    col = mix(brainLight, darkRed, fog);
  }

  // Efeito Bloom/Flash: Nos últimos 70 metros, ofusca a tela toda de luz
  float flashOut = clamp((uAbsZ - (uMetaZ - 70.0)) / 70.0, 0.0, 1.0);
  col = mix(col, brainLight, flashOut);

  // Efeito de Flash Vermelho (Dano):
  col = mix(col, vec3(0.9, 0.05, 0.05), uHit * 0.6);

  col *= 1.0 + BEAT_EXPOSURE * beatCam;
  col += vec3(BEAT_REDDEN, 0.0, 0.0) * beatCam;
  float r2 = dot(uv, uv);
  float vignette = 1.0 - VIGN_BASE * r2 - VIGN_BEAT * beatCam * r2;
  col *= clamp(vignette, 0.0, 1.0);

  col = pow(col, vec3(0.4545));   
  gl_FragColor = vec4(col, 1.0);
}
"""
FRAG = FRAG.replace("TUNNEL_HALF", "%.1f" % TUNNEL_HALF)

# ---------------------------------------------------------------------------
#  Cache Global dos Cílios
# ---------------------------------------------------------------------------
cilio_cache = {}   
cilio_nodes = {}   

def get_cilio(indice_anel, indice_cilio):
    key = (indice_anel, indice_cilio)
    if key not in cilio_cache:
        rng    = random.Random((indice_anel * 997 + indice_cilio * 31 + SEED) & 0xFFFFFFFF)
        posicao_z = indice_anel * eff_cilio_spacing
        
        giro_espiral = indice_anel * math.radians(30)
        angulo = (indice_cilio / max(1, eff_cilios_per_ring)) * math.tau + giro_espiral + rng.uniform(-0.15, 0.15)
        
        comprimento = rng.uniform(eff_cilio_max_length * 0.5, eff_cilio_max_length)
        fase = rng.uniform(0, math.tau)
        cilio_cache[key] = (posicao_z, angulo, comprimento, fase)
    return cilio_cache[key]

def collect_visible_cilios():
    z_inicio = cam_z_f1 - 50.0
    z_fim = cam_z_f1 + VIEW_DIST
    anel_inicio = max(0, int(z_inicio // eff_cilio_spacing))
    anel_fim = int(z_fim // eff_cilio_spacing) + 1
    return [
        (get_cilio(anel, cilio))
        for anel in range(anel_inicio, anel_fim)
        for cilio in range(eff_cilios_per_ring)
    ]

def draw_cilio( base_z, angle, length, phase, t):
    bx  = math.cos(angle) * TUNNEL_RADIUS
    by  = math.sin(angle) * TUNNEL_RADIUS
    
    inx = -math.cos(angle)
    iny = -math.sin(angle)
    perp_x = -iny
    perp_y = inx

    freq = 1.2 
    
    p0x, p0y, p0z = bx, by, base_z
    
    sway1 = math.sin(t * freq + phase) * (length * 0.3)
    p1x = bx + inx * (length * 0.33) + perp_x * sway1
    p1y = by + iny * (length * 0.33) + perp_y * sway1
    p1z = base_z
    
    sway2 = math.sin(t * freq + phase - 1.0) * (length * 0.5)
    p2x = bx + inx * (length * 0.66) + perp_x * sway2
    p2y = by + iny * (length * 0.66) + perp_y * sway2
    p2z = base_z
    
    sway3 = math.sin(t * freq + phase - 2.0) * (length * 0.8)
    p3x = bx + inx * length + perp_x * sway3
    p3y = by + iny * length + perp_y * sway3
    p3z = base_z

    # 4. Renderização da Curva (substitua esta parte em draw_cilio)

    # Fios grossos e escuros, cor de pêlo
    P5.stroke(25, 15, 10, 240) 
    P5.strokeWeight(4.5)  # Um pouco mais espesso para marcar presença na tela
    P5.noFill()

    P5.beginShape()
    P5.vertex(p0x, p0y, p0z)
    P5.bezierVertex(p1x, p1y, p1z, p2x, p2y, p2z, p3x, p3y, p3z)
    P5.endShape()

    dz  = base_z - cam_z_f1
    if abs(dz) < CILIO_RADIUS_COL + SHIP_RADIUS_F1:
        tip_radius = CILIO_RADIUS_COL + SHIP_RADIUS_F1
        body_radius = SHIP_RADIUS_F1 + 4.0
        
        if math.hypot(p1x - px_f1, p1y - py_f1) < body_radius: return True
        if math.hypot(p2x - px_f1, p2y - py_f1) < body_radius: return True
        if math.hypot(p3x - px_f1, p3y - py_f1) < tip_radius: return True
    return False

# ---------------------------------------------------------------------------
#  Estado Global do Jogo
# ---------------------------------------------------------------------------
state = "menu"   # Estados: menu | tutorial | config | fase1 | fase2 | win | win_f2 | pausa | over

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
heart_hz_f2    = 1.25   
pulse_phase_f2 = 0.0

# LOD glóbulos brancos
lod_enabled  = True    
lod_strength = 1.0     
prev_l       = False
prev_lbr     = False   
prev_rbr     = False   

difficulty  = 1          
config_sel  = 0          

timers      = {"fase1": 0.0, "fase2": 0.0}   
timer_total = 0.0                              

menu_sel      = 0            
pausa_sel     = 0            
tutorial_page = 0            
prev_up       = False        
prev_down     = False        
prev_left     = False        
prev_right    = False        
prev_enter    = False        
prev_esc      = False        

state_antes_pausa = None     

def make_cell(indice_celula):
    rng = random.Random((indice_celula * 1234567 + SEED) & 0xFFFFFFFF)
    posicao_z = eff_cilio_spacing + indice_celula * eff_cilio_spacing
    raio_polar  = rng.uniform(TUNNEL_RADIUS * 0.20, TUNNEL_RADIUS * 0.70)
    angulo = rng.uniform(0, math.tau)
    return posicao_z, raio_polar * math.cos(angulo), raio_polar * math.sin(angulo)

def collect_visible_cells():
    z_inicio = cam_z_f1 - 50.0
    z_fim = cam_z_f1 + VIEW_DIST
    idx_inicio = max(0, int((z_inicio - eff_cilio_spacing) // eff_cilio_spacing))
    idx_fim = int((z_fim - eff_cilio_spacing) // eff_cilio_spacing) + 2
    resultado = []
    for i in range(idx_inicio, idx_fim + 1):
        if i in collected_cells:
            continue
        z, cx, cy = make_cell(i)
        if z_inicio <= z <= z_fim:
            resultado.append((i, z, cx, cy))
    return resultado

def make_boogers(indice_regiao):
    """Gera melecas grudadas na parede interna do tunel nasal.

    A geometria e deterministica para cada regiao, mantendo o mesmo desenho
    quando a camera avanca ou recua.
    """
    rng = random.Random((indice_regiao * 1103515245 + SEED + 8080) & 0xFFFFFFFF)
    z_base = BOOGER_CLUSTER_SPACING * 0.55 + indice_regiao * BOOGER_CLUSTER_SPACING
    quantidade = rng.randint(BOOGER_CLUSTER_MIN, BOOGER_CLUSTER_MAX)
    melecas = []

    for _ in range(quantidade):
        z = z_base + rng.uniform(-BOOGER_CLUSTER_SPACING * 0.45, BOOGER_CLUSTER_SPACING * 0.45)
        angle = rng.uniform(0, math.tau)
        radius = rng.uniform(BOOGER_RADIUS_MIN, BOOGER_RADIUS_MAX)
        melecas.append((z, angle, radius))

    return melecas

def collect_visible_boogers():
    """Retorna melecas visiveis na janela de renderizacao da Fase 1."""
    z_inicio = cam_z_f1 - 50.0
    z_fim = cam_z_f1 + VIEW_DIST
    idx_inicio = max(0, int((z_inicio - BOOGER_CLUSTER_SPACING * 0.55) // BOOGER_CLUSTER_SPACING) - 1)
    idx_fim = int((z_fim - BOOGER_CLUSTER_SPACING * 0.55) // BOOGER_CLUSTER_SPACING) + 2
    resultado = []
    for i in range(idx_inicio, idx_fim + 1):
        for z, angle, radius in make_boogers(i):
            if z_inicio <= z <= z_fim:
                resultado.append((i, z, angle, radius))
    return resultado

def make_obstacle(indice_obstaculo):
    rng = random.Random((indice_obstaculo * 2654435761) & 0xFFFFFFFF)

    eh_globulo = rng.random() < 0.3
    raio = rng.uniform(2.5, 3.5) if eh_globulo else rng.uniform(1.6, 2.8)
    
    z_base = OB_START + indice_obstaculo * SPACING
    tipo_visual = rng.uniform(3.15, 6.28) if eh_globulo else rng.uniform(0.0, 3.13)

    p_comp = rng.random()
    if p_comp < 0.4:
        comportamento = 0
    elif p_comp < 0.7:
        comportamento = 1
    else:
        comportamento = 2

    angulo_base = rng.uniform(0, math.tau)
    fase = rng.uniform(0, math.tau)  
    
    # =======================================================
    # FÍSICA CORRIGIDA: 
    # O centro da célula não passa do limite geométrico.
    # O -0.05 é uma tolerância microscópica para o SDF não fundir as texturas.
    # =======================================================
    limite_extremo = TUNNEL_HALF - raio - 0.05

    if comportamento == 0:
        dist_centro = rng.uniform(0.0, limite_extremo * 0.5) 
        freq = rng.uniform(0.04, 0.08)      
    elif comportamento == 1:
        dist_centro = rng.uniform(limite_extremo * 0.7, limite_extremo) 
        freq = rng.uniform(0.015, 0.035)                
    else:
        dist_centro = limite_extremo                 
        freq = rng.uniform(0.02, 0.05)       

    return z_base, raio, tipo_visual, comportamento, angulo_base, dist_centro, freq, fase

def collect_obstacles():
    indice_base = int((cam_z_f2 - OB_START) // SPACING)
    posicoes_relativas, raios, tipos = [], [], []
    contagem = 0
    n = max(0, indice_base - 1)
    
    while contagem < MAX_OBS and n < indice_base + MAX_OBS + 2:
        z_base, raio, tipo, comp, ang_base, dist, freq, fase = make_obstacle(n)
        
        # Evita gerar obstáculos após a linha de chegada
        if z_base > META_F2 - 20.0:
            n += 1
            continue

        # A distância em Z do obstáculo até a câmera
        dist_z = z_base - cam_z_f2
        
        # =======================================================
        # SISTEMA DE PADRÕES AUTÔNOMOS (O "Tempo" é o cam_z_f2)
        # =======================================================
        if comp == 0:
            # NORMAL: Fica na sua faixa, apenas tremendo (drift suave)
            anim = math.sin(cam_z_f2 * freq + fase) * 0.5
            cx = math.cos(ang_base) * dist + anim
            cy = math.sin(ang_base) * dist + anim
            
        elif comp == 1:
            # ORBITAL: Fica girando colado nas paredes do vaso.
            # Metade gira em sentido horário, metade anti-horário
            dir_giro = 1.0 if n % 2 == 0 else -1.0
            angulo_atual = ang_base + (cam_z_f2 * freq * dir_giro)
            cx = math.cos(angulo_atual) * dist
            cy = math.sin(angulo_atual) * dist
            
        else:
            # VARREDOR: Faz um pêndulo rasgando o vaso de uma extremidade à outra
            oscilacao = math.sin(cam_z_f2 * freq + fase) # Oscila perfeitamente de -1 a 1
            cx = math.cos(ang_base) * (dist * oscilacao)
            cy = math.sin(ang_base) * (dist * oscilacao)
        # =======================================================

        n += 1

        # Culling: descarta quem já ficou para trás ou está longe na névoa
        if dist_z < -1.0 or dist_z > 150.0:
            continue

        posicoes_relativas.extend([cx - px_f2, cy - py_f2, dist_z])
        raios.append(raio)
        tipos.append(tipo)
        contagem += 1
    
    # Preenche slots não utilizados do Shader com dados inertes
    while len(raios) < MAX_OBS:
        posicoes_relativas.extend([0.0, 0.0, 9999.0])
        raios.append(0.0)
        tipos.append(0.0)

    return posicoes_relativas, raios, tipos, contagem

def reset_fase_1():
    global cam_z_f1, px_f1, py_f1, pontos, collected_cells, state
    global cilio_cache, cilio_nodes, score

    apply_difficulty()        
    cilio_cache.clear()       
    cilio_nodes.clear()       
    
    P5.camera()               
    P5.perspective()          

    cam_z_f1 = px_f1 = py_f1 = 0.0
    pontos = 0
    score = 0.0
    collected_cells = set()
    timers["fase1"] = 0.0     
    timers["fase2"] = 0.0     
    state = "fase1"

def reset_fase_2():
    global cam_z_f2, px_f2, py_f2, speed, score, hit_flash, state
    global heart_hz_f2, pulse_phase_f2

    apply_difficulty()       

    P5.camera()
    P5.perspective()

    cam_z_f2 = px_f2 = py_f2 = 0.0
    speed          = eff_speed_ini_f2   
    score          = hit_flash = 0.0
    heart_hz_f2    = 1.25
    pulse_phase_f2 = 0.0
    timers["fase2"] = 0.0    
    state = "fase2"

def setup():
    global prog, hud, W, H, overlay_div
    canvas = P5.createCanvas(900, 600, P5.WEBGL)
    canvas.parent("game-container")
    P5.pixelDensity(1)                   
    W, H = P5.width, P5.height
    prog = P5.createShader(VERT, FRAG)   
    hud = P5.createGraphics(W, H)        
    
    overlay_div = None
    try:
        from js import document
        overlay_div = document.createElement("div")
        overlay_div.id = "global_hud_overlay"
        overlay_div.style.position = "absolute"
        overlay_div.style.top = "20px"
        overlay_div.style.right = "20px"
        overlay_div.style.color = "#FFD278"
        overlay_div.style.fontFamily = "monospace"
        overlay_div.style.fontSize = "18px"
        overlay_div.style.backgroundColor = "rgba(20,8,10,0.8)"
        overlay_div.style.padding = "12px"
        overlay_div.style.borderRadius = "8px"
        overlay_div.style.pointerEvents = "none"
        overlay_div.style.zIndex = "9999"
        overlay_div.style.display = "none"
        overlay_div.style.border = "1px solid rgba(255,255,255,0.2)"
        
        document.body.appendChild(overlay_div)
    except:
        pass

def draw():
    P5.background(220, 180, 140)

    if   state == "menu":     draw_menu_principal()
    elif state == "tutorial": draw_tutorial()
    elif state == "config":   draw_config()
    elif state == "fase1":    P5.push(); draw_fase_1(); P5.pop()
    elif state == "fase2":    P5.push(); draw_fase_2(); P5.pop()
    elif state == "win":      draw_win_screen()
    elif state == "win_f2":   draw_win_f2_screen()
    elif state == "pausa":    draw_pausa()
    elif state == "over":     draw_game_over()

    handle_esc()        
    handle_menu_nav()   
    handle_lod()        

    global overlay_div
    if 'overlay_div' in globals() and overlay_div:
        try:
            if state in ("fase1", "fase2", "pausa"):
                pt_total = int(pontos * 100 + score)
                tempo = _fmt_time(timers["fase1"] + timers["fase2"])
                overlay_div.innerHTML = f"<b>PONTUAÇÃO GLOBAL:</b> {pt_total}<br><br><b>TEMPO TOTAL:</b> {tempo}"
                overlay_div.style.display = "block"
                
                from js import document, window
                canvas_elt = document.querySelector("canvas")
                if canvas_elt:
                    rect = canvas_elt.getBoundingClientRect()
                    abs_top = window.scrollY + rect.top
                    abs_left = window.scrollX + rect.left
                    
                    overlay_div.style.top = f"{abs_top + 20}px"
                    overlay_div.style.left = f"{abs_left + rect.width - 20}px"
                    overlay_div.style.right = "auto"
                    overlay_div.style.transform = "translateX(-100%)"
            else:
                overlay_div.style.display = "none"
        except:
            pass

def handle_esc():
    global state, state_antes_pausa, pausa_sel, prev_esc
    esc   = P5.keyIsDown(27)
    esc_p = esc and not prev_esc

    if esc_p:
        if state in ("fase1", "fase2"):
            state_antes_pausa = state   
            pausa_sel         = 0
            state             = "pausa"
        elif state == "pausa":
            state = state_antes_pausa   
        elif state in ("tutorial", "config", "win", "win_f2", "over"):
            state = "menu"

    prev_esc = esc

def handle_menu_nav():
    global prev_up, prev_down, prev_left, prev_right, prev_enter

    up    = P5.keyIsDown(P5.UP_ARROW)
    down  = P5.keyIsDown(P5.DOWN_ARROW)
    left  = P5.keyIsDown(P5.LEFT_ARROW)
    right = P5.keyIsDown(P5.RIGHT_ARROW)
    enter = P5.keyIsDown(13) or P5.keyIsDown(32)   

    up_p    = up    and not prev_up
    down_p  = down  and not prev_down
    left_p  = left  and not prev_left
    right_p = right and not prev_right
    enter_p = enter and not prev_enter

    if state in ("menu", "tutorial", "config", "win", "win_f2", "over", "pausa"):
        _nav_action(up_p, down_p, left_p, right_p, enter_p)

    prev_up,    prev_down  = up,   down
    prev_left,  prev_right = left, right
    prev_enter = enter

def handle_lod():
    global lod_enabled, lod_strength, prev_l, prev_lbr, prev_rbr
    if state != "fase2":
        return

    l_down = P5.keyIsDown(76)
    if l_down and not prev_l:
        lod_enabled = not lod_enabled
    prev_l = l_down

    lb_down = P5.keyIsDown(219)
    if lb_down and not prev_lbr and lod_enabled:
        lod_strength = max(0.0, lod_strength - 0.1)
    prev_lbr = lb_down

    rb_down = P5.keyIsDown(221)
    if rb_down and not prev_rbr and lod_enabled:
        lod_strength = min(1.0, lod_strength + 0.1)
    prev_rbr = rb_down

def _fmt_time(seconds):
    s = int(seconds)
    return "%d:%02d" % (s // 60, s % 60)

def _hud_setup():
    P5.resetShader()
    P5.camera()
    P5.perspective()

def _hud_stamp():
    P5.image(hud, -W / 2, -H / 2, W, H)
    P5.perspective(P5.PI / 3.6, float(W) / float(H), 1.0, 5000.0)

def _hud_panel(cx, cy, w, h, r=10):
    hud.fill(35, 12, 20, 225)
    hud.stroke(160, 70, 90, 160)
    hud.strokeWeight(1.5)
    hud.rect(cx - w / 2, cy - h / 2, w, h, r)
    hud.noStroke()

def apply_difficulty():
    global eff_cilios_per_ring, eff_cilio_spacing, eff_cilio_max_length, eff_pontos_para_fase2, eff_speed_ini_f2
    p = DIFFICULTY_PRESETS[difficulty]
    eff_cilios_per_ring   = p["fase1"]["cilios_ring"]
    eff_cilio_spacing     = p["fase1"]["cilio_spc"]
    eff_cilio_max_length = p["fase1"]["cilio_max_len"]
    eff_pontos_para_fase2 = p["fase1"]["pontos"]
    eff_speed_ini_f2      = p["fase2"]["speed_ini"]

def update_timer(phase_key, dt):
    if phase_key in timers:
        timers[phase_key] += dt

def _ir_para_tutorial():
    global state, tutorial_page
    tutorial_page = 0
    state = "tutorial"

def _ir_para_config():
    global state, config_sel
    config_sel = 0
    state = "config"

def _config_change_value(going_left):
    global difficulty, lod_enabled, lod_strength
    n_diff = len(DIFFICULTY_PRESETS)
    if config_sel == 0:        
        step = -1 if going_left else 1
        difficulty = (difficulty + step) % n_diff
    elif config_sel == 1:      
        lod_enabled = not lod_enabled
    elif config_sel == 2:      
        if lod_enabled:
            lod_strength = max(0.0, min(1.0, lod_strength + (-0.1 if going_left else 0.1)))

def _confirm_pausa():
    global state
    if pausa_sel == 0:          
        state = state_antes_pausa
    elif pausa_sel == 1:        
        if   state_antes_pausa == "fase1": reset_fase_1()
        elif state_antes_pausa == "fase2": reset_fase_2()
        else:                              state = state_antes_pausa
    elif pausa_sel == 2:        
        state = "menu"

def _nav_action(up_p, down_p, left_p, right_p, enter_p):
    global state, menu_sel, tutorial_page, config_sel, pausa_sel

    if state == "menu":
        MENU_COUNT = 3
        if up_p:   menu_sel = (menu_sel - 1) % MENU_COUNT
        if down_p: menu_sel = (menu_sel + 1) % MENU_COUNT
        if enter_p:
            if   menu_sel == 0: reset_fase_1()
            elif menu_sel == 1: _ir_para_tutorial()
            elif menu_sel == 2: _ir_para_config()

    elif state == "tutorial":
        n = len(TUTORIAL_SLIDES)
        if right_p: tutorial_page = min(tutorial_page + 1, n - 1)
        if left_p:  tutorial_page = max(tutorial_page - 1, 0)
        if enter_p: state = "menu"

    elif state == "config":
        CONFIG_COUNT = 3
        if up_p:   config_sel = (config_sel - 1) % CONFIG_COUNT
        if down_p: config_sel = (config_sel + 1) % CONFIG_COUNT
        if (left_p or right_p): _config_change_value(left_p)
        if enter_p: state = "menu"

    elif state == "win":
        if enter_p: reset_fase_2()
        
    elif state == "win_f2":
        if enter_p: state = "menu" 

    elif state == "over":
        if enter_p: reset_fase_1()

    elif state == "pausa":
        PAUSA_COUNT = 3
        if up_p:   pausa_sel = (pausa_sel - 1) % PAUSA_COUNT
        if down_p: pausa_sel = (pausa_sel + 1) % PAUSA_COUNT
        if enter_p: _confirm_pausa()

def draw_menu_principal():
    _hud_setup()
    hud.clear()

    hud.noStroke()
    hud.fill(15, 5, 10, 245)
    hud.rect(0, 0, W, H)

    cx = W / 2
    t  = P5.millis() / 1000.0
    pulse = 0.96 + 0.04 * math.sin(t * 1.8)

    hud.textAlign(P5.CENTER, P5.CENTER)

    hud.fill(80, 10, 20, 180)
    hud.textSize(int(54 * pulse))
    hud.text("RETROVIRUS", cx + 2, H * 0.21 + 2)
    hud.fill(255, 80, 80)
    hud.textSize(int(54 * pulse))
    hud.text("RETROVIRUS", cx, H * 0.21)

    hud.fill(200, 140, 140)
    hud.textSize(14)
    hud.text("Computacao Grafica — 2026/1", cx, H * 0.21 + 42)

    hud.stroke(150, 60, 70, 120)
    hud.strokeWeight(1)
    hud.line(cx - 120, H * 0.36, cx + 120, H * 0.36)
    hud.noStroke()

    MENU_ITEMS = ["JOGAR", "TUTORIAL", "CONFIGURACOES"]
    base_y, spc_y = H * 0.44, 46

    for i, label in enumerate(MENU_ITEMS):
        y = base_y + i * spc_y
        sel = (i == menu_sel)
        if sel:
            hud.fill(120, 30, 40, 200)
            hud.rect(cx - 130, y - 16, 260, 32, 6)
            hud.fill(255, 130, 130)
            hud.textSize(19)
            hud.text("> " + label + " <", cx, y + 2)
        else:
            hud.fill(180, 120, 120)
            hud.textSize(16)
            hud.text(label, cx, y + 2)

    if best_f2 > 0 or best_f1 > 0:
        hud.fill(180, 140, 70, 210)
        hud.textSize(13)
        hud.text("Melhor — F1: %d cel   F2: %dm" % (best_f1, int(best_f2)), cx, H * 0.83)

    hud.fill(120, 85, 85, 200)
    hud.textSize(13)
    hud.text("↑ ↓  navegar   |   ENTER / ESPACO confirmar", cx, H - 16)

    hud.textAlign(P5.LEFT, P5.BASELINE)
    _hud_stamp()

def draw_tutorial():
    _hud_setup()
    hud.clear()

    hud.noStroke()
    hud.fill(12, 5, 15, 248)
    hud.rect(0, 0, W, H)

    slide = TUTORIAL_SLIDES[tutorial_page]
    n     = len(TUTORIAL_SLIDES)
    cx, cy = W / 2, H / 2

    _hud_panel(cx, cy, 530, 350)

    hud.textAlign(P5.CENTER, P5.CENTER)
    hud.fill(255, 165, 80)
    hud.textSize(22)
    hud.text(slide["titulo"], cx, cy - 138)

    hud.stroke(200, 110, 60, 100)
    hud.strokeWeight(1)
    hud.line(cx - 210, cy - 116, cx + 210, cy - 116)
    hud.noStroke()

    hud.fill(220, 205, 205)
    hud.textSize(15)
    for j, linha in enumerate(slide["corpo"]):
        hud.text(linha, cx, cy - 88 + j * 24)

    if slide.get("dica"):
        hud.fill(140, 210, 130)
        hud.textSize(13)
        hud.text(slide["dica"], cx, cy + 112)

    hud.fill(170, 130, 130)
    hud.textSize(13)
    hud.text("%d / %d" % (tutorial_page + 1, n), cx, cy + 135)

    if tutorial_page > 0:
        hud.fill(220, 185, 100)
        hud.textSize(15)
        hud.textAlign(P5.LEFT, P5.CENTER)
        hud.text("← ANTERIOR", 30, H - 20)
    if tutorial_page < n - 1:
        hud.fill(220, 185, 100)
        hud.textSize(15)
        hud.textAlign(P5.RIGHT, P5.CENTER)
        hud.text("PROXIMO →", W - 30, H - 20)

    hud.textAlign(P5.CENTER, P5.CENTER)
    hud.fill(120, 88, 88)
    hud.textSize(13)
    hud.text("ENTER / ESC = voltar ao menu", cx, H - 20)

    hud.textAlign(P5.LEFT, P5.BASELINE)
    _hud_stamp()

def draw_config():
    _hud_setup()
    hud.clear()

    hud.noStroke()
    hud.fill(12, 5, 15, 248)
    hud.rect(0, 0, W, H)

    cx, cy = W / 2, H / 2
    _hud_panel(cx, cy, 490, 310)

    hud.textAlign(P5.CENTER, P5.CENTER)
    hud.fill(255, 165, 80)
    hud.textSize(22)
    hud.text("CONFIGURACOES", cx, cy - 126)

    hud.stroke(200, 110, 60, 100)
    hud.strokeWeight(1)
    hud.line(cx - 195, cy - 106, cx + 195, cy - 106)
    hud.noStroke()

    lod_str = "ON"  if lod_enabled else "OFF"
    lod_int = ("%d%%" % int(lod_strength * 100)) if lod_enabled else "—"
    CONFIG_ITEMS = [
        ("Dificuldade",     DIFFICULTY_PRESETS[difficulty]["nome"]),
        ("LOD Globulos",    lod_str),
        ("LOD Intensidade", lod_int),
    ]

    base_y = cy - 56
    for i, (label, valor) in enumerate(CONFIG_ITEMS):
        y = base_y + i * 52
        sel = (i == config_sel)
        if sel:
            hud.fill(100, 25, 35, 190)
            hud.rect(cx - 200, y - 17, 400, 34, 5)
            hud.fill(255, 210, 100)
            ts = 17
        else:
            hud.fill(170, 150, 150)
            ts = 15

        hud.textSize(ts)
        hud.textAlign(P5.LEFT, P5.CENTER)
        hud.text(label, cx - 180, y)
        hud.textAlign(P5.RIGHT, P5.CENTER)
        hud.text(("< " if sel else "") + valor + (" >" if sel else ""), cx + 180, y)

    hud.textAlign(P5.CENTER, P5.CENTER)
    hud.fill(120, 88, 88)
    hud.textSize(13)
    hud.text("↑ ↓  item   |   ← →  valor   |   ENTER / ESC voltar", cx, H - 16)

    hud.textAlign(P5.LEFT, P5.BASELINE)
    _hud_stamp()

def draw_win_screen():
    _hud_setup()
    hud.clear()

    hud.noStroke()
    hud.fill(12, 5, 15, 235)
    hud.rect(0, 0, W, H)

    cx, cy = W / 2, H / 2
    _hud_panel(cx, cy, 430, 230)

    hud.textAlign(P5.CENTER, P5.CENTER)

    hud.fill(100, 255, 150)
    hud.textSize(28)
    hud.text("FASE 1 COMPLETA!", cx, cy - 86)

    hud.stroke(80, 200, 120, 80)
    hud.strokeWeight(1)
    hud.line(cx - 170, cy - 62, cx + 170, cy - 62)
    hud.noStroke()

    hud.fill(220, 200, 180)
    hud.textSize(16)
    hud.text("Celulas infectadas: %d" % pontos, cx, cy - 34)
    hud.text("Tempo da Fase 1:    %s"  % _fmt_time(timers["fase1"]), cx, cy - 8)

    hud.stroke(160, 120, 80, 60)
    hud.line(cx - 160, cy + 14, cx + 160, cy + 14)
    hud.noStroke()

    hud.fill(255, 200, 80)
    hud.textSize(15)
    hud.text("ESPACO / ENTER — entrar na Fase 2", cx, cy + 48)
    hud.fill(140, 95, 95)
    hud.textSize(13)
    hud.text("ESC — voltar ao menu", cx, cy + 76)

    hud.textAlign(P5.LEFT, P5.BASELINE)
    _hud_stamp()

def draw_win_f2_screen():
    global pontos, score, timers
    
    _hud_setup()
    hud.clear()

    # Fundo escuro levemente avermelhado/vitória
    hud.noStroke()
    hud.fill(12, 5, 20, 235)
    hud.rect(0, 0, W, H)

    cx, cy = W / 2, H / 2
    # Painel um pouco mais alto para acomodar o placar final
    _hud_panel(cx, cy, 460, 250)

    hud.textAlign(P5.CENTER, P5.CENTER)

    # Título de Vitória (Verde vibrante)
    hud.fill(100, 255, 150)
    hud.textSize(32)
    hud.text("VITORIA!", cx, cy - 90)

    hud.stroke(80, 200, 120, 80)
    hud.strokeWeight(1)
    hud.line(cx - 170, cy - 62, cx + 170, cy - 62)
    hud.noStroke()

    # Subtítulo temático
    hud.fill(220, 200, 180)
    hud.textSize(16)
    hud.text("O sistema do hospedeiro foi dominado.", cx, cy - 34)

    # Cálculo dos totais
    pontos_totais = int(pontos * 100 + score)
    tempo_total = _fmt_time(timers["fase1"] + timers["fase2"])

    # Placar Final em destaque (Amarelo/Dourado)
    hud.fill(255, 210, 120)
    hud.textSize(18)
    hud.text("Pontuacao Total: %d" % pontos_totais, cx, cy + 2)
    hud.text("Tempo Total: %s"  % tempo_total, cx, cy + 28)

    hud.stroke(160, 120, 80, 60)
    hud.line(cx - 160, cy + 58, cx + 160, cy + 58)
    hud.noStroke()

    # Instrução para voltar ao menu principal
    hud.fill(255, 200, 80)
    hud.textSize(15)
    hud.text("ESPACO / ENTER — voltar ao menu", cx, cy + 86)

    hud.textAlign(P5.LEFT, P5.BASELINE)
    _hud_stamp()

def draw_game_over():
    _hud_setup()
    hud.clear()

    hud.noStroke()
    hud.fill(12, 2, 5, 240)
    hud.rect(0, 0, W, H)

    cx, cy = W / 2, H / 2
    _hud_panel(cx, cy, 490, 330)

    hud.textAlign(P5.CENTER, P5.CENTER)

    hud.fill(255, 60, 60)
    hud.textSize(32)
    hud.text("COLISAO!", cx, cy - 140)

    hud.stroke(200, 60, 60, 80)
    hud.strokeWeight(1)
    hud.line(cx - 195, cy - 116, cx + 195, cy - 116)
    hud.noStroke()

    hud.fill(220, 200, 200)
    hud.textSize(15)
    hud.text("Celulas infectadas:    %d"   % pontos,      cx, cy - 84)
    hud.text("Distancia percorrida:  %dm"  % int(score),  cx, cy - 58)

    hud.stroke(160, 80, 80, 60)
    hud.line(cx - 165, cy - 36, cx + 165, cy - 36)
    hud.noStroke()

    hud.fill(180, 180, 165)
    hud.textSize(14)
    hud.text("Tempo F1: %s   |   Tempo F2: %s" % (
        _fmt_time(timers["fase1"]), _fmt_time(timers["fase2"])), cx, cy - 10)
    hud.text("Tempo total: %s" % _fmt_time(timer_total), cx, cy + 16)

    if best_f2 > 0 or best_f1 > 0:
        hud.stroke(160, 135, 50, 80)
        hud.line(cx - 165, cy + 38, cx + 165, cy + 38)
        hud.noStroke()
        hud.fill(225, 195, 80)
        hud.textSize(14)
        hud.text("★  Melhor — F1: %d cel   F2: %dm" % (
            best_f1, int(best_f2)), cx, cy + 62)

    hud.fill(200, 165, 100)
    hud.textSize(14)
    hud.text("ESPACO / ENTER — tentar novamente", cx, cy + 108)
    hud.fill(140, 95, 95)
    hud.textSize(13)
    hud.text("ESC — voltar ao menu", cx, cy + 134)

    hud.textAlign(P5.LEFT, P5.BASELINE)
    _hud_stamp()

def draw_pausa():
    _hud_setup()
    hud.clear()

    hud.noStroke()
    hud.fill(5, 2, 8, 215)
    hud.rect(0, 0, W, H)

    cx, cy = W / 2, H / 2
    _hud_panel(cx, cy, 370, 250)

    hud.textAlign(P5.CENTER, P5.CENTER)

    hud.fill(200, 220, 255)
    hud.textSize(26)
    hud.text("|| PAUSADO ||", cx, cy - 92)

    hud.stroke(130, 150, 210, 80)
    hud.strokeWeight(1)
    hud.line(cx - 145, cy - 70, cx + 145, cy - 70)
    hud.noStroke()

    PAUSA_ITEMS = ["RETOMAR  (ESC / ESPACO)", "REINICIAR FASE", "MENU PRINCIPAL"]
    base_y = cy - 30

    for i, label in enumerate(PAUSA_ITEMS):
        y = base_y + i * 46
        sel = (i == pausa_sel)
        if sel:
            hud.fill(75, 55, 115, 190)
            hud.rect(cx - 160, y - 15, 320, 30, 5)
            hud.fill(200, 220, 255)
            hud.textSize(16)
        else:
            hud.fill(145, 155, 195)
            hud.textSize(14)
        hud.text(label, cx, y)

    hud.fill(95, 88, 118)
    hud.textSize(12)
    hud.text("↑ ↓  navegar   |   ENTER confirmar", cx, H - 16)

    hud.textAlign(P5.LEFT, P5.BASELINE)
    _hud_stamp()

def virus_params(prog_t):
    virus_r   = _lerp(VIRUS_R_BASE, VIRUS_R_BASE * VIRUS_R_MAX_MULT, prog_t)
    n_spikes  = VIRUS_SPIKES_MIN + int(prog_t * (VIRUS_SPIKES_MAX - VIRUS_SPIKES_MIN))
    spike_len = _lerp(8.0, 22.0, prog_t)
    spike_w   = _lerp(2.5,  5.0, prog_t)
 
    br = int(_lerp(175, 195, prog_t))
    bg = int(_lerp(95,   18, prog_t))
    bb = int(_lerp(120,  48, prog_t))
    sr = min(255, br + 50)
    sg = min(255, bg + 67)
    sb = min(255, bb + 62)
 
    return {
        "virus_r":    virus_r,
        "n_spikes":   n_spikes,
        "spike_len":  spike_len,
        "spike_w":    spike_w,
        "body_rgb":   (br, bg, bb),
        "spike_rgb":  (sr, sg, sb),
    }

def draw_fase_1():
    global cam_z_f1, px_f1, py_f1, pontos, best_f1, collected_cells, state
    global timer_total

    t  = P5.millis() / 1000.0
    dt = min(0.05, P5.deltaTime / 1000.0)
    update_timer("fase1", dt)   

    mv = MOVE_SPEED_F1

    # Lateral
    if P5.keyIsDown(65): px_f1 += mv 
    if P5.keyIsDown(68): px_f1 -= mv

    if P5.keyIsDown(P5.UP_ARROW):    py_f1 -= mv
    if P5.keyIsDown(P5.DOWN_ARROW):  py_f1 += mv

    # Espaço = subir
    if P5.keyIsDown(32): py_f1 -= mv
    if P5.keyIsDown(17): py_f1 += mv

    if P5.keyIsDown(87): cam_z_f1 += FWD_SPEED_F1
    if P5.keyIsDown(83): cam_z_f1 -= FWD_SPEED_F1 

    dist = math.hypot(px_f1, py_f1)
    lim  = TUNNEL_RADIUS - SHIP_RADIUS_F1 - 10.0
    if dist > lim and dist > 0:
        px_f1 = px_f1 / dist * lim
        py_f1 = py_f1 / dist * lim

    P5.background(125, 46, 46)

    P5.camera(px_f1, py_f1,        cam_z_f1 - 150.0,
              px_f1, py_f1,        cam_z_f1 + 300.0,
              0, 1, 0)
    P5.perspective(P5.PI / 3.6, float(W) / float(H), 1.0, 5000.0)

    P5.ambientLight(115, 53, 68) 
    # P5.ambientLight(219, 160, 174) 
    
    # 2. Luz principal (da frente): Branca levemente amarelada (brilho molhado)
    P5.pointLight(255, 230, 200, px_f1, py_f1, cam_z_f1 + 100) 
    P5.pointLight(255, 50, 80, px_f1, py_f1, cam_z_f1 - 100)

    # Progressão visual da infecção (0.0 → 1.0 conforme células coletadas)
    prog_t = min(1.0, pontos / eff_pontos_para_fase2)  

    draw_tunnel(t)

    for booger in collect_visible_boogers():
        _, z, angle, radius = booger
        draw_booger(z, angle, radius, prog_t)

    hit_cilio = False
    for item in collect_visible_cilios():
        base_z, angle, length, phase = item
        if draw_cilio( base_z, angle, length, phase, t):
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

    # =======================================================================
    #  Renderização do Vírus (Jogador) — Evolução Visual
    # =======================================================================

    draw_virus_f1(prog_t, t, px_f1, py_f1, cam_z_f1)

    if hit_cilio:
        timer_total = timers["fase1"]   
        state = "over"
    elif pontos >= eff_pontos_para_fase2:
        state = "win"

def draw_virus_f1(prog_t, t, px, py, cam_z):
    vp = virus_params(prog_t)

    virus_r    = vp["virus_r"]
    n_spikes   = vp["n_spikes"]
    spike_len  = vp["spike_len"]
    spike_w    = vp["spike_w"]
    br, bg, bb = vp["body_rgb"]
    sr, sg, sb = vp["spike_rgb"]

    P5.push()
    P5.translate(px, py, cam_z)

    P5.noFill()
    P5.strokeWeight(spike_w)

    for i in range(n_spikes):
        a_base = (i / n_spikes) * math.tau + t * 0.12   
        sway   = math.sin(t * 1.8 + i * 0.9) * 0.18    
        tip_a  = a_base + sway

        bx = math.cos(a_base) * virus_r * 0.88
        by = math.sin(a_base) * virus_r * 0.88

        mx = math.cos(a_base + sway * 0.5) * (virus_r + spike_len * 0.6)
        my = math.sin(a_base + sway * 0.5) * (virus_r + spike_len * 0.6)

        tx = math.cos(tip_a) * (virus_r + spike_len)
        ty = math.sin(tip_a) * (virus_r + spike_len)

        P5.stroke(br, bg, bb, 210)
        P5.line(bx, by, 0, mx, my, 0)

        P5.stroke(sr, sg, sb, 220)
        P5.line(mx, my, 0, tx, ty, 0)

        P5.noStroke()
        P5.fill(sr, sg, sb, 230)
        P5.push()
        P5.translate(tx, ty, 0)
        P5.sphere(spike_w * 1.15)
        P5.pop()

    P5.noStroke()

    P5.fill(br, bg, bb)
    P5.sphere(virus_r)

    spec_alpha = int(_lerp(128, 80, prog_t))   
    P5.fill(255, 220, 230, spec_alpha)
    P5.push()
    P5.translate(-virus_r * 0.32, -virus_r * 0.38, virus_r * 0.2)
    P5.sphere(virus_r * 0.42)
    P5.pop()

    P5.pop()   

def draw_booger(z, angle, radius, infection_t):
    infection_t = max(0.0, min(1.0, infection_t))

    # 1. Cor Base: de um marrom bem mais escuro e sujo (70, 50, 20) para o verde
    br = int(_lerp(64,  104, infection_t))
    bg = int(_lerp(38, 166, infection_t))
    bb = int(_lerp(6,   23, infection_t))

    # 2. Cor Emissiva (Brilho Próprio): começa em 0 (não emite luz) e escala 
    # gradativamente multiplicando por infection_t. O marrom não brilha mais!
    em_r = int((br // 5) * infection_t)
    em_g = int((bg // 5) * infection_t)
    em_b = int((bb // 5) * infection_t)

    cx = math.cos(angle) * TUNNEL_RADIUS
    cy = math.sin(angle) * TUNNEL_RADIUS

    # Rotação para grudar na parede do cilindro
    rot_z = angle + P5.PI / 2

    P5.push()
    P5.translate(cx, cy, z)
    P5.rotateZ(rot_z)
    P5.noStroke()
    
    P5.fill(br, bg, bb, 210) 
    # Aplica o brilho progressivo
    P5.emissiveMaterial(em_r, em_g, em_b)
    P5.specularMaterial(150)
    P5.shininess(200.0) 

    # Criação do Cluster Amorfo e Estático
    rng = random.Random(int(z * 1000)) 
    num_blobs = rng.randint(3, 5)

    for i in range(num_blobs):
        P5.push()
        
        # Deslocamento irregular no plano da parede
        dx = rng.uniform(-radius * 0.4, radius * 0.4)
        dy = rng.uniform(-radius * 0.3, radius * 0.6) 
        dz_local = rng.uniform(-radius * 0.1, radius * 0.1)
        
        P5.translate(dx, dy, dz_local)
        P5.rotateZ(rng.uniform(0, math.tau))
        
        # Tamanhos aleatórios e estáticos para cada bolha
        r_x = radius * rng.uniform(0.7, 1.2)
        r_y = radius * rng.uniform(0.4, 0.8)
        r_z = radius * rng.uniform(0.04, 0.08) # Achatado contra a parede
        
        P5.ellipsoid(r_x, r_y, r_z)
        
        P5.pop()

    P5.pop()

def draw_tunnel(t):
    SEGS  = 32
    RINGS = 24
    STEP  = (VIEW_DIST + 200) // RINGS

    for ri in range(RINGS):
        z1_local = cam_z_f1 - 200.0 + ri * STEP
        z2_local = cam_z_f1 - 200.0 + (ri + 1) * STEP

        pulse1 = 0.5 + 0.5 * math.sin(z1_local * 0.012 - t * 2.5)
        pulse2 = 0.5 + 0.5 * math.sin(z2_local * 0.012 - t * 2.5)

        r1 = int(200 + pulse1 * 28)
        g1 = int(200 + pulse1 * 12)
        b1 = int(200 + pulse1 * 10)
        
        r2 = int(200 + pulse2 * 28)
        g2 = int(200 + pulse2 * 12)
        b2 = int(200 + pulse2 * 20)

        P5.noStroke()
        P5.beginShape(P5.TRIANGLE_STRIP)
        for si in range(SEGS + 1):
            a = (si / SEGS) * math.tau
            x = math.cos(a) * TUNNEL_RADIUS
            y = math.sin(a) * TUNNEL_RADIUS
            P5.fill(r1, g1, b1, 255)
            P5.vertex(x, y, z1_local)
            P5.emissiveMaterial(r2, g2, b2, 150)
            P5.vertex(x, y, z2_local)
            P5.emissiveMaterial(0, 0, 0, 255)
        P5.endShape()

def draw_cell(idx, z, cx, cy, t):
    pulse = 0.85 + 0.15 * math.sin(idx * 0.7 + t * 1.2)
    r     = CELL_RADIUS * pulse
    P5.push()
    P5.translate(cx, cy, z)   
    P5.noStroke()
    P5.fill(65, 209, 139)
    P5.sphere(r)
    P5.fill(65, 209, 139, 100)
    P5.sphere(r * 1.35)
    P5.pop()

def draw_fase_2():
    global cam_z_f2, px_f2, py_f2, speed, score, best_f2, hit_flash, state
    global heart_hz_f2, pulse_phase_f2, timer_total

    dt = min(0.05, P5.deltaTime / 1000.0)
    update_timer("fase2", dt)   

    mv = 14.0 * dt
    if P5.keyIsDown(P5.LEFT_ARROW)  or P5.keyIsDown(65): px_f2 -= mv
    if P5.keyIsDown(P5.RIGHT_ARROW) or P5.keyIsDown(68): px_f2 += mv
    if P5.keyIsDown(P5.UP_ARROW)    or P5.keyIsDown(87): py_f2 += mv
    if P5.keyIsDown(P5.DOWN_ARROW)  or P5.keyIsDown(83): py_f2 -= mv

    lim   = TUNNEL_HALF - SHIP_RADIUS_F2
    pdist = math.hypot(px_f2, py_f2)
    if pdist > lim and pdist > 0:
        px_f2 = px_f2 / pdist * lim
        py_f2 = py_f2 / pdist * lim

    speed     = min(60.0, eff_speed_ini_f2 + cam_z_f2 * 0.02)   
    cam_z_f2 += speed * dt
    score     = cam_z_f2
    if score > best_f2:
        best_f2 = score

    # ======== NOVA LÓGICA DE VITÓRIA ========
    if cam_z_f2 >= META_F2:
        timer_total = timers["fase1"] + timers["fase2"]
        state = "win_f2"
        return
    # ========================================

    speed_t = (speed - 18.0) / (60.0 - 18.0)
    speed_t = max(0.0, min(1.0, speed_t))
    target_hz = _lerp(1.10, 2.00, speed_t)
    heart_hz_f2 = _lerp(heart_hz_f2, target_hz, min(1.0, dt * 2.3))
    pulse_phase_f2 = (pulse_phase_f2 + heart_hz_f2 * dt * math.tau) % math.tau

    virus_z = cam_z_f2 + 8.0
    base = int((virus_z - OB_START) // SPACING)
    for n in range(base - 2, base + MAX_OBS + 2):
        if n < 0: continue
        
        z, rad, tipo, comp, ang_base, dist, freq, fase = make_obstacle(n)
        
        if z > META_F2 - 20.0:
            continue

        dz = z - virus_z
        
        if abs(dz) < rad * 0.45:
            if comp == 0:
                anim = math.sin(cam_z_f2 * freq + fase) * 0.5
                cx = math.cos(ang_base) * dist + anim
                cy = math.sin(ang_base) * dist + anim
            elif comp == 1:
                dir_giro = 1.0 if n % 2 == 0 else -1.0
                angulo_atual = ang_base + (cam_z_f2 * freq * dir_giro)
                cx = math.cos(angulo_atual) * dist
                cy = math.sin(angulo_atual) * dist
            else:
                oscilacao = math.sin(cam_z_f2 * freq + fase)
                cx = math.cos(ang_base) * (dist * oscilacao)
                cy = math.sin(ang_base) * (dist * oscilacao)

            # =======================================================
            # HITBOXES HONESTAS:
            # tipo >= 3.14 (Glóbulo Branco): Esfera cheia, hitbox de 85% do raio visual
            # tipo < 3.14 (Hemácia): Disco achatado, hitbox de 70% do raio visual
            # =======================================================
            hitbox_rad = rad * 0.85 if tipo >= 3.14 else rad * 0.70

            if math.hypot(cx - px_f2, cy - py_f2) < hitbox_rad + SHIP_RADIUS_F2:
                timer_total = timers["fase1"] + timers["fase2"]  
                state       = "over"
                hit_flash   = 1.0
                break

    if hit_flash > 0.0:
        hit_flash = max(0.0, hit_flash - dt * 1.5)

    rel, rads, types, count = collect_obstacles()
    P5.shader(prog)
    prog.setUniform("uResolution", _to_js([float(W), float(H)]))
    prog.setUniform("uTime",       float(P5.millis()) / 1000.0)
    prog.setUniform("uCamZ",       float(cam_z_f2 % RIDGE_MOD))
    prog.setUniform("uAbsZ",       float(cam_z_f2))               # Passando o Z absoluto real para os cálculos finais
    prog.setUniform("uPlayer",     _to_js([float(px_f2), float(py_f2)]))
    prog.setUniform("uObCount",    int(count))
    prog.setUniform("uObRel",      _to_js([float(v) for v in rel]))
    prog.setUniform("uObRad",      _to_js([float(v) for v in rads]))
    prog.setUniform("uObType",     _to_js([float(v) for v in types]))
    prog.setUniform("uHit",        float(hit_flash))
    prog.setUniform("uLodEnable",  1.0 if lod_enabled else 0.0)
    prog.setUniform("uLodStrength", float(lod_strength))
    prog.setUniform("uHeartHz",    float(heart_hz_f2))
    prog.setUniform("uPulsePhase", float(pulse_phase_f2))
    prog.setUniform("uMetaZ",      float(META_F2))
    set_virus_uniforms(prog, 1.0)
    P5.noStroke()              
    P5.rect(0, 0, W, H)
    
def _lerp(a, b, x):
    return a + (b - a) * x
 
def set_virus_uniforms(shader, prog_t):
    vp = virus_params(prog_t)
    sc = VIRUS_SCALE_F2
    br, bg, bb = vp["body_rgb"]
    sr, sg, sb = vp["spike_rgb"]
    shader.setUniform("uVirusR",        float(vp["virus_r"]   / sc))
    shader.setUniform("uVirusNSpikes",  float(vp["n_spikes"]))
    shader.setUniform("uVirusSpikeLen", float(vp["spike_len"] / sc))
    shader.setUniform("uVirusSpikeW",   float(vp["spike_w"]   / sc))
    shader.setUniform("uVirusBodyCol",  _to_js([br/255.0, bg/255.0, bb/255.0]))
    shader.setUniform("uVirusSpikeCol", _to_js([sr/255.0, sg/255.0, sb/255.0]))
    
    # Buffer para armazenar as últimas teclas digitadas
cheat_buffer = ""

def keyTyped():
    """Função nativa do p5.js que detecta teclas imprimíveis digitadas"""
    global cheat_buffer, state, timer_total
    
    # Só queremos ouvir o cheat code se o jogador estiver em uma fase ativa
    if state in ("fase1", "fase2"):
        # Adiciona a tecla digitada (em minúsculo) ao buffer
        cheat_buffer += str(P5.key).lower()
        
        # Mantém apenas as últimas 10 letras no buffer
        if len(cheat_buffer) > 10:
            cheat_buffer = cheat_buffer[-10:]
            
        # Verifica se o código secreto "vasco" foi digitado
        if "vasco" in cheat_buffer:
            if state == "fase1":
                # Se estiver na Fase 1, pula para a Fase 2
                reset_fase_2()
            
            elif state == "fase2":
                # Se estiver na Fase 2, força a vitória
                timer_total = timers["fase1"] + timers["fase2"]
                state = "win_f2"
                
            # Limpa o buffer após o código funcionar
            cheat_buffer = ""