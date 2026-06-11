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
# TODO: Adicionar dificuldade para acelerar a velocidade do vírus e a quantidade de obstáculos
# TODO: Adicionar 'meleca' na Fase 1 para ser mais realista
# TODO: Adicionar animações sanguíneas para simular a corrente sanguínea na Fase 2
# TODO: Melhorar os glóbulos brancos
# TODO: Adicionar 'modo' desenvolvedor para controlarmos o vírus por completo para testar as fases (encostar nos obstáculos ou passar perto)
# TODO: Adicionar pequeno tutorial no início do jogo, explicando como funciona cada fase e como jogar
# TODO: Adicionar pontuação e temporizador para todo início de jogo
# TODO: Adicionar som que altera de fase em fase
# TODO: Adicionar tela de game over com pontuação e tempo
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
#  O túnel é um cilindro de raio TUNNEL_RADIUS. O vírus (esfera de
#  SHIP_RADIUS_F1) se move dentro dele, desviando de cílios e coletando
#  células. Ao coletar PONTOS_PARA_FASE2 células, avança para a Fase 2.
# ---------------------------------------------------------------------------
TUNNEL_RADIUS    = 220.0    # Raio do cilindro do túnel (pixels)
SHIP_RADIUS_F1   = 18.0     # Raio da hitbox do vírus na Fase 1 (pixels)
SPEED_F1         = 3.5      # (não utilizado atualmente)
MOVE_SPEED_F1    = 6.0      # Velocidade lateral do vírus (pixels/frame)
FWD_SPEED_F1     = 5.5      # Velocidade de avanço/recuo no eixo Z (pixels/frame)

CELL_SPACING     = 250.0    # Distância em Z entre células infectáveis
CELL_RADIUS      = 22.0     # Raio visual da esfera de cada célula
CELL_COL_DIST    = SHIP_RADIUS_F1 + CELL_RADIUS  # Distância de colisão vírus↔célula

PONTOS_PARA_FASE2 = 5       # Células necessárias para completar a Fase 1
VIEW_DIST        = 1200.0   # Distância máxima de renderização à frente da câmera
SEED             = 42       # Semente global para geração procedural determinística

# ---------------------------------------------------------------------------
#  Constantes dos Cílios — Geometria e Física de Chicote
#  Cílios são curvas de Bézier 3D que nascem na parede do túnel.
#  São organizados em anéis ao longo do eixo Z, com distribuição espiral.
#  A animação usa um sistema spring-damper (mola + amortecimento).
# ---------------------------------------------------------------------------
CILIO_SPACING    = 120.0    # Distância em Z entre anéis de cílios
CILIOS_PER_RING  = 4        # Quantidade de cílios por anel (distribuídos em 360°)
CILIO_LEN        = 110.0    # Comprimento máximo de um cílio (varia aleatoriamente)
CILIO_RADIUS_COL = 14.0     # Raio de colisão da ponta do cílio

WHIP_SEGS  = 4              # Segmentos da cadeia spring-damper (nós de física)
WHIP_STIFF = 0.35           # Rigidez da mola (0=solto, 1=rígido)
WHIP_DAMP  = 0.87           # Amortecimento da velocidade (0=sem, 1=para imediato)
WHIP_FORCE = 0.5            # Amplitude máxima da força oscilatória na ponta
WHIP_FREQ  = 1.2            # Frequência do balançar (Hz)

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

// Smooth Minimum (smin): Interpolação orgânica (blending) entre duas distâncias 'a' e 'b'.
// O parâmetro 'k' controla a suavidade da transição/fusão.
// Retorna a menor distância, suavizando a quina de junção.
float smin(float a, float b, float k){
  float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
  return mix(b, a, h) - k * h * (1.0 - h);
}

// ===========================================================================
//  SDFs BIOLÓGICAS (Modelos de células e vírus)
// ===========================================================================

