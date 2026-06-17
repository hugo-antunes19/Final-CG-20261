# ===========================================================================
#  RETROVÍRUS  -  Computação Gráfica
#  Py5Script (PyScript + p5.js)  -  WEBGL + Shader GLSL (Raymarching SDF)
# ---------------------------------------------------------------------------
#  Fase 1: Túnel Epitelial — desvie dos cílios (Bézier 3D), infecte células
#  Fase 2: Tubo Sanguíneo  — endless runner com raymarching SDF
#  Fase 3: Cérebro - sistema nervoso sendo colonizado pelo vírus
#  Fase 4: ?
#
#  Controles: SETAS / WASD = mover   |   ESPAÇO = começar / reiniciar
# ===========================================================================

# ===========================================================================
# TODOs Gerais
# TODO: Corrigir colisão entre vírus e cílios, a hitbox parece estar inadequada
# TODO: Adicionar 'meleca' na Fase 1 para ser mais realista
# TODO: Adicionar animações sanguíneas para simular a corrente sanguínea na Fase 2
# TODO: Adicionar 'modo' desenvolvedor para controlarmos o vírus por completo para testar as fases (encostar nos obstáculos ou passar perto)
# TODO: Adicionar som que altera de fase em fase
# TODO: Implementar Fase 3
# TODO: Adicionar transição de tela entre fases mais complexa
# TODO: Otimização do código e eventuais problemas de renderização (bugs/travamentos)
# TODO: Melhorar documentação no repositório
# TODO: Testar em diferentes ambientes (computadores)
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
#  Constantes Fase 1 — Túnel Epitelial
# ---------------------------------------------------------------------------
TUNNEL_RADIUS    = 220.0    # Raio do cilindro do túnel (pixels)
SHIP_RADIUS_F1   = 12.0     # Raio da hitbox do vírus na Fase 1 (pixels)
MOVE_SPEED_F1    = 6.0      # Velocidade lateral do vírus (pixels/frame)
FWD_SPEED_F1     = 5.5      # Velocidade de avanço/recuo no eixo Z (pixels/frame)

CELL_RADIUS      = 22.0     # Raio visual da esfera de cada célula
CELL_COL_DIST    = SHIP_RADIUS_F1 + CELL_RADIUS  # Distância de colisão vírus↔célula

VIEW_DIST        = 1200.0   # Distância máxima de renderização à frente da câmera
SEED             = 42       # Semente global para geração procedural determinística

CILIO_RADIUS_COL = 14.0     # Raio de colisão da ponta do cílio

# ---------------------------------------------------------------------------
#  Constantes Fase 2 — Corrente Sanguínea (Raymarching SDF)
#  A Fase 2 é renderizada inteiramente por um fragment shader GLSL.
#  As unidades são diferentes da Fase 1 (escala ~40x menor).
# ---------------------------------------------------------------------------
MAX_OBS        = 8          # Máximo de obstáculos simultâneos enviados ao shader
TUNNEL_HALF    = 6.0        # Meio-raio do vaso sanguíneo (unidades do shader)
SHIP_RADIUS_F2 = 0.55       # Raio do vírus na Fase 2 (= VIRUS_R no shader)
SPACING        = 16.0       # Distância em Z entre obstáculos consecutivos
OB_START       = 28.0       # Posição Z do primeiro obstáculo
RIDGE_MOD      = 64.0       # Módulo para wrap de Z (evita perda de precisão float)

# ---------------------------------------------------------------------------
#  Constantes do Vírus — fonte da verdade compartilhada entre fases
#
#  Fase 1 usa diretamente em pixels (escala p5.js).
#  Fase 2 converte para unidades do shader dividindo por VIRUS_SCALE_F2.
#  Dessa forma, virus_params() é chamado igual nas duas fases e o visual
#  é idêntico: mesmos espinhos, mesma progressão de cor, mesmo halo.
# ---------------------------------------------------------------------------
VIRUS_SCALE_F2   = 40.0   # 1 unidade shader ≈ 22 pixels da Fase 1
VIRUS_R_BASE     = 12.0   # Raio inicial (pixels F1 / unidades * VIRUS_SCALE_F2 = F2)
VIRUS_R_MAX_MULT = 1.55   # Multiplicador máximo ao completar a Fase 1
VIRUS_SPIKES_MIN = 3      # Espinhos no início
VIRUS_SPIKES_MAX = 10     # Espinhos ao completar a Fase 1

# ---------------------------------------------------------------------------
#  Sistema de Dificuldade — Presets configuráveis
#  Para criar um novo nível: insira uma entrada no dicionário.
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
            "cilios_ring": 6, "cilio_spc":  80.0, "cilio_max_len": 150.0, "cell_spacing": 250.0, "pontos": 7
            },
        "fase2": {
            "speed_ini": 24.0
            }},
}

# ---------------------------------------------------------------------------
#  Conteúdo do Tutorial — slides navegáveis com ← →
#  Chaves: titulo (str), corpo (list[str]), dica (str)
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
            "  > Sobreviva o maximo possivel!",
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
  // z=0.9999 => quad encostado no far plane (depth ~0.99995). O HUD desenhado
  // depois (profundidade menor) passa GL_LESS e fica por cima — mesma situação
  // dos menus, onde o depth está limpo em ~1.0. Feito no VERT (e não com
  // gl_FragDepth) para não depender da extensão GL_EXT_frag_depth.
  gl_Position = vec4(p.xy, 0.9999, 1.0);
}
"""

# ---------------------------------------------------------------------------
#  FRAGMENT SHADER — Raymarching SDF da Fase 2
#
#  Técnica: para cada pixel, lança um raio da câmera e avança em passos
#  proporcionais à menor distância até qualquer superfície (SDF). Quando
#  a distância é < 0.002, considera "hit" e calcula iluminação.
#
#  Materiais: 0=túnel, 1=hemácia, 2=glóbulo branco, 3=vírus
#  SDFs biológicas: hemácia = torus+disco, glóbulo = smooth union de esferas
#
#  Ver DOCUMENTACAO.md para explicação detalhada de cada função.
# ---------------------------------------------------------------------------
FRAG = """
precision highp float;
#define MAX_OBS 8

#define TUNNEL_BEAT_AMP 0.24   // quanto a parede afunila no batimento (unidades do shader)
#define TUNNEL_BEAT_LAG 0.05   // atraso por unidade de z -> onda longa (respira sem sulco)

// Batimento GLOBAL de tela (sincronizado com o lub-dub) — torna o coração legível
#define BEAT_ZOOM      0.12    // empurrão de zoom da câmera a cada batida
#define BEAT_EXPOSURE  0.16    // brilho global some/volta no batimento
#define BEAT_REDDEN    0.06    // realce avermelhado no batimento
#define VIGN_BASE      0.16    // vinheta de borda constante (enquadra o vaso)
#define VIGN_BEAT      0.55    // vinheta extra que pulsa nas bordas no batimento

// ===========================================================================
//  VARIÁVEIS UNIFORMS (Inputs enviados pela aplicação Python/p5.js)
// ===========================================================================
uniform vec2  uResolution;     // Resolução da tela (largura, altura) em pixels
uniform float uTime;           // Tempo decorrido (em segundos) usado para animações
uniform float uCamZ;           // Avanço da câmera no eixo Z (aplicado módulo RIDGE_MOD)
uniform vec2  uPlayer;         // Deslocamento lateral (X, Y) do vírus controlado pelo jogador
uniform int   uObCount;        // Número atual de obstáculos ativos na cena (máximo MAX_OBS)
uniform vec3  uObRel[MAX_OBS];// Posição tridimensional (X, Y, Z) de cada obstáculo relativa à câmera
uniform float uObRad[MAX_OBS]; // Raio (escala de tamanho) de cada obstáculo individual
uniform float uObType[MAX_OBS];// Tipo do obstáculo (usado para diferenciar hemácia/glóbulo e definir rotação)
uniform float uHit;            // Fator de colisão (1.0 quando o jogador colide, decai para 0.0 com o tempo)

// --- Uniforms do Vírus (calculados por virus_params() em Python) ---
// Todos em unidades do shader (divididos por VIRUS_SCALE_F2 no Python)
uniform float uVirusR;          // Raio do corpo
uniform float uVirusNSpikes;    // Número de espinhos (float para o GLSL aceitar)
uniform float uVirusSpikeLen;   // Comprimento da haste
uniform float uVirusSpikeW;     // Raio do bulbo na ponta
uniform vec3  uVirusBodyCol;    // Cor do corpo (0..1)
uniform vec3  uVirusSpikeCol;   // Cor da ponta dos espinhos (0..1)

// LOD dos glóbulos brancos (opcional — controlado pelo jogador na Fase 2)
uniform float uLodEnable;       // 0 = qualidade máxima, 1 = LOD ativo
uniform float uLodStrength;     // 0..1 — intensidade do LOD quando ativo
uniform float uHeartHz;         // Frequência cardíaca atual (Hz)
uniform float uPulsePhase;      // Fase acumulada do pulso (radianos)

// ===========================================================================
//  SDFs PRIMITIVAS (Signed Distance Fields - Campos de Distância com Sinal)
//  Retornam a distância de um ponto 'p' até a superfície do objeto.
//  Se a distância for negativa, o ponto está dentro do objeto.
// ===========================================================================

// SDF de uma Esfera: calcula a distância de um ponto 'p' (coordenadas X, Y, Z no espaço local do objeto) até a origem (0, 0, 0), subtraindo o raio 'r'
float sdSphere(vec3 p, float r){ 
  return length(p) - r; 
}

