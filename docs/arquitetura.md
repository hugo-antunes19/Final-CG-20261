# 🏗️ Arquitetura do Projeto

## Visão Geral

O RETROVÍRUS é uma aplicação single-file (`sketch.py`) organizada em camadas funcionais bem definidas. Toda a lógica do jogo, renderização e física estão contidas em um único arquivo Python executado via **Py5Script** (Python no navegador via Pyodide + p5.js).

---

## Diagrama de Fluxo

```
┌──────────────┐
│   setup()    │ ← Inicialização (canvas, shader, HUD buffer)
└──────┬───────┘
       ▼
┌──────────────┐
│    draw()    │ ← Loop principal (~60 FPS)
└──────┬───────┘
       │
       ├─ state == "start" ──→ draw_menu()
       │
       ├─ state == "fase1" ──→ draw_fase_1()
       │                         ├─ Input do jogador
       │                         ├─ Câmera 3D + Iluminação
       │                         ├─ draw_tunnel() ← Geometria do túnel
       │                         ├─ draw_cilio()  ← Curvas de Bézier
       │                         ├─ draw_cell()   ← Células-alvo
       │                         ├─ Vírus (esfera + spikes)
       │                         ├─ Detecção de colisão
       │                         └─ draw_hud_f1_inline()
       │
       ├─ state == "fase2" ──→ draw_fase_2()
       │                         ├─ Input do jogador
       │                         ├─ Colisão CPU-side
       │                         ├─ Shader raymarching (GPU)
       │                         └─ draw_hud_f2()
       │
       ├─ state == "over"  ──→ draw_menu("COLISÃO!")
       │
       └─ state == "win"   ──→ draw_menu("FASE 1 COMPLETA!")
```

---

## Máquina de Estados

O jogo opera como uma **máquina de estados finita** com 4 estados:

| Estado | Descrição | Transição |
|---|---|---|
| `"start"` | Tela inicial / menu | → `"fase1"` (Espaço/movimento) |
| `"fase1"` | Gameplay do túnel epitelial | → `"over"` (colisão) / `"win"` (5 células) |
| `"fase2"` | Gameplay do tubo sanguíneo | → `"over"` (colisão) |
| `"over"` | Tela de game over | → `"fase1"` (Espaço) |
| `"win"` | Tela de vitória da fase 1 | → `"fase2"` (Espaço) |

A transição de estados é controlada por `handle_space()` que implementa **edge detection** para evitar ações repetidas ao manter a tecla pressionada.

---

## Camadas do Sistema

### 1. Camada de Renderização

#### Fase 1 — Geometria Nativa p5.js (WebGL)
- **Túnel:** `TRIANGLE_STRIP` com 32 segmentos × 20 anéis
- **Cílios:** `bezierVertex()` (curvas de Bézier cúbicas)
- **Células:** Esferas com dupla camada (sólido + translúcido)
- **Vírus:** Esfera central + 8 spikes esféricos
- **HUD:** Buffer 2D separado (`createGraphics`) carimbado sobre o canvas 3D

#### Fase 2 — Fragment Shader GLSL
- **Renderização:** Raymarching SDF em tela cheia
- **Tunnel:** SDF de caixa infinita invertida
- **Obstáculos:** Morphing entre esfera, cubo e toro via `mix()`
- **HUD:** Buffer 2D separado (mesma técnica da Fase 1)

### 2. Camada de Lógica

- **Input:** Polling de teclas via `P5.keyIsDown()`
- **Colisão Fase 1:** Distância euclidiana ponto-a-ponto (vírus × ponta do cílio / centro da célula)
- **Colisão Fase 2:** Distância euclidiana CPU-side contra obstáculos procedurais
- **Pontuação:** Contagem de células (Fase 1) / distância percorrida (Fase 2)

### 3. Camada de Geração Procedural

- **Determinística:** Usa `random.Random` com seed fixa para gerar conteúdo idêntico em cada execução
- **Streaming:** Apenas elementos visíveis são processados (`collect_visible_*`)
- **Cache:** Cílios são cacheados em `cilio_cache` para evitar recálculos

---

## Estado Global

O estado do jogo é mantido em variáveis globais no módulo:

```python
# Controle de estado
state = "start"          # Máquina de estados
prev_space = False       # Edge detection para Espaço

# Fase 1
cam_z_f1 = 0.0           # Posição Z da câmera
px_f1, py_f1 = 0.0, 0.0  # Posição X,Y do vírus
pontos = 0                # Células infectadas
collected_cells = set()   # Índices de células já coletadas

# Fase 2
cam_z_f2 = 0.0            # Posição Z da câmera
px_f2, py_f2 = 0.0, 0.0   # Posição do jogador
speed = 18.0               # Velocidade atual
score = 0.0                # Pontuação (distância)
hit_flash = 0.0            # Intensidade do flash de colisão

# Cache
cilio_cache = {}           # Parâmetros gerados dos cílios
cilio_nodes = {}           # Nós de física dos cílios
```

---

## Interoperabilidade Python ↔ JavaScript

A comunicação entre Python (Pyodide) e JavaScript (p5.js) é feita via:

- **`P5` (objeto global):** Referência ao namespace do p5.js, usado como `P5.createCanvas()`, `P5.sphere()`, etc.
- **`_to_js()`:** Converte listas Python em arrays JavaScript, necessário para enviar dados aos uniforms GLSL.

```python
try:
    _to_js = js_array            # helper fornecido pelo Py5Script
except NameError:
    from pyodide.ffi import to_js as _pyto_js
    def _to_js(x):
        return _pyto_js(x)
```

---

## Constantes Importantes

| Constante | Valor | Descrição |
|---|---|---|
| `TUNNEL_RADIUS` | 220.0 | Raio do túnel na Fase 1 |
| `SHIP_RADIUS_F1` | 18.0 | Raio do vírus na Fase 1 |
| `CILIOS_PER_RING` | 4 | Cílios por anel |
| `CILIO_SPACING` | 120.0 | Distância entre anéis de cílios |
| `PONTOS_PARA_FASE2` | 5 | Células necessárias para fase 2 |
| `VIEW_DIST` | 1200.0 | Distância de renderização |
| `TUNNEL_HALF` | 6.0 | Meia-largura do túnel na Fase 2 |
| `MAX_OBS` | 8 | Máximo de obstáculos simultâneos |