// SDF de uma Hemácia: modelada como um disco bicôncavo
// Criada através da união/mínimo entre:
// 1. Um Toro externo que forma a borda arredondada e espessa
// 2. Um cilindro muito fino (disco) posicionado no centro do toro
float sdHemacia(vec3 p, float r){
  // Borda externa (anel do toro)
  vec2 q = vec2(length(p.xz) - r * 0.55, p.y);
  float rim = length(q) - r * 0.3;
  // Centro fino (disco achatado no plano XZ delimitado pelo raio)
  float disc = max(abs(p.y) - r * 0.1, length(p.xz) - r * 0.55);
  // Retorna o menor valor entre a borda e o centro
  return min(rim, disc);
}

// SDF de um Glóbulo Branco: modelado como uma esfera deformada
// Usa a função 'smin' para fundir organicamente uma esfera central maior
// com 3 esferas menores projetadas para fora, simulando pseudópodes ativos
float sdGlobuloBranco(vec3 p, float r){
  float d = sdSphere(p, r * 0.75); // Núcleo principal
  float k = r * 0.25;              // Fator de suavização da fusão
  // Fusão com pseudópode 1 (diagonal superior frontal)
  d = smin(d, sdSphere(p - vec3(r*0.55, r*0.3, 0.0), r*0.35), k);
  // Fusão com pseudópode 2 (diagonal inferior traseira esquerda)
  d = smin(d, sdSphere(p - vec3(-r*0.3, -r*0.45, r*0.35), r*0.3), k);
  // Fusão com pseudópode 3 (diagonal superior esquerda)
  d = smin(d, sdSphere(p - vec3(0.1*r, r*0.35, -r*0.55), r*0.32), k);
  return d;
}

// Renderizador de Obstáculo Genérico:
// 1. Desloca o ponto de amostragem para a coordenada local do obstáculo (p - center)
// 2. Aplica uma rotação contínua nos eixos XY e XZ baseada no tempo e na ID única (typ)
// 3. Escolhe a geometria correta baseada no tipo (typ < 3.14 representa hemácia)
float obstacleSDF(vec3 p, vec3 center, float r, float typ){
  vec3 rp = p - center;
  float ph = typ + uTime * 0.3; // fase da rotação baseada no tempo
  rp.xy = rot(ph * 0.4) * rp.xy;
  rp.xz = rot(ph * 0.3) * rp.xz;
  if(typ < 3.14){
    return sdHemacia(rp, r);
  } else {
    return sdGlobuloBranco(rp, r * 1.2);
  }
}

// SDF do Túnel (Vaso Sanguíneo):
// Representado por um cilindro infinito ao longo do eixo Z.
// É deslocado pelas coordenadas do jogador (uPlayer.x, uPlayer.y), fazendo com que
// o jogador pareça se mover para as laterais ao desviar dos obstáculos.
float tunnelSDF(vec3 p){
  float wx = p.x + uPlayer.x;
  float wy = p.y + uPlayer.y;
  // Distância invertida: quanto mais perto do raio interno, menor a distância.
  // TUNNEL_HALF é o raio interno máximo do túnel.
  return TUNNEL_HALF - length(vec2(wx, wy));
}