// SDF de uma Caixa (Box): calcula o vetor de distância para as faces externas e internas
float sdBox(vec3 p, vec3 b){
  vec3 q = abs(p) - b;
  return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

// SDF de um Toro (Torus): rotaciona uma seção circular 2D (raio menor 't.y') 
// a uma distância 't.x' do eixo vertical central.
float sdTorus(vec3 p, vec2 t){
  vec2 q = vec2(length(p.xz) - t.x, p.y);
  return length(q) - t.y;
}

// ===========================================================================
//  FUNÇÕES UTILITÁRIAS E OPERADORES DE SDF
// ===========================================================================

// Matriz de Rotação 2D: rotaciona um vetor bidimensional por um ângulo 'a'
mat2 rot(float a){ 
  float c = cos(a), s = sin(a); 
  return mat2(c, -s, s, c); 
}

// hash1 — PRNG determinístico via LCG (gerador congruencial linear),
// o mesmo algoritmo clássico de rand()/minstd (C, Java, ...):
//   X_{n+1} = (a * X_n + c) mod m
// Constantes a=75, c=74, m=65537 (LCG do ZX Spectrum) mantêm todo produto
// abaixo de 2^24, garantindo aritmética inteira EXATA em highp float — um
// módulo estilo 2^31 perderia precisão no produto a*X. Retorna 0..1.
float hash1(float n){
  float s = mod(floor(abs(n) * 100.0), 65537.0) + 1.0; // semente inteira 1..65537
  s = mod(75.0 * s + 74.0, 65537.0);                   // 3 iterações do LCG
  s = mod(75.0 * s + 74.0, 65537.0);                   // melhoram a difusão (avalanche)
  s = mod(75.0 * s + 74.0, 65537.0);
  return s / 65537.0;
}

// SDF de uma Cápsula: cilindro com extremos arredondados
// entre os pontos 'a' e 'b'. Usada nas microvilosidades dos glóbulos brancos.
float sdCapsule(vec3 p, vec3 a, vec3 b, float r){
  vec3 pa = p - a, ba = b - a;
  // p relativo a 'a'; eixo do segmento
  float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  // projeta p no segmento [0,1]
  return length(pa - ba * h) - r;
  // distância ao eixo, menos raio
}
// Smooth Minimum (smin): fusão orgânica entre duas distâncias.
// O parâmetro 'k' controla a suavidade da transição/fusão.
// Retorna a menor distância, suavizando a quina de junção.
float smin(float a, float b, float k){
  float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0); // Percentual de mistura entre a e b, de 0 a 1
  return mix(b, a, h) - k * h * (1.0 - h); // Interpolação entre a e b, de 0 a 1, com a suavidade controlada por k
}

// ===========================================================================
//  SDFs BIOLÓGICAS (Modelos de células e vírus)
// ===========================================================================

// SDF de uma Hemácia: modelada como um disco bicôncavo
// Criada através da união/mínimo entre:
// 1. Um Toro externo que forma a borda arredondada e espessa
// 2. Um cilindro muito fino (disco) posicionado no centro do toro
float sdHemacia(vec3 p, float r){
  // Disco bicôncavo: centro fino + borda arredondada (anel)
  float disc = max(abs(p.y) - r * 0.09, length(p.xz) - r * 0.52);
  vec2 q = vec2(length(p.xz) - r * 0.52, p.y);
  float edge  = length(q) - r * 0.28;
  return min(disc, edge);
}

// Glóbulo branco: esfera + microvilosidades. LOD opcional (uLodEnable / uLodStrength).
#define N_MICRO_MAX 24 // TODO: Alocar para o local do código apropriado
// TODO: Adicionar uma função para gerar o número de microvilosidades com base no LOD

float sdGlobuloBranco(vec3 p, float r, float seed, float lod){
  float d = sdSphere(p, r * 0.68);
  float lp = length(p);
  float lodMix = uLodEnable * uLodStrength;

  // Saídas antecipadas para melhorar performance
  // Se o ponto estiver dentro da esfera principal, retorna a distância
  if(lp < r * 0.52) return d;
  // Se o LOD estiver ativo e a distância for menor que 0.08, retorna a distância
  if(lodMix > 0.001 && lod < 0.08) return d;
  // Se o ponto estiver fora da esfera principal, retorna a distância
  if(lp > r * 1.08) return d;

  // Interpolação entre 1.0 (qualidade máxima) e smoothstep(0.12, 0.82, lod)
  float hairT = mix(1.0, smoothstep(0.12, 0.82, lod), lodMix);
  // Interpolação entre N_MICRO_MAX e mix(5.0, float(N_MICRO_MAX), hairT)
  int nHair = int(mix(float(N_MICRO_MAX), mix(5.0, float(N_MICRO_MAX), hairT), lodMix));

  for(int i = 0; i < N_MICRO_MAX; i++){
    if(i >= nHair) break;

    float fi = float(i);
    // Distribuição Fibonacci na esfera de forma uniforme
    float y = 1.0 - (fi + 0.5) * (2.0 / float(N_MICRO_MAX));
    float w = sqrt(max(0.0, 1.0 - y * y));
    float theta = fi * 2.399963 + seed * 1.37;
    // Variação aleatória para a direção da cápsula (pêlos curtos na superfície)
    float h0 = hash1(seed + fi * 19.17);
    float h1 = hash1(seed + fi * 41.23);
    // Normalização da direção da cápsula
    vec3 dir = normalize(vec3(cos(theta) * w, y, sin(theta) * w)
      + (vec3(h0, h1, fract(h0 + h1)) - 0.5) * 0.22);

    float surf = r * (0.66 + 0.05 * fract(h0 * 7.1));
    // Comprimento da cápsula (pêlos curtos na superfície)
    float hLen = r * (0.09 + 0.06 * fract(h1 * 11.3));
    // Raio da cápsula (pêlos curtos na superfície)
    float hRad = r * (0.030 + 0.018 * fract(h0 * 13.7));
    // Ponto base da cápsula
    vec3 base = dir * surf;
    // Distância entre o ponto base e o ponto final da cápsula
    d = min(d, sdCapsule(p, base, base + dir * hLen, hRad));
  }
  return d;
}

// Renderizador de Obstáculo Genérico:
// 1. Desloca o ponto de amostragem para a coordenada local do obstáculo (p - center)
// 2. Aplica uma rotação contínua nos eixos XY e XZ baseada no tempo e na ID única (typ)
// 3. Escolhe a geometria correta baseada no tipo (typ < 3.14 representa hemácia)
float obstacleSDF(vec3 p, vec3 center, float r, float typ){
  vec3 rp = p - center;
  float ph = typ + uTime * 0.7;
  if(typ < 3.14){
    // Hemácia: rotação suave (evita disco virar "linha" ou formas quebradas)
    rp.xz = rot(ph * 0.22) * rp.xz;
    rp.yz = rot(ph * 0.14) * rp.yz;
    return sdHemacia(rp, r);
  }
  rp.xy = rot(ph * 0.4) * rp.xy;
  rp.xz = rot(ph * 0.3) * rp.xz;
  float lod = clamp(1.0 - center.z / 65.0, 0.0, 1.0);
  return sdGlobuloBranco(rp, r * 1.2, typ, lod);
}

// Protótipo: heartPulse é definido mais abaixo, mas tunnelSDF já o usa.
float heartPulse(float phase);

// SDF do Túnel (Vaso Sanguíneo):
// Representado por um cilindro infinito ao longo do eixo Z.
// É deslocado pelas coordenadas do jogador (uPlayer.x, uPlayer.y), fazendo com que
// o jogador pareça se mover para as laterais ao desviar dos obstáculos.
float tunnelSDF(vec3 p){
  float wx = p.x + uPlayer.x;
  float wy = p.y + uPlayer.y;
  float wz = p.z + uCamZ;

  // Raio do vaso pulsando: sístole afunila a parede, diástole relaxa de volta.
  // O atraso em wz faz a constrição VIAJAR ao longo do eixo (onda de pressão),
  // coincidindo com o pulso de brilho de tunnelColor.
  float beat = heartPulse(uPulsePhase - wz * TUNNEL_BEAT_LAG);
  float r    = TUNNEL_HALF - TUNNEL_BEAT_AMP * beat;

  // Distância invertida: quanto mais perto do raio interno, menor a distância.
  // Fator < 1: o raio varia ao longo de z, então encolhemos um pouco o passo do
  // sphere-tracing para evitar overshoot/artefatos na parede.
  return (r - length(vec2(wx, wy))) * 0.9;
}

// SDF do Vírus (Jogador na Fase 2):
// Modelado para corresponder visualmente à Fase 1 evolucionária final (esfera central + 8 espinhos).
// Fica posicionado em Z fixo (VIRUS_Z = 8.0) à frente da câmera.


// ===========================================================================
//  SDF DO VÍRUS — Coroa + Halo
//
//  Replica exatamente o draw_virus_f1 do Python:
//    - Corpo esférico central
//    - N espinhos distribuídos em anel no plano XY com cos/sin
//    - Cada espinho tem haste (cápsula) + bulbo esférico na ponta
//    - Rotação lenta do anel inteiro (t * 0.12), sway individual
//
//  uVirusNSpikes é float; fazemos loop até MAX_SPIKES e descartamos
//  índices >= uVirusNSpikes (GLSL não aceita loop com bound dinâmico).
// ===========================================================================

// TODO: O vírus está feio, pensar em como melhorar o virus visualmente, talvez usando uma geometria mais complexa ou adicionando um efeito de brilho/halo para destacar o jogador
// Talvez o virus nao devesse rodar totalmente, apenas no plano xy 
 
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

