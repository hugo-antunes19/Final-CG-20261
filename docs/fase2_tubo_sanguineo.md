# 🩸 Fase 2 — Tubo Sanguíneo (Raymarching SDF)

## Conceito

A Fase 2 é um **endless runner** dentro de um vaso sanguíneo. Diferente da Fase 1, toda a cena é renderizada por um **fragment shader GLSL** usando a técnica de **raymarching com Signed Distance Functions (SDF)**. O jogador desvia de obstáculos abstratos que sofrem morphing contínuo entre formas geométricas.

---

## Raymarching — Como Funciona

### O Algoritmo

Raymarching é uma técnica de renderização onde, para cada pixel da tela, um **raio** é lançado da câmera em direção à cena. O raio avança em passos, e a cada passo consulta a **SDF (função de distância com sinal)** para saber a menor distância até qualquer superfície:

```
Para cada pixel:
  1. Calcular direção do raio (rd) baseado no UV da tela
  2. Posição inicial = câmera (ro)
  3. Repetir até 90 vezes:
     a. p = ro + rd * t
     b. d = distância_mais_proxima(p)
     c. Se d < 0.002 → ACERTOU uma superfície
     d. t += d (avança pela distância segura)
     e. Se t > 170 → Nada visível (fundo)
```

```glsl
for(int i = 0; i < 90; i++){
    vec3 p = ro + rd * t;
    float d = mapScene(p, mat);
    if(d < 0.002){ hit = true; break; }
    t += d;
    if(t > 170.0) break;
}
```

### Por que SDF?

SDFs permitem combinar formas complexas com operações simples:
- **União:** `min(a, b)` — junta duas formas
- **Interseção:** `max(a, b)` — mantém somente a parte em comum
- **Subtração:** `max(a, -b)` — recorta uma forma da outra
- **Mistura suave:** `mix(a, b, t)` — morphing entre formas

---

## SDFs Primitivas

### Esfera
```glsl
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}
```
A distância de um ponto `p` ao centro da esfera menos o raio.

### Caixa (Box)
```glsl
float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
```
Distância a uma caixa alinhada aos eixos com meia-dimensão `b`.

### Toro
```glsl
float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}
```
Um donut com raio maior `t.x` e raio do tubo `t.y`.

---

## Composição da Cena

### Túnel

O túnel da Fase 2 é um **cubo invertido infinito** (o jogador está dentro):

```glsl
float tunnelSDF(vec3 p) {
    float wx = p.x + uPlayer.x;
    float wy = p.y + uPlayer.y;
    return TUNNEL_HALF - max(abs(wx), abs(wy));
    // Positivo = dentro do túnel; negativo = na parede
}
```

`TUNNEL_HALF = 6.0` define a meia-largura do túnel quadrado.

### Obstáculos — Morphing

Cada obstáculo é uma **mistura animada** de esfera, cubo e toro:

```glsl
float obstacleSDF(vec3 p, vec3 center, float r, float typ) {
    vec3 rp = p - center;
    
    // Rotação para dar vida ao obstáculo
    rp.xy = rot(ph * 0.7) * rp.xy;
    rp.xz = rot(ph * 0.5) * rp.xz;
    
    // Três formas base
    float es = sdSphere(rp, r);
    float cu = sdBox(rp, vec3(r * 0.78));
    float to = sdTorus(rp, vec2(r * 0.70, r * 0.32));
    
    // Morphing animado
    float a = 0.5 + 0.5 * sin(ph);              // Peso esfera/cubo
    float b = 0.5 + 0.5 * sin(ph * 0.73 + 2.1); // Peso toro
    float m = mix(es, cu, a);
    return mix(m, to, b);
}
```

### Cena Completa

```glsl
float mapScene(vec3 p, out float mat) {
    float d = tunnelSDF(p);      // Distância ao túnel
    mat = 0.0;                    // Material: 0 = túnel
    
    for(int i = 0; i < MAX_OBS; i++) {
        float od = obstacleSDF(p, uObRel[i], uObRad[i], uObType[i]);
        if(od < d) {
            d = od;
            mat = 1.0;            // Material: 1 = obstáculo
        }
    }
    return d;
}
```

---

## Iluminação e Cores

### Cálculo de Normal

A normal da superfície é estimada por **diferenças finitas** da SDF:

```glsl
vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.0025, 0.0);
    return normalize(vec3(
        mapDist(p + e.xyy) - mapDist(p - e.xyy),
        mapDist(p + e.yxy) - mapDist(p - e.yxy),
        mapDist(p + e.yyx) - mapDist(p - e.yyx)
    ));
}
```

### Modelo de Iluminação

- **Difusa:** `clamp(dot(n, lig), 0, 1)` — Luz direcional `(0.4, 0.7, -0.5)`
- **Ambiente:** `0.25 + 0.25 * n.y` — Ambiente hemisférico
- **Fresnel:** `pow(1 - dot(n, -rd), 3)` — Brilho nas bordas

### Cores

| Elemento | Técnica | Efeito |
|---|---|---|
| **Túnel** | Grade procedural + pulso | Linhas rosa luminosas correndo pelo túnel |
| **Obstáculo** | `cos(vec3 + p.z + uTime)` | Cores iridescentes que mudam com posição e tempo |
| **Fundo** | Estrelas procedurais | Pontos brancos via hash + threshold |
| **Névoa** | `1 - exp(-t * 0.018)` | Fade progressivo com a distância |
| **Flash de colisão** | `mix(col, vermelho, uHit)` | Tela vermelha ao colidir |

---

## Comunicação CPU ↔ GPU

Os dados são enviados da lógica Python para o shader via **uniforms**:

| Uniform | Tipo | Descrição |
|---|---|---|
| `uResolution` | `vec2` | Resolução da tela (900×600) |
| `uTime` | `float` | Tempo em segundos |
| `uCamZ` | `float` | Posição Z da câmera (mod 64) |
| `uPlayer` | `vec2` | Deslocamento lateral do jogador |
| `uObCount` | `int` | Número de obstáculos ativos |
| `uObRel[8]` | `vec3[]` | Posição relativa dos obstáculos |
| `uObRad[8]` | `float[]` | Raio de cada obstáculo |
| `uObType[8]` | `float[]` | Tipo/fase de animação de cada obstáculo |
| `uHit` | `float` | Intensidade do flash de colisão (0–1) |

```python
prog.setUniform("uObRel", _to_js([float(v) for v in rel]))
```

---

## Progressão de Dificuldade

A velocidade aumenta linearmente com a distância:

```python
speed = min(60.0, 18.0 + cam_z_f2 * 0.02)
```

- **Velocidade inicial:** 18 unidades/s
- **Velocidade máxima:** 60 unidades/s
- **Aceleração:** +0.02 por unidade percorrida

---

## Geração de Obstáculos

Os obstáculos são gerados proceduralmente no eixo Z, com posição e tamanho determinísticos:

```python
def make_obstacle(n):
    rng = Random((n * 2654435761) & 0xFFFFFFFF)
    rad = rng.uniform(1.9, 3.1)           # Raio aleatório
    lim = TUNNEL_HALF - rad - 0.4         # Limite para caber no túnel
    cx  = rng.uniform(-lim, lim)          # Posição X
    cy  = rng.uniform(-lim, lim)          # Posição Y
    typ = rng.uniform(0.0, 6.28)          # Fase de morphing
    return OB_START + n * SPACING, cx, cy, rad, typ
```

- **`SPACING = 16.0`** — Distância entre obstáculos
- **`OB_START = 28.0`** — Primeiro obstáculo aparece a 28 unidades
- **Até 8 obstáculos** visíveis simultâneos no shader
