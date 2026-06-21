# 🦠 RETROVÍRUS

> **Trabalho Final — Computação Gráfica (2026/1)**  
> Um jogo interativo 3D construído inteiramente com **Python (Py5Script)** e **WebGL/GLSL**, explorando técnicas de computação gráfica em tempo real.

---

## 📖 Sobre o Projeto

**RETROVÍRUS** é um jogo educativo e interativo que simula a jornada de um vírus pelo corpo humano. O jogador controla um retrovírus que precisa atravessar o **túnel epitelial** (tecido nasal), desviando de cílios e infectando células, para então entrar na **corrente sanguínea** em uma fuga frenética por um tubo vascular renderizado inteiramente via **raymarching SDF**.

O projeto foi desenvolvido como trabalho final da disciplina de Computação Gráfica, demonstrando na prática conceitos fundamentais como:

- Renderização 3D em tempo real (WebGL)
- Curvas de Bézier cúbicas para modelagem orgânica
- Raymarching com Signed Distance Functions (SDF)
- Shaders GLSL (vertex + fragment)
- Geração procedural de cenários
- Simulação física simplificada (sistema de chicote)
- Detecção de colisão 3D

---

## 🎮 Gameplay

### Fase 1 — Túnel Epitelial
O jogador navega por um túnel cilíndrico que representa o tecido epitelial nasal. Deve desviar dos **cílios** (modelados como curvas de Bézier 3D com simulação física de chicote) e coletar **células** para infectá-las.

- **Objetivo:** Infectar **5 células** para avançar à Fase 2
- **Perigo:** Colidir com a ponta de um cílio encerra o jogo
- **Movimentação:** Livre em todos os eixos dentro do túnel

### Fase 2 — Tubo Sanguíneo
Um *endless runner* dentro de um vaso sanguíneo, renderizado completamente por **raymarching SDF** em um fragment shader GLSL. Obstáculos abstratos (morphing entre esferas, cubos e toros) surgem pelo caminho.

- **Objetivo:** Sobreviver o máximo possível, acumulando distância
- **Dificuldade:** A velocidade aumenta progressivamente
- **Visual:** Cenário inteiro calculado por raio no GPU

---

## 🕹️ Controles

| Ação | Teclas |
|---|---|
| Mover lateralmente | `← →` ou `A` `D` |
| Mover verticalmente | `↑ ↓` ou `W` `S` |
| Subir (Fase 1) | `Espaço` |
| Descer (Fase 1) | `Ctrl` |
| Avançar / Recuar (Fase 1) | `W` / `S` |
| Iniciar / Reiniciar | `Espaço` ou qualquer tecla de movimento |
| Pular para Fase 2 (debug) | `Enter` |

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Uso |
|---|---|
| **Python 3 (Py5Script / Pyodide)** | Lógica do jogo, física, geração procedural |
| **p5.js (WebGL)** | Renderização 3D (Fase 1), canvas, HUD |
| **GLSL ES** | Vertex + Fragment Shaders (Fase 2) |
| **Raymarching SDF** | Renderização volumétrica do túnel sanguíneo |
| **Curvas de Bézier** | Modelagem e animação dos cílios |

---

## 🚀 Como Executar

### Pré-requisitos
- Navegador moderno com suporte a **WebGL** (Chrome, Firefox, Edge)
- Servidor local ou ambiente compatível com **Py5Script**

### Execução
1. Clone o repositório:
   ```bash
   git clone https://github.com/hugo-antunes19/Final-CG-20261.git
   cd Final-CG-20261
   ```

2. Abra o projeto em um ambiente compatível com **Py5Script** (PyScript + p5.js).  
   O arquivo principal é o [`sketch.py`](sketch.py).

3. O jogo será carregado no navegador. Pressione **Espaço** para começar!

---

## 📂 Estrutura do Projeto

```
Final-CG-20261/
├── sketch.py           # Código-fonte principal do jogo (~1035 linhas)
├── README.md           # Este arquivo
└── docs/
    ├── arquitetura.md          # Arquitetura geral e fluxo do programa
    ├── fase1_tunel_epitelial.md # Detalhes da Fase 1
    ├── fase2_tubo_sanguineo.md  # Detalhes da Fase 2 (Raymarching)
    ├── shaders.md               # Documentação dos shaders GLSL
    ├── fisica_cilios.md         # Sistema de física dos cílios
    └── geracao_procedural.md    # Geração procedural de cenários
```

---

## 📚 Documentação

A documentação completa está disponível no diretório [`docs/`](docs/):

- [**Arquitetura**](docs/arquitetura.md) — Visão geral da estrutura, estados e fluxo do programa
- [**Fase 1 — Túnel Epitelial**](docs/fase1_tunel_epitelial.md) — Geometria 3D, cílios, células e colisão
- [**Fase 2 — Tubo Sanguíneo**](docs/fase2_tubo_sanguineo.md) — Raymarching SDF e obstáculos
- [**Shaders GLSL**](docs/shaders.md) — Vertex e Fragment Shaders explicados linha a linha
- [**Física dos Cílios**](docs/fisica_cilios.md) — Simulação de chicote com molas e amortecimento
- [**Geração Procedural**](docs/geracao_procedural.md) — Algoritmos de geração determinística de cenários

---

## 👥 Autores

- **Hugo Antunes** — [@hugo-antunes19](https://github.com/hugo-antunes19)

---

## 📄 Licença

Projeto acadêmico desenvolvido para a disciplina de **Computação Gráfica — 2026/1**.