// ===========================================================================
//  COR DO VÍRUS — distingue corpo, haste e bulbo pelo gradiente de distância
//
//  Como o raymarcher só sabe que bateu no vírus (mat == 3), usamos a
//  distância até o centro para separar corpo (perto) de espinhos (longe).
// ===========================================================================
vec3 virusColor(vec3 p, vec3 n, float dif, float amb, float fre){
  vec3 vp  = p - vec3(0.0, 0.0, VIRUS_Z);
  // Normalized dist from center: 0 = centro do corpo, 1 = ponta do espinho
  float distN = clamp((length(vp) - uVirusR) / uVirusSpikeLen, 0.0, 1.0);
  vec3 base   = mix(uVirusBodyCol, uVirusSpikeCol, distN);
  vec3 col    = base * (amb + dif * 0.9) + fre * uVirusSpikeCol * 0.5;
  return col;
}

// ===========================================================================
//  MAPEAMENTO DA CENA E CÁLCULO DE INTERSEÇÃO (RAYMARCHING)
// ===========================================================================

// mapScene: Calcula a SDF global (menor distância) de toda a cena 3D e retorna
// a ID do material do objeto mais próximo (mat) para pintura e sombreamento posterior.
// Materiais: 0 = túnel, 1 = hemácia, 2 = glóbulo branco, 3 = vírus do jogador
float mapScene(vec3 p, out float mat){
  // 1. Inicializa a cena com a distância até as paredes do túnel (material 0.0)
  float d = tunnelSDF(p);
  mat = 0.0;
  
  // 2. Compara com a SDF do vírus do jogador (material 3.0)
  float vd = sdVirus(p);
  if(vd < d){ d = vd; mat = 3.0; }
  
  // 3. Itera sobre todos os obstáculos ativos e encontra o que está mais próximo de 'p'
  for(int i = 0; i < MAX_OBS; i++){
    if(i >= uObCount) break;
    float od = obstacleSDF(p, uObRel[i], uObRad[i], uObType[i]);
    if(od < d){ 
      d = od; 
      // Distingue o material do obstáculo baseado em seu tipo arbitrário (representado por 3.14)
      mat = uObType[i] < 3.14 ? 1.0 : 2.0; 
    }
  }
  return d;
}

// mapDist: Retorna apenas a distância mínima (usado exclusivamente no cálculo da normal)
float mapDist(vec3 p){
  float m;
  return mapScene(p, m);
}

// calcNormal: Estima o vetor normal da superfície no ponto 'p' usando Diferenças Centrais.
// A normal é o gradiente da SDF, apontando na direção onde a distância cresce mais rapidamente.
vec3 calcNormal(vec3 p){
  vec2 e = vec2(0.0025, 0.0); // Epsilon pequeno para amostragem vizinha
  return normalize(vec3(
    mapDist(p + e.xyy) - mapDist(p - e.xyy),
    mapDist(p + e.yxy) - mapDist(p - e.yxy),
    mapDist(p + e.yyx) - mapDist(p - e.yyx)));
}

// thump: pulso percussivo nítido (gaussiana estreita) centrado em 'center'.
// Ataque/decaimento rápidos dão a sensação de "soco" do batimento, não de onda lenta.
float thump(float cyc, float center, float w){
  float d = cyc - center;
  return exp(-d * d / (w * w));
}

// heartPulse: ritmo cardíaco "lub-dub" (S1 + S2) seguido de diástole em repouso.
// Retorna um envelope 0..1:
//   - S1 ("lub"): contração ventricular, forte e curta
//   - S2 ("dub"): fechamento das válvulas semilunares, mais fraco, logo após
//   - resto do ciclo: diástole (parede relaxada, sem brilho)
float heartPulse(float phase){
  float cyc = fract(phase / 6.28318530718);
  float s1 = thump(cyc, 0.10, 0.052);          // "lub" — sístole
  float s2 = thump(cyc, 0.27, 0.048) * 0.55;   // "dub" — segundo som, mais fraco
  return clamp(s1 + s2, 0.0, 1.0);
}

// vnoise: ruído de valor 2D suave (interpolação cúbica de hash1).
// Base de textura orgânica usada pela parede do vaso.
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

// ===========================================================================
//  SOMBREAMENTO E PROCEDURAIS VISUAIS
// ===========================================================================
// tunnelColor: parede do vaso = mosaico endotelial + fluxo de plasma + pulso cardíaco
vec3 tunnelColor(vec3 p){
  // Coordenadas absolutas na parede do vaso (mundo)
  float wx = p.x + uPlayer.x;
  float wy = p.y + uPlayer.y;
  float wz = p.z + uCamZ;
  float ang = atan(wy, wx);

  // Tuning (estilo biomédico sutil)
  const float TISSUE_STRENGTH = 0.45; // peso do mosaico de tecido no mix de cor
  const float FLOW_STRENGTH   = 0.18; // peso das faixas de plasma escorrendo
  const float PULSE_STRENGTH  = 0.26; // brilho do batimento na parede (reforço; o global domina)

  // 1. Mosaico endotelial: grão fino de tecido (3 oitavas, alta frequência)
  float tissue = vnoise(vec2(ang * 11.0, wz * 2.4)) * 0.5
               + vnoise(vec2(ang * 23.0, wz * 5.2)) * 0.3
               + vnoise(vec2(ang * 47.0, wz * 10.5)) * 0.2;

  // 2. Fluxo laminar: faixas de plasma alongadas no sentido do vaso (advectadas em z)
  float flow = vnoise(vec2(ang * 8.0, wz * 0.12 - uTime * 0.6));

  // 3. Onda de pulso cardíaco viajando pelo eixo (atraso espacial em z e ângulo)
  float lag    = wz * 0.16 + ang * 0.22;
  float hrNorm = clamp((uHeartHz - 1.10) / 0.90, 0.0, 1.0);
  float pulse  = heartPulse(uPulsePhase - lag) * (0.85 + 0.15 * hrNorm);

  // Composição: variação fina e de baixo contraste em torno de uma cor base
  vec3 deep  = vec3(0.32, 0.050, 0.046); // tecido em sombra
  vec3 flesh = vec3(0.44, 0.078, 0.058); // tecido iluminado
  vec3 col   = mix(deep, flesh, clamp(tissue * TISSUE_STRENGTH + flow * FLOW_STRENGTH + 0.25, 0.0, 1.0));
  col += vec3(0.28, 0.06, 0.045) * (pulse * PULSE_STRENGTH);
  return col;
}

