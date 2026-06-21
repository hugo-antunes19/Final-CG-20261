# Documentação Técnica — RETROVÍRUS

Jogo de Computação Gráfica em **Py5Script** (Python + p5.js no browser) usando **WEBGL** e **GLSL (Raymarching SDF)**.

---

## Índice

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Constantes e Configuração](#2-constantes-e-configuração)
3. [Fragment Shader — Raymarching SDF](#3-fragment-shader--raymarching-sdf)
4. [Geração Procedural](#4-geração-procedural)
5. [Cílios — Curvas de Bézier com Física de Chicote](#5-cílios--curvas-de-bézier-com-física-de-chicote)
6. [Máquina de Estados e Loop Principal](#6-máquina-de-estados-e-loop-principal)
7. [Renderização Fase 1 — Túnel Epitelial](#7-renderização-fase-1--túnel-epitelial)
8. [Renderização Fase 2 — Corrente Sanguínea](#8-renderização-fase-2--corrente-sanguínea)
9. [Sistema de HUD](#9-sistema-de-hud)

---

## 1. Visão Geral da Arquitetura

```
┌──────────────────────────────────────────────────┐
│                  sketch.py                       │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │ Fase 1   │  │ Fase 2   │  │ Menu / HUD     │ │
│  │ p5.js 3D │  │ Shader   │  │ Buffer 2D      │ │
│  │ WEBGL    │  │ GLSL     │  │ (createGraphics)│ │
│  └──────────┘  └──────────┘  └────────────────┘ │
│                                                  │
│  ┌──────────────────────────────────────────────┐│
│  │ Geração Procedural (seed determinística)     ││
│  │ Cache de Cílios + Física de Chicote          ││
│  └──────────────────────────────────────────────┘│
└──────────────────────────────────────────────────┘
```

### Fluxo do Jogo

```
start → fase1 → win → fase2 → over
                  ↑              │
                  └──────────────┘
```

- **Fase 1**: Renderização 3D nativa do p5.js (geometria, luzes, perspectiva)
- **Fase 2**: Renderização 100% via fragment shader GLSL (raymarching)
- **HUD**: Buffer 2D (`createGraphics`) carimbado sobre o canvas WEBGL

### Objeto `P5`

Todas as chamadas de desenho usam o objeto global `P5`, que é o binding do p5.js injetado pelo ambiente Py5Script. Exemplo: `P5.sphere()`, `P5.shader()`, `P5.fill()`.

### Interoperabilidade Python ↔ JavaScript

```python
_to_js(lista_python)  # Converte lista Python → array JavaScript
                       # Necessário para passar uniforms ao shader
```

---

## 2. Constantes e Configuração

### Fase 1 — Túnel Epitelial

| Constante | Valor | Descrição |
|-----------|-------|-----------|
| `TUNNEL_RADIUS` | 220.0 | Raio do túnel cilíndrico (pixels) |
| `SHIP_RADIUS_F1` | 18.0 | Raio do vírus na Fase 1 (hitbox fixa) |
| `MOVE_SPEED_F1` | 6.0 | Velocidade lateral do vírus (px/frame) |
| `FWD_SPEED_F1` | 5.5 | Velocidade de avanço/recuo no eixo Z |
| `CELL_SPACING` | 250.0 | Distância entre células infectáveis |
| `CELL_RADIUS` | 22.0 | Raio visual de cada célula |
| `CELL_COL_DIST` | 40.0 | Distância de colisão vírus↔célula |
| `PONTOS_PARA_FASE2` | 5 | Células necessárias para avançar |
| `VIEW_DIST` | 1200.0 | Distância de renderização à frente |
| `SEED` | 42 | Semente para geração procedural |

### Cílios — Parâmetros da Curva e Física

| Constante | Valor | Descrição |
|-----------|-------|-----------|
| `CILIO_SPACING` | 120.0 | Distância em Z entre anéis de cílios |
| `CILIOS_PER_RING` | 4 | Cílios por anel (distribuídos em 360°) |
| `CILIO_LEN` | 110.0 | Comprimento máximo de um cílio |
| `CILIO_RADIUS_COL` | 14.0 | Raio de colisão da ponta do cílio |
| `WHIP_SEGS` | 4 | Segmentos da cadeia de física |
| `WHIP_STIFF` | 0.35 | Rigidez da mola (spring constant) |
| `WHIP_DAMP` | 0.87 | Amortecimento (0=sem, 1=total) |
| `WHIP_FORCE` | 0.5 | Amplitude da força oscilatória |
| `WHIP_FREQ` | 1.2 | Frequência do balançar (Hz) |

### Fase 2 — Corrente Sanguínea

| Constante | Valor | Descrição |
|-----------|-------|-----------|
| `MAX_OBS` | 8 | Máximo de obstáculos simultâneos no shader |
| `TUNNEL_HALF` | 6.0 | Meio-raio do túnel cilíndrico (unidades shader) |
| `SHIP_RADIUS_F2` | 0.55 | Raio do vírus na Fase 2 |
| `SPACING` | 16.0 | Distância em Z entre obstáculos |
| `OB_START` | 28.0 | Z do primeiro obstáculo |
| `RIDGE_MOD` | 64.0 | Módulo para wrap da posição Z (evita perda de precisão float) |

---

## 3. Fragment Shader — Raymarching SDF

> O shader da Fase 2 renderiza **toda a cena** usando a técnica de **raymarching** com **Signed Distance Fields (SDF)**.

### O que é Raymarching?

Para cada pixel da tela, um raio é lançado da câmera. O raio avança em passos, onde cada passo tem o tamanho da menor distância até qualquer superfície da cena (a SDF). Quando essa distância é menor que um limiar (0.002), o raio "acertou" uma superfície.

```
Câmera ──→ ·····→ ···→ ··→ ·→ ● HIT!
           passo1 p2   p3  p4
           (grande → cada vez menor conforme se aproxima)
```

### Uniforms (Dados Python → Shader)

| Uniform | Tipo | Descrição |
|---------|------|-----------|
| `uResolution` | `vec2` | Tamanho do canvas (900, 600) |
| `uTime` | `float` | Tempo em segundos desde o início |
| `uCamZ` | `float` | Posição Z da câmera mod 64 (evita imprecisão float) |
| `uPlayer` | `vec2` | Deslocamento lateral do jogador (x, y) |
| `uObCount` | `int` | Número de obstáculos ativos (0-8) |
| `uObRel[8]` | `vec3[]` | Posição de cada obstáculo relativa à câmera |
| `uObRad[8]` | `float[]` | Raio de cada obstáculo |
| `uObType[8]` | `float[]` | Tipo: <3.14 = hemácia, ≥3.14 = glóbulo branco |
| `uHit` | `float` | Intensidade do flash de colisão (0.0 a 1.0) |

### SDFs Primitivas

#### `sdSphere(p, r)` — Esfera
```glsl
// Distância do ponto p ao centro de uma esfera de raio r
// Retorna: negativo se dentro, positivo se fora, zero na superfície
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}
```

#### `sdBox(p, b)` — Caixa (não usada visualmente, mantida como utilitário)
```glsl
// Distância até uma caixa centrada na origem com meio-tamanhos b.xyz
```

#### `sdTorus(p, t)` — Toro (anel)
```glsl
// t.x = raio maior (distância do centro ao anel)
// t.y = raio menor (espessura do tubo)
// O toro fica no plano XZ
```

### Funções Auxiliares

#### `rot(a)` — Matriz de rotação 2D
```glsl
// Retorna uma mat2 que roda um vec2 em 'a' radianos
// Usada para girar os obstáculos e o vírus ao longo do tempo
mat2 rot(float a) { ... }
```

#### `smin(a, b, k)` — Smooth Minimum (Mínimo Suave)
```glsl
// Une duas SDFs com uma transição suave (orgânica) em vez de aresta viva
// k = raio de suavização (maior = mais blobby/orgânico)
// Essencial para criar os pseudópodes do glóbulo branco e espinhos do vírus
```
**Uso**: `smin(esfera1, esfera2, k)` produz uma forma como se as esferas estivessem "derretendo" uma na outra.

### SDFs dos Objetos Biológicos

#### `sdHemacia(p, r)` — Glóbulo Vermelho (Hemácia)

Forma: **disco bicôncavo** (borda grossa, centro fino — como uma bala de goma achatada)

```
Corte lateral:    ___________
                 /   ·····   \    ← torus (borda grossa, r*0.3 de espessura)
                |  ·       ·  |
                 \ ·········/     ← disco (centro fino, r*0.1 de espessura)
                  ‾‾‾‾‾‾‾‾‾
```

**Construção**:
1. `rim` = Toro com raio maior `r*0.55` e raio menor `r*0.3` → cria a borda grossa
2. `disc` = Interseção de cilindro (raio `r*0.55`) + slab (altura `r*0.1`) → centro fino
3. `min(rim, disc)` = União das duas formas → disco bicôncavo completo

**Por que não usar esfera achatada?** Escalar coordenadas (`p.y * 3.0`) distorce o campo de distância, quebrando o raymarching. O torus+disco é uma SDF **exata** — sem artefatos visuais.

#### `sdGlobuloBranco(p, r)` — Glóbulo Branco (Leucócito)

Forma: **esfera irregular com pseudópodes** (protuberâncias ameboides)

**Construção**:
1. Esfera principal de raio `r*0.75` (corpo)
2. Três esferas menores (`r*0.25` a `r*0.35`) posicionadas ao redor
3. `smin()` com `k = r*0.25` une tudo com transições suaves
4. As rotações aplicadas em `obstacleSDF()` fazem os pseudópodes girarem

#### `sdVirus(p)` — Vírus do Jogador

Forma: **esfera com 8 espinhos** (coroa viral)

**Construção**:
1. Esfera principal de raio `VIRUS_R` (0.55)
2. 6 esferas nos eixos ±X, ±Y, ±Z a distância `VIRUS_R*0.85`
3. 2 esferas em diagonais para preencher
4. `smin()` com `k = VIRUS_R*0.1` (baixo = espinhos pontiagudos, não blobby)
5. Rotação lenta via `rot(uTime * 0.5)` e `rot(uTime * 0.3)` para animação

**Posição**: fixo em `z = VIRUS_Z (8.0)` à frente da câmera → terceira pessoa.

#### `obstacleSDF(p, center, r, typ)` — Roteador de Obstáculos

Posiciona o ponto no espaço local do obstáculo (subtrai `center`, aplica rotações), depois chama `sdHemacia` ou `sdGlobuloBranco` conforme o valor de `typ`:

| `typ` | Tipo | Forma |
|-------|------|-------|
| < 3.14 | Hemácia | Disco bicôncavo |
| ≥ 3.14 | Glóbulo Branco | Esfera com pseudópodes |

### Cena Completa

#### `tunnelSDF(p)` — Túnel Cilíndrico (Vaso Sanguíneo)

```glsl
// Distância interna: TUNNEL_HALF - distância_do_centro
// O jogador (uPlayer) move o túnel ao redor da câmera (câmera sempre na origem)
return TUNNEL_HALF - length(vec2(p.x + uPlayer.x, p.y + uPlayer.y));
```

#### `mapScene(p, mat)` — Composição da Cena

Avalia **todas** as SDFs e retorna a menor distância + identifica o material:

| Material (`mat`) | Objeto |
|-------------------|--------|
| 0.0 | Parede do túnel |
| 1.0 | Hemácia |
| 2.0 | Glóbulo branco |
| 3.0 | Vírus |

#### `calcNormal(p)` — Normal da Superfície

Calcula o **gradiente numérico** da SDF no ponto de hit usando diferenças finitas centrais com epsilon = 0.0025:

```
normal = normalize(∂SDF/∂x, ∂SDF/∂y, ∂SDF/∂z)
```

Isso dá o vetor perpendicular à superfície, necessário para iluminação.

### `tunnelColor(p)` — Cor das Paredes do Vaso

- **Base**: vermelho escuro `(0.35, 0.05, 0.05)` — interior de vaso sanguíneo
- **Padrão radial**: `atan(wy, wx)` cria linhas que seguem a curvatura do cilindro
- **Padrão longitudinal**: `fract(wz * 0.18)` cria anéis ao longo do Z
- **Pulso cardíaco**: onda sinusoidal viajando em Z (`sin(z*0.12 - t*4.0)`) simula o batimento

### `main()` — Loop Principal do Shader

```
1. SETUP UV
   uv = coordenada normalizada do pixel (-0.5 a 0.5 em Y)

2. DEFINIR RAIO
   ro = vec3(0)        → câmera na origem
   rd = normalize(uv, 1.45) → direção do raio (FOV controlado por 1.45)

3. RAYMARCHING (até 90 passos)
   Para cada passo:
     d = mapScene(ro + rd * t)  → distância mínima
     Se d < 0.002 → HIT (acertou superfície)
     Senão, avança t += d
     Se t > 170 → MISS (nada encontrado)

4. SHADING (se hit)
   - Calcula normal, difusa, ambiente, fresnel
   - Aplica cor por material (túnel/hemácia/glóbulo/vírus)
   - Aplica névoa exponencial (profundidade → vermelho escuro)

5. PÓS-PROCESSAMENTO
   - Flash vermelho de colisão (mistura com uHit)
   - Correção gamma (pow 0.4545 = gamma 2.2)
```

### Modelo de Iluminação

Para cada hit, três componentes são calculados:

| Componente | Fórmula | Efeito Visual |
|------------|---------|---------------|
| **Difusa** | `dot(normal, luz)` | Sombreamento básico (faces viradas para a luz são mais claras) |
| **Ambiente** | `0.25 + 0.25 * normal.y` | Iluminação mínima para evitar preto total |
| **Fresnel** | `(1 - dot(normal, -raio))³` | Brilho nas bordas (silhueta mais clara) |

A hemácia também tem **subsurface scattering simulado**: `dot(raio, normal)²` simula a luz passando "através" da célula.

---

## 4. Geração Procedural

Todos os objetos são gerados **deterministicamente** a partir de um índice, usando `random.Random(seed)` local:

### `get_cilio(indice_anel, indice_cilio)`

Gera um cílio na parede do túnel com cache (nunca recria).

**Parâmetros**:
- `indice_anel` — Qual anel ao longo do eixo Z (0, 1, 2, ...). Cada anel está a `CILIO_SPACING` unidades do anterior
- `indice_cilio` — Qual cílio dentro do anel (0 a `CILIOS_PER_RING - 1`)

**Distribuição em espiral**: cada anel é girado 30° em relação ao anterior (`indice_anel * 30°`), criando um padrão espiral que evita alinhamento de cílios entre anéis consecutivos.

**Retorna**: `(posicao_z, angulo, comprimento, fase_animacao)`

### `make_cell(indice_celula)`

Gera uma célula infectável em posição polar aleatória dentro do túnel (20% a 70% do raio).

### `make_obstacle(n)`

Gera um obstáculo da Fase 2. Com 30% de chance é glóbulo branco (maior, tipo ≥3.14), 70% hemácia (menor, tipo <3.14). Distribuição circular (`sqrt(random)` para uniformidade).

### `collect_visible_*()` — Coleta por Janela de Visibilidade

Essas funções determinam quais objetos estão na zona visível (`cam_z - offset` a `cam_z + VIEW_DIST`) e retornam apenas esses, evitando processar milhares de objetos.

---

## 5. Cílios — Curvas de Bézier com Física de Chicote

### Estrutura Visual

Cada cílio é uma **curva de Bézier cúbica 3D** com 4 pontos:

```
P0 (base na parede) ──── P1 (1/3) ──── P2 (2/3) ──── P3 (ponta)
```

### Efeito de Chicote (Whip Effect)

Os pontos P1, P2, P3 balançam com **atraso de fase progressivo**:

```python
sway1 = sin(t * freq + phase)          # P1: sem atraso
sway2 = sin(t * freq + phase - 1.0)    # P2: atrasado 1 rad
sway3 = sin(t * freq + phase - 2.0)    # P3: atrasado 2 rad
```

Esse atraso faz a onda viajar da base à ponta, como um chicote real. A amplitude cresce da base (30% do comprimento) à ponta (80%).

### Colisão

Apenas a **ponta (P3)** é testada contra o vírus, usando distância euclidiana simples.

---

## 6. Máquina de Estados e Loop Principal

### Estados

| Estado | Tela | Transição |
|--------|------|-----------|
| `"start"` | Menu inicial | ESPAÇO → `"fase1"` |
| `"fase1"` | Jogando Fase 1 | 5 células → `"win"`, cílio → `"over"` |
| `"win"` | Tela de vitória | ESPAÇO → `"fase2"` |
| `"fase2"` | Jogando Fase 2 | obstáculo → `"over"` |
| `"over"` | Game over | ESPAÇO → `"fase1"` |

### `draw()` — Loop Principal

Chamado ~60x/segundo pelo p5.js. Despacha para a função de renderização correta baseado no `state`.

### `handle_space()` — Detecção de Borda

Detecta ESPAÇO (ou qualquer tecla de movimento) com **edge detection** — só dispara no momento em que a tecla é **pressionada**, não enquanto mantida.

---

## 7. Renderização Fase 1 — Túnel Epitelial

### Câmera

```python
P5.camera(
    px_f1, py_f1, cam_z_f1 - 150,  # Posição: 150 unidades atrás do vírus
    px_f1, py_f1, cam_z_f1 + 300,  # Olhando para: 300 unidades à frente
    0, 1, 0                         # Up vector
)
P5.perspective(PI/3.6, ...)  # FOV ~50° (estreito para imersão no túnel)
```

### Túnel (`draw_tunnel`)

Cilindro construído com **TRIANGLE_STRIP** — 24 anéis de 32 segmentos cada. Cor base rosa-carne com pulso sinusoidal. 8 linhas longitudinais para dar sensação de profundidade.

### Vírus — Progressão Visual

O vírus muda de aparência conforme coleta células:

```python
prog_t = pontos / PONTOS_PARA_FASE2  # 0.0 a 1.0

# Cor: rosa pálido → vermelho intenso
# Tamanho: SHIP_RADIUS_F1 → SHIP_RADIUS_F1 * 1.4
# Espinhos: 3 → 12
# Glow: invisível → esfera translúcida pulsante
```

> A hitbox permanece fixa (`SHIP_RADIUS_F1`) — o crescimento é puramente cosmético.

---

## 8. Renderização Fase 2 — Corrente Sanguínea

### Pipeline

```
1. Python calcula posições dos obstáculos relativas à câmera
2. Passa como uniforms para o shader
3. Shader renderiza tudo via raymarching (fullscreen quad)
4. Python desenha HUD 2D por cima (resetShader + image)
```

### Colisão (Python)

```python
virus_z = cam_z_f2 + 8.0  # Posição visual do vírus (VIRUS_Z do shader)

# Z: abs(dz) < rad * 0.45 — compensa hemácias serem discos finos
# Lateral: hypot < rad * 0.6 + SHIP_RADIUS_F2 — compensa SDFs menores que rad
```

### Velocidade Progressiva

```python
speed = min(60.0, 18.0 + cam_z_f2 * 0.02)  # 18 → 60 conforme avança
```

---

## 9. Sistema de HUD

O p5.js em modo WEBGL não suporta `text()` diretamente. Solução:

1. `hud = P5.createGraphics(W, H)` — cria buffer 2D separado
2. Desenha textos e retângulos no buffer 2D
3. `P5.resetShader()` — desativa o shader raymarching
4. `P5.image(hud, ...)` — carimba o buffer 2D sobre o canvas WEBGL

> Após carimbar o HUD, `P5.perspective()` é chamado para restaurar a projeção 3D.
