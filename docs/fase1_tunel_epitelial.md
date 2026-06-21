# 🫁 Fase 1 — Túnel Epitelial

## Conceito

A Fase 1 simula a entrada de um retrovírus pelo **epitélio nasal**. O jogador navega por um túnel cilíndrico 3D, desviando dos cílios (estruturas de defesa do corpo) e infectando células epiteliais.

Toda a renderização é feita com a **geometria nativa do p5.js no modo WebGL**, sem shaders customizados.

---

## Renderização do Túnel

### Geometria

O túnel é um cilindro formado por **anéis** de `TRIANGLE_STRIP`:

```
Parâmetros:
- SEGS  = 32  (segmentos por anel, define a suavidade circular)
- RINGS = 20  (anéis visíveis de uma vez)
- STEP  = VIEW_DIST / RINGS = 60.0 unidades
- TUNNEL_RADIUS = 220.0 unidades
```

Cada anel é calculado com:
```python
for si in range(SEGS + 1):
    a = (si / SEGS) * math.tau   # Ângulo 0..2π
    x = math.cos(a) * TUNNEL_RADIUS
    y = math.sin(a) * TUNNEL_RADIUS
```

### Efeito Visual — Pulsação Peristáltica

O túnel pulsa ao longo do eixo Z para simular movimento peristáltico:

```python
pulse = 0.5 + 0.5 * math.sin(z * 0.012 - t * 2.5)
r = int(220 + pulse * 35)   # 220–255
g = int(140 + pulse * 25)   # 140–165
b = int(140 + pulse * 20)   # 140–160
```

Cores resultantes: tons de **rosa/salmão** que simulam tecido vivo.

### Linhas Longitudinais

8 linhas ao longo do eixo Z criam a sensação de profundidade e velocidade:

```python
for li in range(8):
    a = (li / 8.0) * math.tau
    P5.line(x, y, z_inicio, x, y, z_fim)
```

---

## Cílios — Curvas de Bézier 3D

### Modelagem

Cada cílio é uma **curva de Bézier cúbica** definida por 4 pontos de controle:

```
P0 (base)  → Fixo na parede do túnel
P1 (1/3)   → Balança com amplitude 30% do comprimento
P2 (2/3)   → Balança com atraso de fase (-1.0 rad)
P3 (ponta)  → Máximo balanço, atraso de fase (-2.0 rad)
```

A **mágica do chicote** está no atraso de fase progressivo:

```python
sway1 = sin(t * freq + phase)          # Base: sem atraso
sway2 = sin(t * freq + phase - 1.0)    # Meio: atraso de 1 rad
sway3 = sin(t * freq + phase - 2.0)    # Ponta: atraso de 2 rad
```

Isso cria o efeito visual de uma **onda propagando** da base para a ponta.

### Renderização

```python
P5.beginShape()
P5.vertex(p0x, p0y, p0z)
P5.bezierVertex(p1x, p1y, p1z, p2x, p2y, p2z, p3x, p3y, p3z)
P5.endShape()
```

### Distribuição Espacial

Os cílios são organizados em **anéis** ao longo do eixo Z do túnel, com distribuição **espiral** para garantir cobertura uniforme:

```python
# Cada anel roda 30° em relação ao anterior
offset_anel = ring_index * math.radians(30)

# Ângulo final = posição base + rotação do anel + aleatoriedade
angle = (cilio_index / CILIOS_PER_RING) * tau + offset_anel + random(-0.15, 0.15)
```

- **`CILIOS_PER_RING = 4`** — 4 cílios por anel
- **`CILIO_SPACING = 120.0`** — Distância entre anéis
- **Comprimento:** Varia aleatoriamente entre 50% e 100% de `CILIO_LEN` (110.0)

---

## Células

### Geração

Cada célula é posicionada proceduralmente no interior do túnel:

```python
z = CELL_SPACING + cell_index * CELL_SPACING   # Espaçadas de 250 unidades
r = random(TUNNEL_RADIUS * 0.20, TUNNEL_RADIUS * 0.70)  # 20%–70% do raio
a = random(0, 2π)                                         # Ângulo aleatório
```

### Movimento Dinâmico

As células se movem em **padrão Lissajous** para tornar a captura mais desafiadora:

```python
dinamico_cx = base_cx + sin(t * vel_x + idx) * 45.0
dinamico_cy = base_cy + cos(t * vel_y + idx * 0.8) * 45.0
```

### Renderização

Cada célula é renderizada como **duas esferas concêntricas**:
1. **Interna (sólida):** `fill(255, 220, 100)` — Amarelo dourado
2. **Externa (translúcida):** `fill(255, 240, 150, 100)` — Halo brilhante (135% do raio)

Ambas pulsam via `0.85 + 0.15 * sin(idx * 0.7 + t * 1.2)`.

---

## O Vírus (Jogador)

Renderizado como uma esfera central com 8 spikes:

```python
# Corpo principal
P5.fill(180, 30, 60)       # Vermelho escuro
P5.sphere(SHIP_RADIUS_F1)   # Raio = 18

# 8 spikes ao redor
for i in range(8):
    a = (i / 8.0) * math.tau
    P5.fill(220, 60, 80)   # Vermelho mais claro
    P5.sphere(5)            # Mini-esferas nos spikes
```

---

## Sistema de Câmera e Iluminação

### Câmera

```python
P5.camera(
    px_f1, py_f1, cam_z_f1 - 250.0,    # Posição: atrás do vírus
    px_f1, py_f1, cam_z_f1 + 300.0,     # Olhando para frente
    0, 1, 0                              # Up vector
)
P5.perspective(PI / 3.0, W / H, 1.0, 5000.0)
```

### Iluminação — 3 Pontos

| Luz | Tipo | Cor | Posição | Efeito |
|---|---|---|---|---|
| Ambiente | `ambientLight` | `(60, 20, 30)` | Global | Elimina sombras pretas |
| Principal | `pointLight` | `(255, 230, 200)` | Frente +100z | Brilho molhado |
| Preenchimento | `pointLight` | `(255, 50, 80)` | Trás -100z | Subsurface scattering |

---

## Detecção de Colisão

### Vírus × Cílio
Colisão com a **ponta** do cílio (P3):

```python
dz = base_z - cam_z_f1
if abs(dz) < CILIO_RADIUS_COL + SHIP_RADIUS_F1:       # 14 + 18 = 32
    if hypot(p3x - px_f1, p3y - py_f1) < 32:
        return True  # COLISÃO → Game Over
```

### Vírus × Célula
Colisão com o centro da célula:

```python
if abs(dz) < CELL_COL_DIST:                            # 18 + 22 = 40
    if hypot(cx - px_f1, cy - py_f1) < CELL_COL_DIST:
        # Célula infectada → pontos++
```

---

## HUD (Heads-Up Display)

O HUD é renderizado em um **buffer 2D separado** (`createGraphics`) e carimbado sobre o canvas 3D:

```python
hud.clear()
hud.rect(10, 10, 220, 65, 8)          # Caixa de fundo
hud.text("CELULAS INFECTADAS", 20, 12) # Título
hud.rect(18, 38, bw, 14, 4)            # Barra de progresso

P5.resetShader()
P5.image(hud, -W/2, -H/2, W, H)       # Carimba no canvas 3D
```

Essa técnica é necessária porque o modo WebGL do p5.js tem limitações com renderização de texto 2D diretamente.