// ===========================================================================
//  PIXEL SHADER ENTRY POINT (Função Principal)
// ===========================================================================
void main(){
  // Normaliza as coordenadas da tela (UV de -0.5 a 0.5 no eixo menor)
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;

  // Batimento global na fase da câmera (sem atraso espacial): a tela inteira
  // pulsa em uníssono, que é o que faz o efeito "ler" como um coração.
  float beatCam = heartPulse(uPulsePhase);

  // Configuração da câmera virtual (Ray Generation)
  vec3 ro = vec3(0.0);                                    // Origem do raio (Ray Origin) na posição local da câmera
  vec3 rd = normalize(vec3(uv, 1.45 + BEAT_ZOOM * beatCam)); // z maior no batimento => leve "soco" de zoom

  float t = 0.0;        // Distância total percorrida pelo raio (Ray Marching Step)
  float mat = 0.0;      // Armazenará a ID do material atingido
  bool hit = false;     // Flag de colisão visual do raio
  
  //TODO: Checar o melhor numero de passos para o raymarching, talvez seja necessário aumentar ou diminuir 
  // Loop de Raymarching (Máximo de 90 passos para bom equilíbrio de desempenho)
  for(int i = 0; i < 90; i++){
    vec3 p = ro + rd * t;        // Posição atual da ponta do raio
    float d = mapScene(p, mat);  // Consulta a SDF da cena
    if(d < 0.002){               // Se a distância for quase zero, atingiu a superfície (HIT!)
      hit = true; 
      break; 
    }
    t += d;                      // Avança o raio com segurança pela distância informada pela SDF
    if(t > 170.0) break;         // Plano de corte distante (Far plane limit)
  }

  vec3 col;
  if(hit){
    vec3 p = ro + rd * t;        // Ponto tridimensional onde o raio tocou a superfície
    vec3 n = calcNormal(p);      // Vetor normal apontando para fora da superfície
    vec3 lig = normalize(vec3(0.4, 0.7, -0.5)); // Direção da fonte de luz direcional
    
    // Cálculo clássico de iluminação:
    float dif = clamp(dot(n, lig), 0.0, 1.0);  // Difuso de Lambert (Lambertian Diffuse)
    float amb = 0.25 + 0.25 * n.y;              // Luz ambiente direcional leve (sky/ground hemisférico)
    float fre = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 3.0); // Fresnel (brilho nas bordas de visão)

    // =======================================================================
    //  APLICAÇÃO DOS MATERIAIS
    // =======================================================================
    if(mat < 0.5){
      // MATERIAL 0: Paredes do Túnel (Vaso Sanguíneo)
      col = tunnelColor(p) * (amb + dif * 0.5);
    } else if(mat < 1.5){
      // MATERIAL 1: Hemácias
      vec3 oc = vec3(0.85, 0.12, 0.08); // Vermelho vivo
      // Subsurface Scattering (SSS): Simula a luz atravessando as bordas finas da hemácia
      float sss = pow(clamp(dot(rd, n), 0.0, 1.0), 2.0) * 0.3;
      col = oc * (amb + dif * 0.8 + sss) + fre * vec3(0.9, 0.2, 0.1);
    } else if(mat < 2.5){
      // MATERIAL 2: Glóbulos Brancos
      vec3 oc = vec3(0.86, 0.88, 0.91);
      float rim = pow(fre, 1.4);
      float lodMix = uLodEnable * uLodStrength;
      float tex = sin(p.x * 15.0 + p.y * 19.0) * sin(p.y * 17.0 + p.z * 21.0) * 0.5 + 0.5;
      float texAmt = lodMix * 0.10;
      col = oc * (1.0 - texAmt + texAmt * tex) * (amb + dif * 0.92) + rim * vec3(0.95, 0.97, 1.0) * 0.45;
    } else {
      // MATERIAL 3: Vírus (Jogador)
      col = virusColor(p, n, dif, amb, fre);
    }
    
    // Efeito de Névoa Volumétrica (Fog):
    // Conforme a distância 't' aumenta, mistura a cor do objeto com a profundidade
    // do vaso. O alvo é um vermelho-escuro de tecido (não preto), então a "garganta"
    // do vaso recua como uma penumbra avermelhada em vez de um halo preto.
    float fog = 1.0 - exp(-t * 0.022);
    col = mix(col, vec3(0.16, 0.025, 0.025), fog);
  } else {
    // Fundo: profundidade oculta do vaso (vermelho-escuro de tecido)
    col = vec3(0.16, 0.025, 0.025);
  }

  // Efeito de Flash Vermelho:
  // Quando colide com obstáculos, a tela pisca em vermelho de acordo com uHit
  col = mix(col, vec3(0.9, 0.05, 0.05), uHit * 0.6);

  // ---- Batimento cardíaco global (lub-dub) ----
  // A cada batida: o quadro clareia, ganha um realce avermelhado e as bordas
  // escurecem (vinheta pulsante), reproduzindo a sensação de pressão sanguínea.
  col *= 1.0 + BEAT_EXPOSURE * beatCam;
  col += vec3(BEAT_REDDEN, 0.0, 0.0) * beatCam;
  float r2 = dot(uv, uv);
  float vignette = 1.0 - VIGN_BASE * r2 - VIGN_BEAT * beatCam * r2;
  col *= clamp(vignette, 0.0, 1.0);

  // Correção Gamma: Converte a cor linear para espaço sRGB padrão de exibição
  col = pow(col, vec3(0.4545));   // 1.0 / 2.2 aprox.
  // Profundidade do quad é definida no vertex shader (z=0.999); o HUD fica por cima.
  gl_FragColor = vec4(col, 1.0);
}
"""
# Injeta a constante TUNNEL_HALF como literal no shader (GLSL não aceita variáveis Python)
FRAG = FRAG.replace("TUNNEL_HALF", "%.1f" % TUNNEL_HALF)

# ---------------------------------------------------------------------------
#  Cache Global dos Cílios
#
#  Os cílios são gerados proceduralmente, mas precisam manter estado entre
#  frames (posição, ângulo, física). O cache evita recriá-los a cada frame.
# ---------------------------------------------------------------------------
cilio_cache = {}   # Chave: (indice_anel, indice_cilio)
                   # Valor: (posicao_z, angulo, comprimento, fase_animacao)
cilio_nodes = {}   # Chave: (indice_anel, indice_cilio)
                   # Valor: lista de dicts com posição e velocidade de cada nó

# ---------------------------------------------------------------------------
#  get_cilio — Busca ou cria um cílio com distribuição espiral
# ---------------------------------------------------------------------------
def get_cilio(indice_anel, indice_cilio):
    """Retorna os dados geométricos de um cílio, criando-o se necessário.

    Os cílios são organizados em anéis ao longo do eixo Z do túnel.
    Cada anel tem eff_cilios_per_ring cílios distribuídos em 360°.
    Anéis consecutivos são girados 30° entre si (espiral), evitando
    que cílios de anéis vizinhos fiquem alinhados.

    Parâmetros:
        indice_anel   -- Qual anel no eixo Z (0, 1, 2, ...). Anel i
                         está na posição Z = i * eff_cilio_spacing.
        indice_cilio  -- Qual cílio dentro do anel (0 a eff_cilios_per_ring-1).
                         Cílio j fica no ângulo base = j/total * 360°.

    Retorna:
        (posicao_z, angulo, comprimento, fase_animacao)
    """
    key = (indice_anel, indice_cilio)
    if key not in cilio_cache:
        # Gerador local com seed determinística — mesmo anel/cílio = mesmo resultado
        rng    = random.Random((indice_anel * 997 + indice_cilio * 31 + SEED) & 0xFFFFFFFF)
        # Usa eff_cilio_spacing (sobrescrita pela dificuldade) em vez da constante fixa
        posicao_z = indice_anel * eff_cilio_spacing
        
        # Espaçamento espiral: cada anel é girado 30° em relação ao anterior.
        # Isso evita que cílios de anéis vizinhos se alinhem.
        giro_espiral = indice_anel * math.radians(30)
        
        # Ângulo final = posição base + giro espiral + ruído
        # Usa eff_cilios_per_ring para distribuição angular correta por dificuldade
        angulo = (indice_cilio / max(1, eff_cilios_per_ring)) * math.tau + giro_espiral + rng.uniform(-0.15, 0.15)
        
        comprimento = rng.uniform(eff_cilio_max_length * 0.5, eff_cilio_max_length)
        fase = rng.uniform(0, math.tau)
        cilio_cache[key] = (posicao_z, angulo, comprimento, fase)
    return cilio_cache[key]

# ---------------------------------------------------------------------------
#  collect_visible_cilios — Retorna cílios na janela de visibilidade
# ---------------------------------------------------------------------------
def collect_visible_cilios():
    """Coleta todos os cílios visíveis entre cam_z - 50 e cam_z + VIEW_DIST.

    Calcula os índices de anel correspondentes à janela de visibilidade
    e retorna uma lista de tuplas (chave, posicao_z, angulo, comprimento, fase).
    """
    z_inicio = cam_z_f1 - 50.0
    z_fim = cam_z_f1 + VIEW_DIST
    # Usa variáveis efetivas de dificuldade (eff_cilio_spacing, eff_cilios_per_ring)
    anel_inicio = max(0, int(z_inicio // eff_cilio_spacing))
    anel_fim = int(z_fim // eff_cilio_spacing) + 1
    return [
        (get_cilio(anel, cilio))
        for anel in range(anel_inicio, anel_fim)
        for cilio in range(eff_cilios_per_ring)
    ]

# ---------------------------------------------------------------------------
#  draw_cilio — Renderiza um cílio como curva de Bézier 3D e testa colisão
# ---------------------------------------------------------------------------
def draw_cilio( base_z, angle, length, phase, t):
    """Desenha um cílio e retorna True se colidiu com o vírus.

    Usa uma curva de Bézier cúbica com 4 pontos de controle:
      P0 (base na parede) → P1 (1/3) → P2 (2/3) → P3 (ponta)
    
    O efeito de chicote é criado por atraso de fase progressivo:
      P1 balança sem atraso, P2 com atraso de 1 rad, P3 com 2 rad.

    Parâmetros:
        base_z -- Posição Z da base do cílio no túnel
        angle  -- Ângulo em radianos da posição na parede (0 a 2π)
        length -- Comprimento do cílio (varia aleatoriamente)
        phase  -- Fase inicial da animação (evita sincronismo)
        t      -- Tempo atual em segundos

    Retorna:
        True se a ponta do cílio colidiu com o vírus.
    """
    # 1. Posição da base na parede do túnel
    bx  = math.cos(angle) * TUNNEL_RADIUS
    by  = math.sin(angle) * TUNNEL_RADIUS
    
    # 2. Vetores de Direção
    # Vetor apontando para o centro (crescimento normal do cílio)
    inx = -math.cos(angle)
    iny = -math.sin(angle)
    perp_x = -iny
    perp_y = inx

    freq = 1.2 
    
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

    # 5. Colisão (Checa se o vírus bateu em qualquer parte do chicote)
    dz  = base_z - cam_z_f1
    if abs(dz) < CILIO_RADIUS_COL + SHIP_RADIUS_F1:
        # A ponta do cílio é maior e mais perigosa
        tip_radius = CILIO_RADIUS_COL + SHIP_RADIUS_F1
        # O corpo do cílio (P1, P2) é fino, então a hitbox deve ser menor e mais justa
        body_radius = SHIP_RADIUS_F1 + 4.0
        
        # Verifica colisão com o corpo do cílio (P1, P2) com raio menor
        if math.hypot(p1x - px_f1, p1y - py_f1) < body_radius: return True
        if math.hypot(p2x - px_f1, p2y - py_f1) < body_radius: return True
        # Verifica colisão com a ponta (P3) com raio maior
        if math.hypot(p3x - px_f1, p3y - py_f1) < tip_radius: return True
    return False

# ---------------------------------------------------------------------------
#  Estado Global do Jogo
# ---------------------------------------------------------------------------
state = "menu"   # Estados: menu | tutorial | config | fase1 | fase2 | win | pausa | over

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
heart_hz_f2    = 1.25   # ~75 BPM inicial
pulse_phase_f2 = 0.0

# LOD glóbulos brancos (Fase 2) — opcional para o jogador
lod_enabled  = True    # L = ligar/desligar
lod_strength = 1.0     # [ / ] = intensidade 0..1 (só quando ligado)
prev_l       = False
prev_lbr     = False   # [
prev_rbr     = False   # ]

# ---------------------------------------------------------------------------
#  Configurações Mutáveis (persistem durante a sessão)
# ---------------------------------------------------------------------------
difficulty  = 1          # Índice do preset ativo em DIFFICULTY_PRESETS
config_sel  = 0          # Item selecionado na tela de config (0=dific., 1=LOD on/off, 2=LOD int.)

# ---------------------------------------------------------------------------
#  Timers por fase — dict extensível: adicione a chave ao criar nova fase
# ---------------------------------------------------------------------------
timers      = {"fase1": 0.0, "fase2": 0.0}   # Tempo acumulado em cada fase (s)
timer_total = 0.0                              # Soma dos timers no momento do game over

# ---------------------------------------------------------------------------
#  Navegação de Menus — edge detection independente por tecla
# ---------------------------------------------------------------------------
menu_sel      = 0            # Item selecionado no menu principal (0=Jogar, 1=Tutorial, 2=Config)
pausa_sel     = 0            # Item selecionado no menu de pausa (0=Retomar, 1=Reiniciar, 2=Menu)
tutorial_page = 0            # Página atual do tutorial (0-based)
prev_up       = False        # Edge detection: seta para cima
prev_down     = False        # Edge detection: seta para baixo
prev_left     = False        # Edge detection: seta para esquerda
prev_right    = False        # Edge detection: seta para direita
prev_enter    = False        # Edge detection: ENTER / ESPAÇO
prev_esc      = False        # Edge detection: ESC

# ---------------------------------------------------------------------------
#  Estado de Pausa
# ---------------------------------------------------------------------------
state_antes_pausa = None     # Estado salvo para retomar após pausa

# ---------------------------------------------------------------------------
#  Geração Procedural
#  Todas as funções usam random.Random(seed) local, garantindo que o
#  mesmo índice sempre gera o mesmo objeto (determinismo por seed).
# ---------------------------------------------------------------------------

def make_cell(indice_celula):
    """Gera posição de uma célula infectável dentro do túnel.

    Cada célula fica em uma posição polar aleatória (20% a 70% do raio
    do túnel), espaçada eff_cilio_spacing unidades no eixo Z.

    Retorna: (posicao_z, centro_x, centro_y)
    """
    rng = random.Random((indice_celula * 1234567 + SEED) & 0xFFFFFFFF)
    posicao_z = eff_cilio_spacing + indice_celula * eff_cilio_spacing
    raio_polar  = rng.uniform(TUNNEL_RADIUS * 0.20, TUNNEL_RADIUS * 0.70)
    angulo = rng.uniform(0, math.tau)
    return posicao_z, raio_polar * math.cos(angulo), raio_polar * math.sin(angulo)

def collect_visible_cells():
    """Retorna células visíveis e ainda não coletadas na janela de visibilidade."""
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

def make_obstacle(indice_obstaculo):
    """Gera um obstáculo da Fase 2 (hemácia ou glóbulo branco) com distribuição em anel.

    30% de chance de glóbulo branco (maior, typ >= 3.14).
    70% de chance de hemácia (menor, typ < 3.14).
    
    Posição distribuída em formato de "rosquinha" (donut). 
    As células nascem perto das bordas (30% a 92% do raio) para criar 
    um corredor de fuga estratégico no centro do vaso sanguíneo.

    O campo 'tipo' (typ) serve duplo propósito:
      - No shader: typ < 3.14 renderiza hemácia, >= 3.14 renderiza glóbulo.
      - Na colisão Python: não é usado diretamente.

    Retorna: (posicao_z, centro_x, centro_y, raio, tipo)
    """

    rng = random.Random((indice_obstaculo * 2654435761) & 0xFFFFFFFF)

    # 1. Definição do Tipo e Tamanho
    eh_globulo = rng.random() < 0.3
    if eh_globulo:
        raio = rng.uniform(2.5, 3.5)   # Glóbulos são maiores
    else:
        raio = rng.uniform(1.6, 2.8)   # Hemácias são menores
    
    # Margem de segurança para a célula não atravessar a parede do vaso
    limite = TUNNEL_HALF - raio - 0.4

    # 2. Posição Base: Distribuição em anel (sem a raiz quadrada)
    angulo_base = rng.uniform(0, math.tau)
    # Sorteia a distância do centro, forçando a nascer entre 30% e 92% do limite
    dist_centro = rng.uniform(limite * 0.3, limite * 0.92)  
    centro_x_base = math.cos(angulo_base) * dist_centro
    centro_y_base = math.sin(angulo_base) * dist_centro

    # 3. Drift Espacial: Cria uma curva sinuosa na base do obstáculo
    drift_amp = rng.uniform(0.8, 2.2)       # Força do desvio (amplitude)
    drift_freq = rng.uniform(0.06, 0.14)    # Quantas curvas faz ao longo do eixo Z
    drift_phase = rng.uniform(0, math.tau)  # Fase inicial aleatória
    
    # A direção do desvio é sempre 90 graus (pi/2) em relação ao centro,
    # fazendo a célula orbitar sutilmente a parede do túnel
    drift_ang = angulo_base + math.pi / 2   

    z_base = OB_START + indice_obstaculo * SPACING
    
    # Aplica o desvio espacial usando o Z como tempo
    drift = math.sin(z_base * drift_freq + drift_phase) * drift_amp
    centro_x = centro_x_base + math.cos(drift_ang) * drift
    centro_y = centro_y_base + math.sin(drift_ang) * drift

    # 4. Clipping de Segurança
    # Garante que, mesmo com o drift, o obstáculo nunca saia do vaso sanguíneo
    dist = math.hypot(centro_x, centro_y)
    if dist > limite:
        centro_x = centro_x / dist * limite
        centro_y = centro_y / dist * limite

    tipo = rng.uniform(3.15, 6.28) if eh_globulo else rng.uniform(0.0, 3.13)
    return z_base, centro_x, centro_y, raio, tipo

def collect_obstacles():
    """Coleta obstáculos visíveis, aplica animação de flutuação e formata para o shader.

    Retorna:
        posicoes_relativas -- Lista flat de [x, y, z] relativas à câmera (até MAX_OBS * 3)
        raios              -- Lista de raios (até MAX_OBS)
        tipos              -- Lista de tipos (até MAX_OBS)
        contagem           -- Quantidade real de obstáculos ativos na tela
    """

    indice_base = int((cam_z_f2 - OB_START) // SPACING)
    posicoes_relativas, raios, tipos = [], [], []
    contagem = 0
    n = max(0, indice_base - 1)
    while contagem < MAX_OBS and n < indice_base + MAX_OBS + 2:
        z, cx, cy, raio, tipo = make_obstacle(n)
        # Drift animado: oscilação adicional baseada no tempo 
        # (cam_z_f2 como um "relógio" para animar as células vindo na sua direção)
        rng2 = random.Random((n * 1234567 + 99) & 0xFFFFFFFF)
        anim_amp   = rng2.uniform(0.3, 0.9)     # O quanto ela treme
        anim_freq  = rng2.uniform(0.04, 0.10)   # O quão rápido ela treme
        anim_phase = rng2.uniform(0, math.tau)  # Deslocamento inicial da tremida
        anim_ang   = rng2.uniform(0, math.tau)  # Direção aleatória da tremida
        
        # O valor do seno sobe e desce com o avanço da câmera
        anim = math.sin(cam_z_f2 * anim_freq + anim_phase) * anim_amp
        cx += math.cos(anim_ang) * anim
        cy += math.sin(anim_ang) * anim

        # Distância Z relativa à câmera
        dist_z = z - cam_z_f2
        n += 1

        # Descarta obstáculos muito atrás da câmera (< -1.0) ou muito longe na névoa (> 150.0)
        if dist_z < -1.0 or dist_z > 150.0:
            continue

        posicoes_relativas.extend([cx - px_f2, cy - py_f2, dist_z])
        raios.append(raio)
        tipos.append(tipo)
        contagem += 1
    
    # Preenche slots vazios dos arrays com dados inertes 
    # (z=9999 garante que o obstáculo fique invisível no shader)
    while len(raios) < MAX_OBS:
        posicoes_relativas.extend([0.0, 0.0, 9999.0])
        raios.append(0.0)
        tipos.append(0.0)

    return posicoes_relativas, raios, tipos, contagem

# ---------------------------------------------------------------------------
#  Funções de Reset — Reinicializam o estado de cada fase
# ---------------------------------------------------------------------------

def reset_fase_1():
    """Reinicia a Fase 1: zera posição, pontos e limpa cache de cílios."""
    global cam_z_f1, px_f1, py_f1, pontos, collected_cells, state
    global cilio_cache, cilio_nodes, score

    apply_difficulty()        # Aplica preset de dificuldade
    cilio_cache.clear()       # Limpa cache para regenerar cílios (novo eff_cilio_spacing)
    cilio_nodes.clear()       # Limpa nós de física
    
    P5.camera()               # Restaura câmera padrão
    P5.perspective()          # Restaura projeção padrão

    cam_z_f1 = px_f1 = py_f1 = 0.0
    pontos = 0
    score = 0.0
    collected_cells = set()
    timers["fase1"] = 0.0     # Zera timer da Fase 1
    timers["fase2"] = 0.0     # Zera timer da Fase 2
    state = "fase1"

def reset_fase_2():
    """Reinicia a Fase 2: zera posição, velocidade e score."""
    global cam_z_f2, px_f2, py_f2, speed, score, hit_flash, state
    global heart_hz_f2, pulse_phase_f2

    apply_difficulty()       

    P5.camera()
    P5.perspective()

    cam_z_f2 = px_f2 = py_f2 = 0.0
    speed          = eff_speed_ini_f2   # Velocidade inicial pelo preset de dificuldade
    score          = hit_flash = 0.0
    heart_hz_f2    = 1.25
    pulse_phase_f2 = 0.0
    timers["fase2"] = 0.0    # Zera timer da Fase 2
    state = "fase2"

# ---------------------------------------------------------------------------
#  setup — Inicialização do p5.js (chamado 1x no início)
# ---------------------------------------------------------------------------

def setup():
    """Cria canvas WEBGL, compila o shader e inicializa o buffer de HUD."""
    global prog, hud, W, H, overlay_div
    P5.createCanvas(900, 600, P5.WEBGL)  # Canvas 3D com WebGL
    P5.pixelDensity(1)                    # 1 pixel real = 1 pixel do canvas
    W, H = P5.width, P5.height
    prog = P5.createShader(VERT, FRAG)    # Compila os shaders GLSL
    hud = P5.createGraphics(W, H)         # Buffer 2D para textos (HUD)
    
    # Abordagem alternativa para HUD Global (Placar HTML nativo imune ao WebGL)
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
        
        # Anexa diretamente ao body para posicionamento absoluto perfeito
        document.body.appendChild(overlay_div)
    except:
        pass

# ---------------------------------------------------------------------------
#  draw
# ---------------------------------------------------------------------------

def draw():
    P5.background(220, 180, 140)

    # Despacho por estado — para adicionar novo estado: inclua elif aqui e em _nav_action
    if   state == "menu":     draw_menu_principal()
    elif state == "tutorial": draw_tutorial()
    elif state == "config":   draw_config()
    elif state == "fase1":    push(); draw_fase_1(); pop()
    elif state == "fase2":    push(); draw_fase_2(); pop()
    elif state == "win":      draw_win_screen()
    elif state == "pausa":    draw_pausa()
    elif state == "over":     draw_game_over()

    handle_esc()        # ESC: pausa / retorno a menus
    handle_menu_nav()   # ↑↓←→ + ENTER: navegação em menus
    handle_lod()        # L / [ ]: controle de LOD durante Fase 2

    # Atualiza DOM overlay HUD (Pontuação Global e Timer)
    global overlay_div
    if 'overlay_div' in globals() and overlay_div:
        try:
            if state in ("fase1", "fase2", "pausa"):
                pt_total = int(pontos * 100 + score)
                tempo = _fmt_time(timers["fase1"] + timers["fase2"])
                overlay_div.innerHTML = f"<b>PONTUAÇÃO GLOBAL:</b> {pt_total}<br><br><b>TEMPO TOTAL:</b> {tempo}"
                overlay_div.style.display = "block"
                
                # Prende o overlay perfeitamente dentro do canto superior direito do canvas
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


# ---------------------------------------------------------------------------
#  handle_esc — pausa, retorno a menus (edge detection)
# ---------------------------------------------------------------------------

def handle_esc():
    """Gerencia a tecla ESC para pausa e retorno a menus."""
    global state, state_antes_pausa, pausa_sel, prev_esc
    esc   = P5.keyIsDown(27)
    esc_p = esc and not prev_esc

    if esc_p:
        if state in ("fase1", "fase2"):
            state_antes_pausa = state   # Salva o estado para retomar
            pausa_sel         = 0
            state             = "pausa"
        elif state == "pausa":
            state = state_antes_pausa   # Retoma de onde parou
        elif state in ("tutorial", "config", "win", "over"):
            state = "menu"

    prev_esc = esc


# ---------------------------------------------------------------------------
#  handle_menu_nav — navegação de menus com edge detection
# ---------------------------------------------------------------------------

def handle_menu_nav():
    """Gerencia navegação em todos os estados de menu (edge detection)."""
    global prev_up, prev_down, prev_left, prev_right, prev_enter

    up    = P5.keyIsDown(P5.UP_ARROW)
    down  = P5.keyIsDown(P5.DOWN_ARROW)
    left  = P5.keyIsDown(P5.LEFT_ARROW)
    right = P5.keyIsDown(P5.RIGHT_ARROW)
    enter = P5.keyIsDown(13) or P5.keyIsDown(32)   # ENTER ou ESPAÇO

    up_p    = up    and not prev_up
    down_p  = down  and not prev_down
    left_p  = left  and not prev_left
    right_p = right and not prev_right
    enter_p = enter and not prev_enter

    # Só despacha em estados de menu — estados de jogo gerenciam próprias teclas
    if state in ("menu", "tutorial", "config", "win", "over", "pausa"):
        _nav_action(up_p, down_p, left_p, right_p, enter_p)

    prev_up,    prev_down  = up,   down
    prev_left,  prev_right = left, right
    prev_enter = enter

# ---------------------------------------------------------------------------
#  handle_lod  — Fase 2: L = toggle, [ / ] = intensidade
# ---------------------------------------------------------------------------

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

# ==============================================================================
#  SISTEMA DE UI — Helpers, Dificuldade, Timer, Navegação e Telas
#  Estrutura modular: adicione novas telas seguindo o padrão existente.
# ==============================================================================

# ---------------------------------------------------------------------------
#  Helpers de HUD — compartilhados por todas as telas de UI
# ---------------------------------------------------------------------------

def _fmt_time(seconds):
    """Formata um tempo em segundos para a string 'M:SS'."""
    s = int(seconds)
    return "%d:%02d" % (s // 60, s % 60)

def _hud_setup():
    """Prepara o canvas WEBGL para renderização 2D via buffer HUD."""
    P5.resetShader()
    P5.camera()
    P5.perspective()

def _hud_stamp():
    """Carimba o buffer HUD na tela e restaura a projeção 3D."""
    P5.image(hud, -W / 2, -H / 2, W, H)
    P5.perspective(P5.PI / 3.6, float(W) / float(H), 1.0, 5000.0)

def _hud_panel(cx, cy, w, h, r=10):
    """Desenha um painel com fundo escuro e borda sutil no buffer HUD.

    Parâmetros:
        cx, cy -- centro do painel (pixels do HUD)
        w, h   -- largura e altura
        r      -- raio dos cantos arredondados
    """
    hud.fill(35, 12, 20, 225)
    hud.stroke(160, 70, 90, 160)
    hud.strokeWeight(1.5)
    hud.rect(cx - w / 2, cy - h / 2, w, h, r)
    hud.noStroke()

# ---------------------------------------------------------------------------
#  Sistema de Dificuldade e Timer
# ---------------------------------------------------------------------------

def apply_difficulty():
    """Aplica o preset de dificuldade selecionado nas variáveis efetivas.

    Lê DIFFICULTY_PRESETS[difficulty] e sobrescreve as variáveis eff_*.
    Chamada a cada reset de fase — não modifica as constantes originais.
    Para adicionar novo nível: inserir entrada em DIFFICULTY_PRESETS.
    """
    global eff_cilios_per_ring, eff_cilio_spacing, eff_cilio_max_length, eff_pontos_para_fase2, eff_speed_ini_f2
    p = DIFFICULTY_PRESETS[difficulty]
    eff_cilios_per_ring   = p["fase1"]["cilios_ring"]
    eff_cilio_spacing     = p["fase1"]["cilio_spc"]
    eff_cilio_max_length = p["fase1"]["cilio_max_len"]
    eff_pontos_para_fase2 = p["fase1"]["pontos"]
    eff_speed_ini_f2      = p["fase2"]["speed_ini"]


def update_timer(phase_key, dt):
    """Acumula delta time no timer da fase ativa.

    Parâmetros:
        phase_key -- chave no dict 'timers' (ex: "fase1", "fase2", "fase3")
        dt        -- delta time em segundos do frame atual
    Para adicionar nova fase: basta registrar a chave em 'timers' no estado global.
    """
    if phase_key in timers:
        timers[phase_key] += dt

# ---------------------------------------------------------------------------
#  Navegação Interna dos Menus
# ---------------------------------------------------------------------------

def _ir_para_tutorial():
    """Abre o tutorial resetando para o primeiro slide."""
    global state, tutorial_page
    tutorial_page = 0
    state = "tutorial"

def _ir_para_config():
    """Abre a tela de configurações resetando a seleção."""
    global state, config_sel
    config_sel = 0
    state = "config"

def _config_change_value(going_left):
    """Altera o valor do item selecionado na tela de configurações.

    Parâmetros:
        going_left -- True se ← foi pressionada, False se →
    """
    global difficulty, lod_enabled, lod_strength
    n_diff = len(DIFFICULTY_PRESETS)
    if config_sel == 0:        # Dificuldade
        step = -1 if going_left else 1
        difficulty = (difficulty + step) % n_diff
    elif config_sel == 1:      # LOD on/off
        lod_enabled = not lod_enabled
    elif config_sel == 2:      # LOD intensidade (só quando ativo)
        if lod_enabled:
            lod_strength = max(0.0, min(1.0, lod_strength + (-0.1 if going_left else 0.1)))

def _confirm_pausa():
    """Executa a ação selecionada no menu de pausa."""
    global state
    if pausa_sel == 0:          # Retomar
        state = state_antes_pausa
    elif pausa_sel == 1:        # Reiniciar fase
        if   state_antes_pausa == "fase1": reset_fase_1()
        elif state_antes_pausa == "fase2": reset_fase_2()
        else:                              state = state_antes_pausa
    elif pausa_sel == 2:        # Menu principal
        state = "menu"

def _nav_action(up_p, down_p, left_p, right_p, enter_p):
    """Despacha a ação de navegação para o estado de menu atual.

    Para adicionar suporte a novo estado de menu:
      1. Adicione um elif com a lógica de navegação desse estado.
      2. Adicione o estado à lista em handle_menu_nav().
    """
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

    elif state == "over":
        if enter_p: reset_fase_1()

    elif state == "pausa":
        PAUSA_COUNT = 3
        if up_p:   pausa_sel = (pausa_sel - 1) % PAUSA_COUNT
        if down_p: pausa_sel = (pausa_sel + 1) % PAUSA_COUNT
        if enter_p: _confirm_pausa()

# ---------------------------------------------------------------------------
#  Menu Principal — estado "menu"
# ---------------------------------------------------------------------------

def draw_menu_principal():
    """Tela de menu principal com logo animado, navegação e melhor pontuação."""
    _hud_setup()
    hud.clear()

    # Fundo escuro avermelhado
    hud.noStroke()
    hud.fill(15, 5, 10, 245)
    hud.rect(0, 0, W, H)

    cx = W / 2
    t  = P5.millis() / 1000.0
    pulse = 0.96 + 0.04 * math.sin(t * 1.8)

    hud.textAlign(P5.CENTER, P5.CENTER)

    # Título com sombra e pulso suave
    hud.fill(80, 10, 20, 180)
    hud.textSize(int(54 * pulse))
    hud.text("RETROVIRUS", cx + 2, H * 0.21 + 2)
    hud.fill(255, 80, 80)
    hud.textSize(int(54 * pulse))
    hud.text("RETROVIRUS", cx, H * 0.21)

    # Subtítulo
    hud.fill(200, 140, 140)
    hud.textSize(14)
    hud.text("Computacao Grafica — 2026/1", cx, H * 0.21 + 42)

    # Separador
    hud.stroke(150, 60, 70, 120)
    hud.strokeWeight(1)
    hud.line(cx - 120, H * 0.36, cx + 120, H * 0.36)
    hud.noStroke()

    # Itens do menu
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

    # Melhor pontuação histórica da sessão
    if best_f2 > 0 or best_f1 > 0:
        hud.fill(180, 140, 70, 210)
        hud.textSize(13)
        hud.text("Melhor — F1: %d cel   F2: %dm" % (best_f1, int(best_f2)), cx, H * 0.83)

    # Rodapé de navegação
    hud.fill(120, 85, 85, 200)
    hud.textSize(13)
    hud.text("↑ ↓  navegar   |   ENTER / ESPACO confirmar", cx, H - 16)

    hud.textAlign(P5.LEFT, P5.BASELINE)
    _hud_stamp()

# ---------------------------------------------------------------------------
#  Tutorial — estado "tutorial"
# ---------------------------------------------------------------------------

def draw_tutorial():
    """Exibe o tutorial em slides navegáveis com ← →.

    O conteúdo vem de TUTORIAL_SLIDES (definido nas constantes).
    Para adicionar slide de nova fase: inserir dict na lista.
    """
    _hud_setup()
    hud.clear()

    hud.noStroke()
    hud.fill(12, 5, 15, 248)
    hud.rect(0, 0, W, H)

    slide = TUTORIAL_SLIDES[tutorial_page]
    n     = len(TUTORIAL_SLIDES)
    cx, cy = W / 2, H / 2

    _hud_panel(cx, cy, 530, 350)

    # Título do slide
    hud.textAlign(P5.CENTER, P5.CENTER)
    hud.fill(255, 165, 80)
    hud.textSize(22)
    hud.text(slide["titulo"], cx, cy - 138)

    # Separador
    hud.stroke(200, 110, 60, 100)
    hud.strokeWeight(1)
    hud.line(cx - 210, cy - 116, cx + 210, cy - 116)
    hud.noStroke()

    # Corpo do slide (linhas do array)
    hud.fill(220, 205, 205)
    hud.textSize(15)
    for j, linha in enumerate(slide["corpo"]):
        hud.text(linha, cx, cy - 88 + j * 24)

    # Dica opcional
    if slide.get("dica"):
        hud.fill(140, 210, 130)
        hud.textSize(13)
        hud.text(slide["dica"], cx, cy + 112)

    # Indicador de página
    hud.fill(170, 130, 130)
    hud.textSize(13)
    hud.text("%d / %d" % (tutorial_page + 1, n), cx, cy + 135)

    # Botões de navegação lateral
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

# ---------------------------------------------------------------------------
#  Configurações — estado "config"
# ---------------------------------------------------------------------------

def draw_config():
    """Tela de configurações: dificuldade e LOD dos glóbulos brancos.

    Para adicionar nova configuração:
      1. Inserir entrada em CONFIG_ITEMS com (label, valor_str).
      2. Adicionar case em _config_change_value() com o índice correspondente.
      3. Incrementar CONFIG_COUNT em _nav_action() para "config".
    """
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

# ---------------------------------------------------------------------------
#  Tela de Vitória — estado "win"
# ---------------------------------------------------------------------------

def draw_win_screen():
    """Tela exibida ao completar a Fase 1, com resumo e instrução para avançar."""
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

# ---------------------------------------------------------------------------
#  Tela de Game Over — estado "over"
# ---------------------------------------------------------------------------

def draw_game_over():
    """Tela de game over com estatísticas completas da sessão."""
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

    # Melhor pontuação histórica da sessão
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

# ---------------------------------------------------------------------------
#  Overlay de Pausa — estado "pausa"
# ---------------------------------------------------------------------------

def draw_pausa():
    """Overlay de pausa com três opções: Retomar, Reiniciar, Menu."""
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

# ==============================================================================
#  FIM DO SISTEMA DE UI
# ==============================================================================

# ------------------------------------------------------------------------------
# Virus (Jogador)
# ------------------------------------------------------------------------------

def virus_params(prog_t):
    """Fonte única da verdade visual do vírus. Usada nas duas fases."""
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

# ---------------------------------------------------------------------------
#  Fase 1 — Túnel Epitelial 
# ---------------------------------------------------------------------------

def draw_fase_1():
    global cam_z_f1, px_f1, py_f1, pontos, best_f1, collected_cells, state
    global timer_total

    t  = P5.millis() / 1000.0
    dt = min(0.05, P5.deltaTime / 1000.0)
    update_timer("fase1", dt)   # Acumula tempo enquanto jogando

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

    # Posição da câmera
    P5.camera(px_f1, py_f1,        cam_z_f1 - 150.0,
              px_f1, py_f1,        cam_z_f1 + 300.0,
              0, 1, 0)
    P5.perspective(P5.PI / 3.6, float(W) / float(H), 1.0, 5000.0)

    # Luzes acompanham a câmera
    # 1. Luz ambiente cor de vinho 
    P5.ambientLight(115, 53, 68) 
    
    # 2. Luz principal (da frente): Branca levemente amarelada (brilho molhado)
    P5.pointLight(255, 230, 200, px_f1, py_f1, cam_z_f1 + 100) 
    
    # 3. Luz de preenchimento (trás): Rosa choque/vermelho para dar subsurface scattering
    P5.pointLight(255, 50, 80, px_f1, py_f1, cam_z_f1 - 100)

    draw_tunnel(t)

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

    #  Progressão visual (0.0 → 1.0 conforme células coletadas)
    prog_t = min(1.0, pontos / eff_pontos_para_fase2)   # usa preset de dificuldade

    draw_virus_f1(prog_t, t, px_f1, py_f1, cam_z_f1)

    draw_hud_f1_inline()

    if P5.keyIsDown(13):
        reset_fase_2()
        return

    if hit_cilio:
        timer_total = timers["fase1"]   # Congela total no momento do game over
        state = "over"
    elif pontos >= eff_pontos_para_fase2:
        state = "win"

def draw_virus_f1(prog_t, t, px, py, cam_z):
    """Desenha o vírus na Fase 1 usando p5.js WEBGL.

    Consome virus_params() diretamente — nenhum parâmetro visual
    é calculado aqui. Basta passar a posição do jogador.

    Parâmetros:
        prog_t    -- Progressão 0.0-1.0 (células coletadas / meta)
        t         -- Tempo em segundos (para animações de sway)
        px, py    -- Posição lateral do jogador no plano XY
        cam_z     -- Posição Z da câmera (usado para translate Z)
    """
    vp = virus_params(prog_t)

    virus_r    = vp["virus_r"]
    n_spikes   = vp["n_spikes"]
    spike_len  = vp["spike_len"]
    spike_w    = vp["spike_w"]
    br, bg, bb = vp["body_rgb"]
    sr, sg, sb = vp["spike_rgb"]

    P5.push()
    P5.translate(px, py, cam_z)

    # ------------------------------------------------------------------
    #  1. Espinhos curvos com receptor bulboso (coroa de proteínas)
    #     Desenhados ANTES do corpo para ficarem atrás dele quando
    #     o p5.js fizer a ordenação z-buffer.
    #     Como p5.js não tem quadraticCurveTo 3D, aproximamos a curva
    #     com dois segmentos de linha — suficiente para dar a curvatura.
    # ------------------------------------------------------------------
    P5.noFill()
    P5.strokeWeight(spike_w)

    for i in range(n_spikes):
        a_base = (i / n_spikes) * math.tau + t * 0.12   # rotação lenta da coroa
        sway   = math.sin(t * 1.8 + i * 0.9) * 0.18    # balanceio orgânico
        tip_a  = a_base + sway

        # Ponto de saída na superfície do corpo
        bx = math.cos(a_base) * virus_r * 0.88
        by = math.sin(a_base) * virus_r * 0.88

        # Ponto de controle intermediário (curva suave)
        mx = math.cos(a_base + sway * 0.5) * (virus_r + spike_len * 0.6)
        my = math.sin(a_base + sway * 0.5) * (virus_r + spike_len * 0.6)

        # Ponta da proteína
        tx = math.cos(tip_a) * (virus_r + spike_len)
        ty = math.sin(tip_a) * (virus_r + spike_len)

        # Segmento base → meio (cor do corpo)
        P5.stroke(br, bg, bb, 210)
        P5.line(bx, by, 0, mx, my, 0)

        # Segmento meio → ponta (cor da ponta, mais clara)
        P5.stroke(sr, sg, sb, 220)
        P5.line(mx, my, 0, tx, ty, 0)

        # Receptor bulboso esférico na ponta
        P5.noStroke()
        P5.fill(sr, sg, sb, 230)
        P5.push()
        P5.translate(tx, ty, 0)
        P5.sphere(spike_w * 1.15)
        P5.pop()

    # ------------------------------------------------------------------
    #  2. Corpo principal com especular simulado
    #     p5.js não expõe shading custom, então usamos duas esferas:
    #     - Corpo opaco com a cor principal
    #     - Esfera menor deslocada (highlight) para simular especular
    # ------------------------------------------------------------------
    P5.noStroke()

    # Corpo
    P5.fill(br, bg, bb)
    P5.sphere(virus_r)

    # Highlight especular (esfera branca translúcida deslocada para
    # cima-esquerda, imitando reflexo de luz direcional)
    spec_alpha = int(_lerp(128, 80, prog_t))   # some levemente ao evoluir
    P5.fill(255, 220, 230, spec_alpha)
    P5.push()
    P5.translate(-virus_r * 0.32, -virus_r * 0.38, virus_r * 0.2)
    P5.sphere(virus_r * 0.42)
    P5.pop()

    P5.pop()   # fecha o translate principal do vírus

def draw_tunnel(t):
    SEGS  = 32
    RINGS = 24
    STEP  = VIEW_DIST / RINGS

    for ri in range(RINGS):
        # z absoluto: estendido atrás da câmera para imersão total
        z1_local = cam_z_f1 - 200.0 + ri * STEP
        z2_local = cam_z_f1 - 200.0 + (ri + 1) * STEP

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

def draw_hud_f1_inline():
    # Limpa o buffer 2D
    hud.clear()

    # Fundo da caixa de HUD (canto superior esquerdo) — cor semi-transparente
    hud.noStroke()
    hud.fill(150, 100, 100, 180)
    hud.rectMode(P5.CORNER)
    hud.rect(10, 10, 220, 65, 8)

    # Barra de progresso (usa eff_pontos_para_fase2 pelo preset de dificuldade)
    bw = 190.0 * (pontos / eff_pontos_para_fase2)
    hud.fill(255, 220, 100)
    hud.rect(18, 38, bw, 14, 4)

    # Texto
    hud.textSize(14)
    hud.fill(255, 240, 150)
    hud.textAlign(P5.LEFT, P5.TOP)
    hud.text("CELULAS INFECTADAS", 20, 12)
    hud.fill(255, 240, 180)
    hud.text("%d / %d" % (pontos, eff_pontos_para_fase2), 20, 54)

    # Status global e Fase 1 (canto superior direito)
    hud.textAlign(P5.RIGHT, P5.TOP)
    
    hud.fill(150, 100, 100, 180)
    hud.rect(W - 170, 10, 160, 65, 8)

    hud.fill(200, 240, 200)
    hud.textSize(14)
    tempo_str = _fmt_time(timers["fase1"] + timers["fase2"])
    pontos_totais = pontos * 100 + int(score)
    hud.text("TEMPO TOTAL: %s" % tempo_str, W - 20, 20)
    hud.text("PONTUACAO: %d" % pontos_totais, W - 20, 44)

    hud.fill(200, 100, 120, 200)
    hud.textSize(13)
    hud.textAlign(P5.CENTER, P5.BOTTOM)
    hud.text("WASD / setas: mover  |  desvie dos cilios!", W / 2, H - 6)

    hud.textAlign(P5.LEFT, P5.BASELINE)

    # Carimba HUD sobre a cena 3D.
    # A Fase 1 usa perspectiva do jogo (near=1, far=5000): geometria tem depth ≈0.99.
    # O HUD com perspectiva padrão (near=52, far=5196) tem depth ≈0.909 < 0.99 → passa GL_LESS.
    # P5.image deve ser chamado DIRETAMENTE sem manipulação de drawingContext
    # (em Py5Script, drawingContext pode gerar exceção silenciosa e abortar a função.)
    P5.resetShader()
    P5.camera()
    P5.perspective()
    P5.fill(255, 255, 255, 255)
    P5.image(hud, -W / 2, -H / 2, W, H)

    # Restaura perspectiva 3D para o próximo frame
    P5.perspective(P5.PI / 3.6, float(W) / float(H), 1.0, 5000.0)

# ---------------------------------------------------------------------------
#  Fase 2 — Tubo Sanguíneo (shader raymarching)
# ---------------------------------------------------------------------------

def draw_fase_2():
    global cam_z_f2, px_f2, py_f2, speed, score, best_f2, hit_flash, state
    global heart_hz_f2, pulse_phase_f2, timer_total

    dt = min(0.05, P5.deltaTime / 1000.0)
    update_timer("fase2", dt)   # Acumula tempo enquanto jogando

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

    speed     = min(60.0, eff_speed_ini_f2 + cam_z_f2 * 0.02)   # velocidade pelo preset
    cam_z_f2 += speed * dt
    score     = cam_z_f2
    if score > best_f2:
        best_f2 = score

    # BPM adaptativo pela velocidade (66 -> 120 BPM) com suavização temporal.
    speed_t = (speed - 18.0) / (60.0 - 18.0)
    speed_t = max(0.0, min(1.0, speed_t))
    target_hz = _lerp(1.10, 2.00, speed_t)
    heart_hz_f2 = _lerp(heart_hz_f2, target_hz, min(1.0, dt * 2.3))
    pulse_phase_f2 = (pulse_phase_f2 + heart_hz_f2 * dt * math.tau) % math.tau

    # Posição real do vírus = camera + VIRUS_Z (8.0 do shader)
    virus_z = cam_z_f2 + 8.0
    base = int((virus_z - OB_START) // SPACING)
    for n in range(base - 2, base + MAX_OBS + 2):
        if n < 0: continue
        z, cx, cy, rad, _ = make_obstacle(n)
        dz = z - virus_z
        # Hitbox ajustada: hemácias são discos finos, glóbulos ~0.9r
        if abs(dz) < rad * 0.45:
            if math.hypot(cx - px_f2, cy - py_f2) < rad * 0.6 + SHIP_RADIUS_F2:
                timer_total = timers["fase1"] + timers["fase2"]  # Congela total
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
    set_virus_uniforms(prog, 1.0)
    P5.noStroke()              # Sem contorno: evita as bordas do quad virarem linhas no centro da tela
    P5.rect(0, 0, W, H)

    # HUD fase 2 via buffer 2D (necessário porque o shader ocupa tudo)
    draw_hud_f2()


def draw_hud_f2():
    global pontos, score, timers, best_f2, speed, heart_hz_f2, lod_enabled, lod_strength

    hud.clear()
    hud.textAlign(P5.LEFT, P5.TOP)
    hud.noStroke()

    try:
        hud.fill(20, 8, 10, 170)
        hud.rect(10, 12, 200, 72, 8)       # bloco esquerdo
        hud.rect(W - 152, 12, 142, 98, 8)  # bloco direito

        hud.fill(255, 210, 120)
        hud.textSize(16)
        pontos_totais = int(pontos * 100 + score)
        hud.text("PONTUACAO: %d" % pontos_totais, 18, 18)
        hud.text("DISTANCIA: %d m" % int(score), 18, 40)
        hud.text("RECORDE:   %d m" % int(best_f2), 18, 62)
        
        hud.text("VEL: %d" % int(speed), W - 144, 18)
        hud.text("BPM: %d" % int(heart_hz_f2 * 60.0), W - 144, 40)
        hud.text("TEMPO F2: %s" % _fmt_time(timers["fase2"]), W - 144, 62)
        
        hud.fill(200, 240, 200)
        tempo_str = _fmt_time(timers["fase1"] + timers["fase2"])
        hud.text("T. TOTAL: %s" % tempo_str, W - 144, 84)

        if lod_enabled:
            hud.fill(180, 220, 180)
            hud.textSize(14)
            hud.text("LOD: ON  %d%%" % int(lod_strength * 100), 16, H - 42)
            hud.fill(200, 180, 140)
            hud.textSize(12)
            hud.text("L = desligar  |  [ ] = intensidade", 16, H - 24)
        else:
            hud.fill(220, 180, 180)
            hud.textSize(14)
            hud.text("LOD: OFF (max)", 16, H - 32)
            hud.fill(200, 180, 140)
            hud.textSize(12)
            hud.text("L = ligar LOD", 16, H - 14)
            
    except Exception as e:
        hud.fill(255, 0, 0, 255)
        hud.textSize(20)
        hud.text("ERRO HUD: " + str(e), 20, 20)

    hud.textAlign(P5.LEFT, P5.BASELINE)

    # Carimba o HUD forçando a textura para contornar bugs do P5.image no WebGL
    P5.resetShader()
    P5.camera()
    P5.perspective()

    try:
        gl = P5.drawingContext
        gl.clear(256)      # DEPTH_BUFFER_BIT
        gl.disable(2929)   # DEPTH_TEST
    except:
        pass

    P5.noStroke()
    P5.fill(255, 255, 255, 255)
    P5.texture(hud)
    P5.rect(-W / 2, -H / 2, W, H)

    try:
        gl = P5.drawingContext
        gl.enable(2929)
    except:
        pass

    P5.perspective(P5.PI / 3.6, float(W) / float(H), 1.0, 5000.0)

def _lerp(a, b, x):
    return a + (b - a) * x
 
def set_virus_uniforms(shader, prog_t):
    """Passa os params do vírus ao shader, convertendo pixels → unidades shader."""
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

