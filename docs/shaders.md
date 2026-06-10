# 🎨 Shaders GLSL

## Visão Geral

O projeto utiliza dois shaders GLSL ES para a renderização da Fase 2:
1. **Vertex Shader (VERT)** — Posicionamento dos vértices em tela cheia
2. **Fragment Shader (FRAG)** — Raymarching SDF para renderizar a cena inteira

---

## Vertex Shader

```glsl
precision highp float;
attribute vec3 aPosition;

void main() {
    vec4 p = vec4(aPosition, 1.0);
    p.xy = p.xy * 2.0 - 1.0;    // Mapeia [0,1] → [-1,1] (clip space)
    gl_Position = p;
}
```

### Explicação
- **`aPosition`:** Coordenadas do vértice fornecidas pelo p5.js ao chamar `rect(0, 0, W, H)`.
- **`p.xy * 2.0 - 1.0`:** Converte as coordenadas de textura (0 a 1) para o clip space de OpenGL (-1 a +1).
- O retângulo cobre a tela inteira, permitindo que o fragment shader processe cada pixel.

---

## Fragment Shader — Estrutura

```
┌─────────────────────────────────────────────┐
│                 UNIFORMS                     │
│  Dados recebidos da CPU (Python)             │
├─────────────────────────────────────────────┤
│             SDFs PRIMITIVAS                  │
│  sdSphere, sdBox, sdTorus                    │
├─────────────────────────────────────────────┤
│            FUNÇÕES DE CENA                   │
│  obstacleSDF, tunnelSDF, mapScene            │
├─────────────────────────────────────────────┤
│            ILUMINAÇÃO                        │
│  calcNormal, tunnelColor                     │
├─────────────────────────────────────────────┤
│              main()                          │
│  Raymarching + composição final              │
└─────────────────────────────────────────────┘
```

---

## Uniforms — Interface CPU ↔ GPU

```glsl
uniform vec2  uResolution;        // Tamanho do canvas em pixels
uniform float uTime;              // Tempo em segundos (animação)
uniform float uCamZ;              // Posição Z da câmera (mod 64)
uniform vec2  uPlayer;            // Deslocamento lateral (x, y)
uniform int   uObCount;           // Número de obstáculos ativos (0–8)
uniform vec3  uObRel[MAX_OBS];    // Posições relativas dos obstáculos
uniform float uObRad[MAX_OBS];    // Raios dos obstáculos
uniform float uObType[MAX_OBS];   // Tipo/fase de animação
uniform float uHit;               // Flash de colisão (0.0–1.0)
```

### `uCamZ` — Módulo 64

Para evitar problemas de precisão numérica com floats muito grandes (a câmera avança infinitamente), `uCamZ` usa módulo 64:

```python
prog.setUniform("uCamZ", float(cam_z_f2 % RIDGE_MOD))  # RIDGE_MOD = 64
```

---

## Função `rot()` — Rotação 2D

```glsl
mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}
```

Retorna uma **matriz de rotação 2D** usada para girar os obstáculos nos planos XY e XZ.

---

## Função `obstacleSDF()` — Morphing de Formas

```glsl
float obstacleSDF(vec3 p, vec3 center, float r, float typ) {
    vec3 rp = p - center;
    float ph = typ + uTime * 0.6;    // Fase única por obstáculo
    
    rp.xy = rot(ph * 0.7) * rp.xy;   // Rotação plano XY
    rp.xz = rot(ph * 0.5) * rp.xz;   // Rotação plano XZ
    
    float es = sdSphere(rp, r);                    // Esfera
    float cu = sdBox(rp, vec3(r * 0.78));          // Cubo
    float to = sdTorus(rp, vec2(r*0.70, r*0.32));  // Toro
    
    // Mistura animada: pesos oscilam com o tempo
    float a = 0.5 + 0.5 * sin(ph);
    float b = 0.5 + 0.5 * sin(ph * 0.73 + 2.1);
    float m = mix(es, cu, a);       // Esfera ↔ Cubo
    return mix(m, to, b);           // (Esfera/Cubo) ↔ Toro
}
```

### Visualização do Morphing

