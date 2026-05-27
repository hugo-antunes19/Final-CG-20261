// ===========================================================================
//  VERTEX SHADER  -  quad de tela cheia
//  aPosition chega normalizado (0..1); mapeamos direto para clip space
//  (-1..1) para cobrir toda a tela. O raymarching e feito no fragment.
// ===========================================================================
precision highp float;

attribute vec3 aPosition;

void main() {
  vec4 p = vec4(aPosition, 1.0);
  p.xy = p.xy * 2.0 - 1.0;
  gl_Position = p;
}
