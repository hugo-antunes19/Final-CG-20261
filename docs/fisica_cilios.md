# 🌊 Física dos Cílios — Sistema de Chicote

## Visão Geral

Os cílios no jogo possuem dois sistemas de animação sobrepostos:

1. **Curva de Bézier animada** — O visual renderizado (4 pontos de controle com atraso de fase)
2. **Simulação de chicote (whip physics)** — Um sistema de molas/amortecimento que adiciona naturalidade (parcialmente implementado)

---

## Sistema Principal — Bézier com Phase Delay

### Conceito

O efeito de "chicote" visual é criado por **atraso de fase progressivo** nos pontos de controle da curva de Bézier. A onda de movimento começa na base e se propaga até a ponta com amplitude crescente:

```
Base (P0)  ──→  P1      ──→  P2       ──→  Ponta (P3)
Fixo          Atraso 0     Atraso 1.0    Atraso 2.0
Amp: 0%       Amp: 30%     Amp: 50%      Amp: 80%
```

### Implementação

```python
freq = 1.2  # Frequência de oscilação

# P0 — Base: fixa na parede
p0x, p0y = bx, by

# P1 — 1/3 do cílio: balanço suave
sway1 = sin(t * freq + phase) * (length * 0.3)
p1x = bx + inx * (length * 0.33) + perp_x * sway1

# P2 — 2/3 do cílio: balanço atrasado em 1 radiano
sway2 = sin(t * freq + phase - 1.0) * (length * 0.5)
p2x = bx + inx * (length * 0.66) + perp_x * sway2

# P3 — Ponta: balanço atrasado em 2 radianos, amplitude máxima
sway3 = sin(t * freq + phase - 2.0) * (length * 0.8)
p3x = bx + inx * length + perp_x * sway3
```

### Vetores de Direção

Cada cílio utiliza dois vetores perpendiculares:

```python
# Vetor radial (aponta para o centro do túnel)
inx = -cos(angle)
iny = -sin(angle)

# Vetor tangencial (perpendicular ao radial, no plano XY)
perp_x = -iny     # = sin(angle)
perp_y =  inx     # = -cos(angle)
```

O cílio **cresce** na direção `(inx, iny)` e **balança** na direção `(perp_x, perp_y)`.

---

## Sistema Secundário — Simulação de Molas (Whip Physics)

### Modelo Físico

Uma cadeia de **nós** conectados por molas virtuais, da base (fixa na parede) à ponta (livre):

```
PAREDE ─── Nó₀ ─── Nó₁ ─── Nó₂ ─── Nó₃ ─── Nó₄
           fixo     mola    mola    mola    livre
```

### Constantes

| Constante | Valor | Descrição |
|---|---|---|
| `WHIP_SEGS` | 4 | Número de segmentos da cadeia |
| `WHIP_STIFF` | 0.35 | Rigidez da mola (coeficiente de restauração) |
| `WHIP_DAMP` | 0.87 | Amortecimento (0 = sem amortecimento, 1 = sem perda) |
| `WHIP_FORCE` | 0.5 | Amplitude da força oscilatória |
| `WHIP_FREQ` | 1.2 | Frequência da oscilação |

### Inicialização dos Nós

```python
def init_cilio_nodes(key, bx, by, bz, inx, iny, length):
    seg = length / WHIP_SEGS
    nodes = []
    for i in range(WHIP_SEGS + 1):
        nodes.append({
            'x':  bx + inx * seg * i,    # Posição atual X
            'y':  by + iny * seg * i,    # Posição atual Y
            'vx': 0.0,                   # Velocidade X
            'vy': 0.0,                   # Velocidade Y
            'rx': bx + inx * seg * i,    # Posição de repouso X
            'ry': by + iny * seg * i,    # Posição de repouso Y
        })
```

### Atualização Física (por frame)

```python
def update_cilio_nodes(key, bx, by, inx, iny, phase, t, dt):
    SUBSTEPS = 4   # Sub-passos para estabilidade numérica
    sdt = dt / SUBSTEPS
    
    for _ in range(SUBSTEPS):
        for i in range(1, WHIP_SEGS + 1):
            # Posição-alvo = nó anterior + offset de repouso relativo
            target_x = nodes[i-1]['x'] + rest_rel_x
            target_y = nodes[i-1]['y'] + rest_rel_y
            
            dx = nodes[i]['x'] - target_x
            dy = nodes[i]['y'] - target_y
            
            # Amplitude cresce da base à ponta
            amp = WHIP_FORCE * (i / WHIP_SEGS)
            
            # Força = mola restauradora + oscilação perpendicular
            fx = -dx * WHIP_STIFF + perp_x * amp * sin(t * freq + phase + i * 0.5)
            fy = -dy * WHIP_STIFF + perp_y * amp * sin(t * freq + phase + i * 0.4)
            
            # Integração de Euler semi-implícito
            vx = (vx + fx * sdt) * WHIP_DAMP
            vy = (vy + fy * sdt) * WHIP_DAMP
            x += vx
            y += vy
```

### Diagrama de Forças em Cada Nó

```
        Força de Mola (restauradora)
        ←──── dx × WHIP_STIFF ────→
                    │
                    ▼ Nó[i]
                    │
        Força Oscilatória (perpendicular)
    ↕ perp × amp × sin(t + phase + i)
```

---

## Cache e Performance

### Cache de Parâmetros

Parâmetros geométricos dos cílios são **cacheados** na primeira geração:

```python
cilio_cache = {}   # (ring_index, cilio_index) → (base_z, angle, length, phase)
```

### Cache de Nós Físicos

Os nós de simulação também são persistidos entre frames:

```python
cilio_nodes = {}   # (ring_index, cilio_index) → lista de nós
```

### Visibilidade (Frustum Culling Manual)

Apenas cílios dentro da janela de visibilidade são processados:

```python
def collect_visible_cilios():
    z0 = cam_z_f1 - 50.0         # 50 unidades atrás da câmera
    z1 = cam_z_f1 + VIEW_DIST    # VIEW_DIST (1200) à frente
    r0 = max(0, int(z0 // CILIO_SPACING))
    r1 = int(z1 // CILIO_SPACING) + 1
```

---

## Efeito Visual — Pulsação Luminosa

O brilho de cada cílio pulsa individualmente:

```python
pulse = 0.6 + 0.4 * sin(t * 2.2 + phase)
v = int(30 + pulse * 60)       # Varia de 30 a 90
P5.stroke(v, v, v, 210)       # Cinza escuro pulsante
P5.strokeWeight(3.5)
```

Isso cria a impressão de cílios **semi-transparentes** e **vivos**.