```
t=0.0    t=0.25     t=0.5      t=0.75     t=1.0
  ●    →  ◐     →    ■     →    ◑     →    ●
Esfera   Mix     Cubo/Toro   Mix       Esfera
```

---

## Função `tunnelSDF()` — Túnel Quadrado Infinito

```glsl
float tunnelSDF(vec3 p) {
    float wx = p.x + uPlayer.x;
    float wy = p.y + uPlayer.y;
    return TUNNEL_HALF - max(abs(wx), abs(wy));
}
```

- **Dentro do túnel:** Retorna valor **positivo** (distância até a parede)
- **Na parede:** Retorna **0**
- **Fora:** Retorna **negativo**

O deslocamento do jogador (`uPlayer`) é aplicado à posição do ponto, não à câmera, criando a ilusão de movimento lateral.

---

## Função `tunnelColor()` — Textura Procedural do Túnel

```glsl
vec3 tunnelColor(vec3 p) {
    float wz = p.z + uCamZ;
    
    // Grade luminosa (linhas cruzadas)
    float gx = smoothstep(0.06, 0.0, abs(fract(wz * 0.25) - 0.5) - 0.46);
    float gy = smoothstep(0.06, 0.0, abs(fract((wx+wy) * 0.5) - 0.5) - 0.46);
    
    vec3 base = vec3(0.75, 0.40, 0.30);   // Rosa/nariz
    vec3 glow = vec3(0.9, 0.6, 0.5) * (gx + gy);
    
    // Pulso correndo pelo túnel
    glow += vec3(0.8, 0.4, 0.3) * smoothstep(...) * 0.5;
    
    return base + glow;
}
```

### Efeitos Visuais
1. **Grade luminosa:** Linhas finas ao longo de Z e na diagonal XY
2. **Cor base:** Rosa/salmão (simula mucosa)
3. **Pulso:** Onda de luz correndo pelo túnel (`sin(p.z * 0.15 - uTime * 3.0)`)

---

## `main()` — Loop de Raymarching

```glsl
void main() {
    // 1. Calcular UV normalizado
    vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;
    
    // 2. Configurar raio
    vec3 ro = vec3(0.0);                    // Origem: câmera na posição (0,0,0)
    vec3 rd = normalize(vec3(uv, 1.45));    // Direção: FOV ≈ 70°
    
    // 3. Marchar o raio (até 90 passos)
    float t = 0.0;
    for(int i = 0; i < 90; i++) {
        vec3 p = ro + rd * t;
        float d = mapScene(p, mat);
        if(d < 0.002) { hit = true; break; }
        t += d;
        if(t > 170.0) break;
    }
    
    // 4. Colorir o pixel
    if(hit) {
        // Calcular normal + iluminação
        // Aplicar cor do material (túnel ou obstáculo)
        // Aplicar névoa
    } else {
        // Fundo: espaço + estrelas procedurais
    }
    
    // 5. Flash de colisão
    col = mix(col, vec3(0.9, 0.05, 0.05), uHit * 0.6);
    
    // 6. Correção gamma
    col = pow(col, vec3(0.4545));
    gl_FragColor = vec4(col, 1.0);
}
```

### Parâmetros do Raymarching

| Parâmetro | Valor | Descrição |
|---|---|---|
| Passos máximos | 90 | Limite de iterações por raio |
| Threshold de hit | 0.002 | Precisão da superfície |
| Distância máxima | 170.0 | Corte de distância (background) |
| FOV | ~70° | Controlado pelo `1.45` na direção do raio |

---

## Estrelas Procedurais (Background)

```glsl
vec2 sc = floor(rd.xy * 90.0);   // Grade 90×90 no espaço de direção
float h = fract(sin(dot(sc, vec2(12.9898, 78.233))) * 43758.5453);
col += smoothstep(0.995, 1.0, h) * vec3(0.9);
```

Usa uma **função hash** clássica para gerar estrelas esparsas no fundo.

---

## Correção Gamma

```glsl
col = pow(col, vec3(0.4545));   // gamma = 1/2.2 ≈ 0.4545
```

Converte de **linear** para **sRGB** para exibição correta no monitor.