// SDF do Vírus (Jogador na Fase 2):
// Modelado para corresponder visualmente à Fase 1 evolucionária final (esfera central + 8 espinhos).
// Fica posicionado em Z fixo (VIRUS_Z = 8.0) à frente da câmera.
#define VIRUS_Z  8.0
#define VIRUS_R  0.55
float sdVirus(vec3 p){
  // Desloca para a posição local do vírus (centralizado em X/Y e fixo em Z=8.0)
  vec3 vp = p - vec3(0.0, 0.0, VIRUS_Z);
  // Rotaciona lentamente o vírus para torná-lo vivo e dinâmico
  vp.xy = rot(uTime * 0.5) * vp.xy;
  vp.xz = rot(uTime * 0.3) * vp.xz;
  
  float d = sdSphere(vp, VIRUS_R); // Corpo esférico central
  float k = VIRUS_R * 0.1;         // Mistura suave para os espinhos parecerem brotar do corpo
  
  // 6 espinhos alinhados nos eixos principais (+X, -X, +Y, -Y, +Z, -Z)
  d = smin(d, sdSphere(vp - vec3( VIRUS_R*0.85, 0.0, 0.0), VIRUS_R*0.3), k);
  d = smin(d, sdSphere(vp - vec3(-VIRUS_R*0.85, 0.0, 0.0), VIRUS_R*0.3), k);
  d = smin(d, sdSphere(vp - vec3(0.0,  VIRUS_R*0.85, 0.0), VIRUS_R*0.3), k);
  d = smin(d, sdSphere(vp - vec3(0.0, -VIRUS_R*0.85, 0.0), VIRUS_R*0.3), k);
  d = smin(d, sdSphere(vp - vec3(0.0, 0.0,  VIRUS_R*0.85), VIRUS_R*0.3), k);
  d = smin(d, sdSphere(vp - vec3(0.0, 0.0, -VIRUS_R*0.85), VIRUS_R*0.3), k);
  
  // 2 espinhos adicionais nas diagonais para quebrar a simetria ortogonal pura
  d = smin(d, sdSphere(vp - vec3( VIRUS_R*0.6, VIRUS_R*0.6, 0.0), VIRUS_R*0.25), k);
  d = smin(d, sdSphere(vp - vec3(-VIRUS_R*0.6, 0.0, VIRUS_R*0.6), VIRUS_R*0.25), k);
  return d;
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
    if(i >= uObCount) break; // Sai do loop se atingir o total de obstáculos gerados
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

// ===========================================================================
//  SOMBREAMENTO E PROCEDURAIS VISUAIS
// ===========================================================================

// tunnelColor: Gera a textura e a iluminação pulsante do túnel epitelial
vec3 tunnelColor(vec3 p){
  // Coordenadas absolutas somando o deslocamento do jogador e avanço da câmera
  float wx = p.x + uPlayer.x;
  float wy = p.y + uPlayer.y;
  float wz = p.z + uCamZ;
  
  // Efeito de grade/sulcos procedurais na parede (estética de vasos biológicos)
  // gx e gy geram faixas transversais e longitudinais usando funções fract e smoothstep
  float gx = smoothstep(0.06, 0.0, abs(fract(wz * 0.18) - 0.5) - 0.44);
  float gy = smoothstep(0.06, 0.0, abs(fract(atan(wy, wx) * 1.27) - 0.5) - 0.44);
  
  vec3 base = vec3(0.35, 0.05, 0.05);  // Cor base: vermelho escuro vascular
  vec3 glow = vec3(0.5, 0.08, 0.05) * (gx + gy); // Emissão de luz avermelhada nos sulcos da grade
  
  // Pulso Cardíaco: Uma onda de luz senoidal que viaja no eixo Z oposto à câmera
  // Dá a sensação de que o coração está batendo e empurrando o sangue
  glow += vec3(0.6, 0.1, 0.05) * smoothstep(0.85, 1.0, sin(p.z * 0.12 - uTime * 4.0) * 0.5 + 0.5) * 0.6;
  return base + glow;
}

// ===========================================================================
//  PIXEL SHADER ENTRY POINT (Função Principal)
// ===========================================================================
void main(){
  // Normaliza as coordenadas da tela (UV de -0.5 a 0.5 no eixo menor)
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;

  // Configuração da câmera virtual (Ray Generation)
  vec3 ro = vec3(0.0);                          // Origem do raio (Ray Origin) na posição local da câmera
  vec3 rd = normalize(vec3(uv, 1.45));          // Direção do raio (Ray Direction) inclinando-se para o plano Z

  float t = 0.0;        // Distância total percorrida pelo raio (Ray Marching Step)
  float mat = 0.0;      // Armazenará a ID do material atingido
  bool hit = false;     // Flag de colisão visual do raio
  
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
      vec3 oc = vec3(0.9, 0.92, 0.95);  // Branco azulado translúcido
      col = oc * (amb + dif * 0.9) + fre * vec3(0.6, 0.7, 1.0); // Brilho azul de borda
    } else {
      // MATERIAL 3: Vírus (Jogador)
      vec3 body  = vec3(0.78, 0.08, 0.20); // Vermelho carmim fosco para o corpo
      vec3 spike = vec3(0.94, 0.20, 0.27); // Vermelho brilhante/rosa para os espinhos
      col = body * (amb + dif * 0.9) + fre * spike * 0.5; // Borda fresnel destaca os espinhos
    }
    
    // Efeito de Névoa Volumétrica (Fog):
    // Conforme a distância 't' aumenta, mistura a cor do objeto com o escuro de fundo
    // Simula a opacidade da corrente sanguínea cheia de plasma denso
    float fog = 1.0 - exp(-t * 0.022);
    col = mix(col, vec3(0.08, 0.01, 0.01), fog);
  } else {
    // Fundo escuro avermelhado (profundidade oculta do vaso onde o raio se perdeu)
    col = vec3(0.08, 0.01, 0.01);
  }

  // Efeito de Flash Vermelho:
  // Quando colide com obstáculos, a tela pisca em vermelho de acordo com uHit
  col = mix(col, vec3(0.9, 0.05, 0.05), uHit * 0.6);

  // Correção Gamma: Converte a cor linear para espaço sRGB padrão de exibição
  col = pow(col, vec3(0.4545));   // 1.0 / 2.2 aprox.
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
    Cada anel tem CILIOS_PER_RING cílios distribuídos em 360°.
    Anéis consecutivos são girados 30° entre si (espiral), evitando
    que cílios de anéis vizinhos fiquem alinhados.

    Parâmetros:
        indice_anel   -- Qual anel no eixo Z (0, 1, 2, ...). Anel i
                         está na posição Z = i * CILIO_SPACING.
        indice_cilio  -- Qual cílio dentro do anel (0 a CILIOS_PER_RING-1).
                         Cílio j fica no ângulo base = j/total * 360°.

    Retorna:
        (posicao_z, angulo, comprimento, fase_animacao)
    """
    key = (indice_anel, indice_cilio)
    if key not in cilio_cache:
        # Gerador local com seed determinística — mesmo anel/cílio = mesmo resultado
        rng    = random.Random((indice_anel * 997 + indice_cilio * 31 + SEED) & 0xFFFFFFFF)
        posicao_z = indice_anel * CILIO_SPACING
        
        # Espaçamento espiral: cada anel é girado 30° em relação ao anterior.
        # Isso evita que cílios de anéis vizinhos se alinhem.
        giro_espiral = indice_anel * math.radians(30)
        
        # Ângulo final = posição base (0°, 90°, 180°, 270°) + giro espiral + ruído
        angulo = (indice_cilio / CILIOS_PER_RING) * math.tau + giro_espiral + rng.uniform(-0.15, 0.15)
        
        comprimento = rng.uniform(CILIO_LEN * 0.5, CILIO_LEN)
        fase = rng.uniform(0, math.tau)
        cilio_cache[key] = (posicao_z, angulo, comprimento, fase)
    return cilio_cache[key]

# ---------------------------------------------------------------------------
#  init_cilio_nodes — Inicializa a cadeia de física spring-damper
# ---------------------------------------------------------------------------
def init_cilio_nodes(key, base_x, base_y, base_z, dir_x, dir_y, comprimento):
    """Cria os nós de física ao longo do cílio (da base à ponta).

    Cada nó tem posição atual (x, y), velocidade (vx, vy) e
    posição de repouso (rx, ry). O nó 0 é a raiz (fixa na parede).

    Parâmetros:
        key         -- Tupla (indice_anel, indice_cilio) para o cache
        base_x/y    -- Posição da base do cílio na parede do túnel
        base_z      -- Posição Z da base (não usado na física 2D)
        dir_x/y     -- Vetor unitário apontando da parede para o centro
        comprimento -- Comprimento total do cílio
    """
    seg = comprimento / WHIP_SEGS  # Distância entre nós consecutivos
    nodes = []
    for i in range(WHIP_SEGS + 1):
        nodes.append({
            'x':  base_x + dir_x * seg * i,   # Posição atual X
            'y':  base_y + dir_y * seg * i,   # Posição atual Y
            'vx': 0.0,                         # Velocidade X
            'vy': 0.0,                         # Velocidade Y
            'rx': base_x + dir_x * seg * i,   # Posição de repouso X
            'ry': base_y + dir_y * seg * i,   # Posição de repouso Y
        })
    cilio_nodes[key] = nodes

# ---------------------------------------------------------------------------
#  update_cilio_nodes — Simula a física de chicote (spring-damper)
#
#  Para cada nó (exceto a raiz fixa), aplica:
#    1. Força de mola: puxa o nó de volta à posição de repouso
#    2. Força oscilatória: empurra na direção perpendicular (balançar)
#    3. Amortecimento: multiplica velocidade por WHIP_DAMP cada step
# ---------------------------------------------------------------------------
def update_cilio_nodes(key, base_x, base_y, dir_x, dir_y, fase, tempo, dt):
    nodes = cilio_nodes[key]

    # Raiz sempre na parede — nunca se move
    nodes[0]['x'] = base_x
    nodes[0]['y'] = base_y

    # Direção perpendicular ao eixo radial (plano XY)
    perp_x = -dir_y
    perp_y =  dir_x

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
            fx = -dx * WHIP_STIFF + perp_x * amp * math.sin(tempo * WHIP_FREQ       + fase + i * 0.5)
            fy = -dy * WHIP_STIFF + perp_y * amp * math.sin(tempo * WHIP_FREQ * 0.8 + fase + i * 0.4)

            n['vx'] = (n['vx'] + fx * sdt) * WHIP_DAMP
            n['vy'] = (n['vy'] + fy * sdt) * WHIP_DAMP
            n['x'] += n['vx']
            n['y'] += n['vy']

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
    anel_inicio = max(0, int(z_inicio // CILIO_SPACING))
    anel_fim = int(z_fim // CILIO_SPACING) + 1
    return [
        ((anel, cilio), *get_cilio(anel, cilio))
        for anel in range(anel_inicio, anel_fim)
        for cilio in range(CILIOS_PER_RING)
    ]

# ---------------------------------------------------------------------------
#  draw_cilio — Renderiza um cílio como curva de Bézier 3D e testa colisão
# ---------------------------------------------------------------------------
def draw_cilio(key, base_z, angle, length, phase, t, dt):
    """Desenha um cílio e retorna True se colidiu com o vírus.

    Usa uma curva de Bézier cúbica com 4 pontos de controle:
      P0 (base na parede) → P1 (1/3) → P2 (2/3) → P3 (ponta)
    
    O efeito de chicote é criado por atraso de fase progressivo:
      P1 balança sem atraso, P2 com atraso de 1 rad, P3 com 2 rad.

    Parâmetros:
        key    -- Tupla (indice_anel, indice_cilio) para identificação
        base_z -- Posição Z da base do cílio no túnel
        angle  -- Ângulo em radianos da posição na parede (0 a 2π)
        length -- Comprimento do cílio (varia aleatoriamente)
        phase  -- Fase inicial da animação (evita sincronismo)
        t      -- Tempo atual em segundos
        dt     -- Delta time do frame

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
prog = None     # Shader GLSL compilado (createShader) — usado na Fase 2
hud  = None     # Buffer 2D auxiliar (createGraphics) — para textos sobre WEBGL
W = H = 0       # Largura e altura do canvas

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
#  Geração Procedural
#  Todas as funções usam random.Random(seed) local, garantindo que o
#  mesmo índice sempre gera o mesmo objeto (determinismo por seed).
# ---------------------------------------------------------------------------

