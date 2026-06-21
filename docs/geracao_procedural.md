# 🎲 Geração Procedural

## Visão Geral

Toda a geração de conteúdo no RETROVÍRUS é **procedural e determinística**. Isso significa que:

1. **Nenhum dado de nível é armazenado em arquivos** — tudo é calculado em tempo real
2. **Mesma seed = mesmo mundo** — O conteúdo é reprodutível entre execuções
3. **Apenas o visível é gerado** — Sistema de streaming baseado na posição da câmera

---

## Seed e Determinismo

O sistema usa `random.Random` com seeds derivadas dos índices dos elementos, garantindo que cada elemento tenha parâmetros **únicos mas reprodutíveis**:

```python
SEED = 42  # Seed global do mundo

# Cada cílio tem sua própria seed baseada na posição
rng = random.Random((ring_index * 997 + cilio_index * 31 + SEED) & 0xFFFFFFFF)

# Cada célula tem outra
rng = random.Random((cell_index * 1234567 + SEED) & 0xFFFFFFFF)

# Cada obstáculo usa um multiplicador primo
rng = random.Random((n * 2654435761) & 0xFFFFFFFF)
```

### Por que `& 0xFFFFFFFF`?

Garante que a seed seja um inteiro de 32 bits, evitando problemas com valores negativos ou muito grandes em diferentes implementações de Python.

### Multiplicadores Primos

Os multiplicadores (`997`, `31`, `1234567`, `2654435761`) são **números primos ou coprimos** escolhidos para minimizar **correlações** entre elementos vizinhos. O valor `2654435761` é um primo de Knuth frequentemente usado em hash functions.

---

## Geração de Cílios

### Distribuição Espiral

Os cílios são distribuídos em **anéis** ao longo do eixo Z do túnel, com uma rotação progressiva que cria um padrão espiral:

```python
def get_cilio(ring_index, cilio_index):
    base_z = ring_index * CILIO_SPACING          # 120 unidades entre anéis
    
    # Rotação espiral: cada anel gira 30° em relação ao anterior
    offset_anel = ring_index * math.radians(30)
    
    # Posição angular = base + espiral + aleatoriedade
    angle = (cilio_index / CILIOS_PER_RING) * tau + offset_anel + random(-0.15, 0.15)
    
    length = random(CILIO_LEN * 0.5, CILIO_LEN)  # 55–110 unidades
    phase  = random(0, tau)                        # Fase inicial aleatória
```

### Visualização da Distribuição

```
Anel 0:  ×     ×     ×     ×     (0°, 90°, 180°, 270°)
Anel 1:    ×     ×     ×     ×   (30°, 120°, 210°, 300°)
Anel 2:      ×     ×     ×     × (60°, 150°, 240°, 330°)
...
```

A espiral garante que os cílios **nunca se alinham** em colunas, criando um campo mais orgânico e desafiador.

---

## Geração de Células

```python
def make_cell(cell_index):
    rng = random.Random((cell_index * 1234567 + SEED) & 0xFFFFFFFF)
    z   = CELL_SPACING + cell_index * CELL_SPACING   # Espaçadas de 250 unidades
    r   = rng.uniform(TUNNEL_RADIUS * 0.20, TUNNEL_RADIUS * 0.70)  # 44–154 unidades do centro
    a   = rng.uniform(0, math.tau)                                   # Ângulo aleatório
    return z, r * math.cos(a), r * math.sin(a)
```

### Restrições
- **Distância mínima do centro:** 20% do raio do túnel (evita spawn no centro)
- **Distância máxima do centro:** 70% do raio (evita spawn perto da parede/cílios)
- **Espaçamento fixo:** 250 unidades entre células

### Movimento Dinâmico

As células não são estáticas — elas flutuam em padrão Lissajous:

```python
vel_x = 1.3 + (idx % 3) * 0.2   # Velocidade X: 1.3, 1.5 ou 1.7
vel_y = 1.1 + (idx % 2) * 0.3   # Velocidade Y: 1.1 ou 1.4
amp   = 45.0                      # Amplitude do movimento

dinamico_cx = base_cx + sin(t * vel_x + idx) * amp
dinamico_cy = base_cy + cos(t * vel_y + idx * 0.8) * amp
```

---

## Geração de Obstáculos (Fase 2)

```python
def make_obstacle(n):
    rng = random.Random((n * 2654435761) & 0xFFFFFFFF)
    rad = rng.uniform(1.9, 3.1)           # Raio: 1.9–3.1
    lim = TUNNEL_HALF - rad - 0.4         # Margem de segurança
    cx  = rng.uniform(-lim, lim)          # Posição X
    cy  = rng.uniform(-lim, lim)          # Posição Y
    typ = rng.uniform(0.0, 6.28)          # Fase de morphing
    return OB_START + n * SPACING, cx, cy, rad, typ
```

### Restrições
- **Raio:** Entre 1.9 e 3.1 unidades
- **Posição:** Limitada para que o obstáculo caiba no túnel (`TUNNEL_HALF - rad - 0.4`)
- **Espaçamento:** Fixo em 16 unidades no eixo Z
- **Início:** Primeiro obstáculo a 28 unidades

---

## Sistema de Streaming (Visibilidade)

O sistema só gera e processa elementos que estão **dentro da janela de visibilidade** da câmera:

### Cílios

```python
def collect_visible_cilios():
    z0 = cam_z_f1 - 50.0          # 50 atrás da câmera
    z1 = cam_z_f1 + VIEW_DIST     # 1200 à frente
    r0 = max(0, int(z0 // CILIO_SPACING))
    r1 = int(z1 // CILIO_SPACING) + 1
    return [get_cilio(ri, ci) for ri in range(r0, r1) for ci in range(CILIOS_PER_RING)]
```

**Cílios visíveis por frame:** ~10 anéis × 4 cílios = ~40 cílios

### Células

```python
def collect_visible_cells():
    z0 = cam_z_f1 - 50.0
    z1 = cam_z_f1 + VIEW_DIST
    i0 = max(0, int((z0 - CELL_SPACING) // CELL_SPACING))
    i1 = int((z1 - CELL_SPACING) // CELL_SPACING) + 2
    # Filtra células já coletadas (collected_cells set)
```

**Células visíveis por frame:** ~5–6 (espaçamento de 250 em janela de 1200)

### Obstáculos (Fase 2)

```python
def collect_obstacles():
    base = int((cam_z_f2 - OB_START) // SPACING)
    # Coleta até MAX_OBS (8) obstáculos com relz entre -1 e 150
```

**Obstáculos visíveis:** Até 8 simultâneos (limite do shader)

---

## Cache e Invalidação

### Cílios (Persistente)

```python
cilio_cache = {}   # (ring, ci) → parâmetros
cilio_nodes = {}   # (ring, ci) → nós de física
```

- **Criados** na primeira vez que são visíveis
- **Nunca removidos** durante a partida
- **Limpos** apenas ao reiniciar (`reset_fase_1()`)

### Células (Via Set)

```python
collected_cells = set()   # Índices de células infectadas
```

Células infectadas são adicionadas ao set e filtradas em `collect_visible_cells()`.

### Obstáculos (Sem Cache)

Obstáculos da Fase 2 são **recalculados a cada frame** pois o custo é trivial (max 8 chamadas a `make_obstacle()`).

---

## Diagrama do Fluxo de Streaming

```
Câmera Z = 500
                    │
    ┌───────────────┼───────────────────────────────┐
    │  z=450        │                        z=1700 │
    │  (atrás)      │ câmera                (frente)│
    │               │                               │
    │  ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● │  ← Cílios visíveis
    │     ◆     ◆     ◆     ◆     ◆     ◆          │  ← Células visíveis
    │                                               │
    └───────────────────────────────────────────────┘
    
    Elementos fora dessa janela NÃO são processados.
```