def make_cilio(indice_anel, indice_cilio):
    """Versão legada de get_cilio (sem cache). Mantida para referência."""
    rng    = random.Random((indice_anel * 997 + indice_cilio * 31 + SEED) & 0xFFFFFFFF)
    posicao_z = indice_anel * CILIO_SPACING
    angulo = (indice_cilio / CILIOS_PER_RING) * math.tau + rng.uniform(-0.2, 0.2)
    comprimento = rng.uniform(CILIO_LEN * 0.5, CILIO_LEN)
    fase = rng.uniform(0, math.tau)
    return posicao_z, angulo, comprimento, fase

def make_cell(indice_celula):
    """Gera posição de uma célula infectável dentro do túnel.

    Cada célula fica em uma posição polar aleatória (20% a 70% do raio
    do túnel), espaçada CELL_SPACING unidades no eixo Z.

    Retorna: (posicao_z, centro_x, centro_y)
    """
    rng = random.Random((indice_celula * 1234567 + SEED) & 0xFFFFFFFF)
    posicao_z = CELL_SPACING + indice_celula * CELL_SPACING
    raio_polar  = rng.uniform(TUNNEL_RADIUS * 0.20, TUNNEL_RADIUS * 0.70)
    angulo = rng.uniform(0, math.tau)
    return posicao_z, raio_polar * math.cos(angulo), raio_polar * math.sin(angulo)

# def collect_visible_cilios():
#     z0 = cam_z_f1 - 50.0
#     z1 = cam_z_f1 + VIEW_DIST
#     r0 = max(0, int(z0 // CILIO_SPACING))
#     r1 = int(z1 // CILIO_SPACING) + 1
#     return [make_cilio(ri, ci) for ri in range(r0, r1) for ci in range(CILIOS_PER_RING)]

def collect_visible_cells():
    """Retorna células visíveis e ainda não coletadas na janela de visibilidade."""
    z_inicio = cam_z_f1 - 50.0
    z_fim = cam_z_f1 + VIEW_DIST
    idx_inicio = max(0, int((z_inicio - CELL_SPACING) // CELL_SPACING))
    idx_fim = int((z_fim - CELL_SPACING) // CELL_SPACING) + 2
    resultado = []
    for i in range(idx_inicio, idx_fim + 1):
        if i in collected_cells:
            continue
        z, cx, cy = make_cell(i)
        if z_inicio <= z <= z_fim:
            resultado.append((i, z, cx, cy))
    return resultado

def make_obstacle(indice_obstaculo):
    """Gera um obstáculo da Fase 2 (hemácia ou glóbulo branco).

    30% chance de glóbulo branco (maior, typ >= 3.14).
    70% chance de hemácia (menor, typ < 3.14).
    Posição distribuída uniformemente dentro do círculo do vaso.

    O campo 'typ' serve duplo propósito:
      - No shader: typ < 3.14 renderiza hemácia, >= 3.14 renderiza glóbulo
      - Na colisão Python: não é usado diretamente

    Retorna: (posicao_z, centro_x, centro_y, raio, tipo)
    """
    rng = random.Random((indice_obstaculo * 2654435761) & 0xFFFFFFFF)
    eh_globulo = rng.random() < 0.3
    if eh_globulo:
        raio = rng.uniform(2.5, 3.5)   # Glóbulos são maiores
    else:
        raio = rng.uniform(1.6, 2.8)   # Hemácias são menores
    limite = TUNNEL_HALF - raio - 0.4   # Margem da parede
    # Distribuição uniforme em disco: sqrt(random) corrige o viés para o centro
    angulo = rng.uniform(0, math.tau)
    dist_centro = limite * math.sqrt(rng.random())
    centro_x = math.cos(angulo) * dist_centro
    centro_y = math.sin(angulo) * dist_centro
    tipo = rng.uniform(3.15, 6.28) if eh_globulo else rng.uniform(0.0, 3.13)
    return OB_START + indice_obstaculo * SPACING, centro_x, centro_y, raio, tipo

def collect_obstacles():
    """Coleta obstáculos visíveis e formata como arrays para o shader.

    Retorna:
        rel   -- Lista flat de [x, y, z] relativos à câmera (até MAX_OBS * 3)
        rads  -- Lista de raios (até MAX_OBS)
        types -- Lista de tipos (até MAX_OBS)
        count -- Quantidade real de obstáculos ativos
    """
    indice_base = int((cam_z_f2 - OB_START) // SPACING)
    posicoes_relativas, raios, tipos = [], [], []
    contagem = 0
    n = max(0, indice_base - 1)
    while contagem < MAX_OBS and n < indice_base + MAX_OBS + 2:
        z, cx, cy, raio, tipo = make_obstacle(n)
        dist_z = z - cam_z_f2  # Distância Z relativa à câmera
        n += 1
        if dist_z < -1.0 or dist_z > 150.0:
            continue
        posicoes_relativas.extend([cx - px_f2, cy - py_f2, dist_z])
        raios.append(raio)
        tipos.append(tipo)
        contagem += 1
    # Preenche slots vazios com dados inertes (z=9999 = invisível no shader)
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
    global cilio_cache, cilio_nodes

    cilio_cache.clear()   # Limpa cache para regenerar cílios
    cilio_nodes.clear()   # Limpa nós de física
    
    P5.camera()           # Restaura câmera padrão
    P5.perspective()      # Restaura projeção padrão

    cam_z_f1 = px_f1 = py_f1 = 0.0
    pontos = 0
    collected_cells = set()
    state = "fase1"

def reset_fase_2():
    """Reinicia a Fase 2: zera posição, velocidade e score."""
    global cam_z_f2, px_f2, py_f2, speed, score, hit_flash, state

    P5.camera()
    P5.perspective()

    cam_z_f2 = px_f2 = py_f2 = 0.0
    speed = 18.0
    score = hit_flash = 0.0
    state = "fase2"

# ---------------------------------------------------------------------------
#  setup — Inicialização do p5.js (chamado 1x no início)
# ---------------------------------------------------------------------------

def setup():
    """Cria canvas WEBGL, compila o shader e inicializa o buffer de HUD."""
    global prog, hud, W, H
    P5.createCanvas(900, 600, P5.WEBGL)  # Canvas 3D com WebGL
    P5.pixelDensity(1)                    # 1 pixel real = 1 pixel do canvas
    W, H = P5.width, P5.height
    prog = P5.createShader(VERT, FRAG)    # Compila os shaders GLSL
    hud = P5.createGraphics(W, H)         # Buffer 2D para textos (HUD)

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

    # Posição da câmera
    P5.camera(px_f1, py_f1,        cam_z_f1 - 150.0,
              px_f1, py_f1,        cam_z_f1 + 300.0,
              0, 1, 0)
    P5.perspective(P5.PI / 3.6, float(W) / float(H), 1.0, 5000.0)

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

    # =======================================================================
    #  Renderização do Vírus (Jogador) — Evolução Visual
    #
    #  O vírus sofre mutação e evolui visualmente à medida que coleta células.
    #  A aparência muda em 4 eixos principais: Cor, Tamanho, Quantidade de Espinhos
    #  e Tamanho dos Espinhos. Tudo é interpolado usando a variável 'prog_t'.
    # =======================================================================
    
    # 1. Cálculo da Progressão (0.0 a 1.0)
    # Garante que a mutação pare de crescer ao atingir a meta da fase (PONTOS_PARA_FASE2)
    prog_t = min(1.0, pontos / PONTOS_PARA_FASE2)
    
    # 2. Interpolação de Cores (RGB)
    # Inicia como um tom neutro/pálido (180, 120, 130) e evolui para um
    # vermelho agressivo e vibrante (200, 20, 50) no final da fase.
    vr = int(180 + prog_t * 20)
    vg = int(120 - prog_t * 100)
    vb = int(130 - prog_t * 80)
    
    # 3. Evolução Geométrica
    virus_r = SHIP_RADIUS_F1 * (1.0 + prog_t * 0.4) # Cresce até 40% a mais do tamanho original
    n_spikes = 3 + int(prog_t * 9)                  # Começa com 3 espinhos, termina com 12
    spike_r  = 4 + prog_t * 4                       # Espinhos dobram de tamanho (de 4 para 8)

    P5.push()
    # Move a "caneta 3D" para a posição atual do jogador na tela
    P5.translate(px_f1, py_f1, cam_z_f1)
    P5.noStroke()
    
    # 4. Desenha o corpo central do Vírus
    P5.fill(vr, vg, vb)
    P5.sphere(virus_r)
    
    # 5. Desenha os Espinhos (Proteínas Virais)
    # Os espinhos são distribuídos uniformemente em um anel ao redor do corpo
    for i in range(n_spikes):
        # Ângulo base do espinho no anel (0 a 2π)
        a = (i / n_spikes) * math.tau
        
        # Animação Procedural: 'elev' faz os espinhos subirem e descerem suavemente no eixo Z,
        # dando a impressão de um organismo vivo que respira e se contorce.
        elev = math.sin(i * 1.2 + t * 0.5) * 0.3
        
        P5.push()
        # Posiciona o espinho na borda do corpo principal (0.85 * raio = levemente afundado no corpo)
        P5.translate(math.cos(a) * virus_r * 0.85,
                     math.sin(a) * virus_r * 0.85,
                     elev * virus_r * 0.3)
        
        # A cor do espinho é sempre uma versão um pouco mais clara e brilhante do corpo
        P5.fill(min(255, vr + 40), min(255, vg + 30), min(255, vb + 20))
        P5.sphere(spike_r)
        P5.pop()
        
    # 6. Efeito de Brilho / Aura (Apenas se já coletou alguma célula)
    if prog_t > 0:
        # A aura pulsa em opacidade baseada no tempo
        glow_pulse = 0.8 + 0.2 * math.sin(t * 3.0)
        # Esfera translúcida alaranjada, cuja opacidade total é ditada pelo progresso (prog_t)
        P5.fill(255, 100, 60, int(40 * prog_t * glow_pulse))
        P5.sphere(virus_r * 1.5) # Aura é 50% maior que o corpo
        
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

    P5.stroke(40, 180, 120, 100)
    P5.strokeWeight(0.8)
    P5.noFill()
    for li in range(8):
        a  = (li / 8.0) * math.tau
        xv = math.cos(a) * TUNNEL_RADIUS
        yv = math.sin(a) * TUNNEL_RADIUS
        P5.line(xv, yv, cam_z_f1 - 200.0, xv, yv, cam_z_f1 + VIEW_DIST)


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
    P5.perspective(P5.PI / 3.6, float(W) / float(H), 1.0, 5000.0)

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
    pdist = math.hypot(px_f2, py_f2)
    if pdist > lim and pdist > 0:
        px_f2 = px_f2 / pdist * lim
        py_f2 = py_f2 / pdist * lim

    speed     = min(60.0, 18.0 + cam_z_f2 * 0.02)
    cam_z_f2 += speed * dt
    score     = cam_z_f2
    if score > best_f2:
        best_f2 = score

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