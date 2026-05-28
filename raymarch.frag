// ===========================================================================
//  FRAGMENT SHADER  —  Raymarching (cometas SDF) + Galáxia Ultra-Realista
//
//  Obstáculos: núcleo rochoso-gelado com coma, jatos de gás e cauda em
//              espaço de ecrã — aparecem como cometas reais.
//  Fundo:      Via Láctea (FBM), nebulosas Hα / OIII / reflexão,
//              campo estelar multicamada com cores espectrais e spikes de
//              difração, streaks de warp alongados radialmente.
// ===========================================================================
precision highp float;
#define MAX_OBS 8

uniform vec2  uResolution;
uniform float uTime;
uniform float uWarp;
uniform vec3  uObRel[MAX_OBS];
uniform float uObRad[MAX_OBS];
uniform float uObType[MAX_OBS];
uniform float uHit;

// ===========================================================================
//  SDFs — inalterado (colisão = geometria 3D real)
// ===========================================================================
float sdSphere(vec3 p, float r){ return length(p)-r; }
float sdBox(vec3 p, vec3 b){
  vec3 q=abs(p)-b;
  return length(max(q,0.0))+min(max(q.x,max(q.y,q.z)),0.0);
}
float sdTorus(vec3 p, vec2 t){
  vec2 q=vec2(length(p.xz)-t.x,p.y);
  return length(q)-t.y;
}
mat2 rot(float a){ float c=cos(a),s=sin(a); return mat2(c,-s,s,c); }

float obstacleSDF(vec3 p, vec3 center, float r, float typ){
  vec3 rp=p-center;
  float ph=typ+uTime*0.6;
  rp.xy=rot(ph*0.7)*rp.xy; rp.xz=rot(ph*0.5)*rp.xz;
  float es=sdSphere(rp,r);
  float cu=sdBox(rp,vec3(r*0.78));
  float to=sdTorus(rp,vec2(r*0.70,r*0.32));
  float a=0.5+0.5*sin(ph), b=0.5+0.5*sin(ph*0.73+2.1);
  return mix(mix(es,cu,a),to,b);
}

#define OBS(i) ob=min(ob,obstacleSDF(p,uObRel[i],uObRad[i],uObType[i]))
float mapScene(vec3 p, out float mat){
  mat=1.0;
  float ob=obstacleSDF(p,uObRel[0],uObRad[0],uObType[0]);
  OBS(1);OBS(2);OBS(3);OBS(4);OBS(5);OBS(6);OBS(7);
  return ob;
}
float mapDist(vec3 p){ float m; return mapScene(p,m); }
vec3 calcNormal(vec3 p){
  vec2 e=vec2(0.0025,0.0);
  return normalize(vec3(
    mapDist(p+e.xyy)-mapDist(p-e.xyy),
    mapDist(p+e.yxy)-mapDist(p-e.yxy),
    mapDist(p+e.yyx)-mapDist(p-e.yyx)));
}

// ===========================================================================
//  GALÁXIA — funções auxiliares
// ===========================================================================
float hash11(float n){ return fract(sin(n*127.1)*43758.5453); }
float hash21(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
vec2  hash22(vec2 p) {
  vec2 q=vec2(dot(p,vec2(127.1,311.7)),dot(p,vec2(269.5,183.3)));
  return fract(sin(q)*43758.5453);
}

float smoothNoise(vec2 p){
  vec2 i=floor(p), f=fract(p);
  f=f*f*(3.0-2.0*f);
  float a=hash21(i), b=hash21(i+vec2(1,0)), c=hash21(i+vec2(0,1)), d=hash21(i+vec2(1,1));
  return mix(mix(a,b,f.x),mix(c,d,f.x),f.y);
}

// FBM 5 oitavas — nuvens de gás e estrutura da Via Láctea
float fbm(vec2 p){
  float v=0.0,a=0.5;
  for(int i=0;i<5;i++){ v+=a*smoothNoise(p); p=p*2.13+vec2(31.41,27.18); a*=0.5; }
  return v;
}

// Cor estelar pelo tipo espectral O→B→A→F→G→K→M
vec3 starColor(float t){
  vec3 ob =vec3(0.55,0.68,1.00);
  vec3 af =vec3(1.00,1.00,0.96);
  vec3 g  =vec3(1.00,0.88,0.50);
  vec3 km =vec3(1.00,0.42,0.12);
  vec3 c=mix(ob,af,smoothstep(0.0,0.3,t));
  c=mix(c,g,smoothstep(0.3,0.6,t));
  return mix(c,km,smoothstep(0.6,1.0,t));
}

// Camada de estrelas com posição sub-célula + glow gaussiano + cintilação
vec3 starLayer(vec2 dir, float scale, float thresh){
  vec2 g=floor(dir*scale), f=fract(dir*scale);
  float h=hash21(g);
  float brt=max(0.0,(h-thresh)/(1.0-thresh)); brt*=brt;
  vec2 pos=hash22(g+0.5);
  float d=length(f-pos)*scale;
  float twinkle=1.0+0.07*sin(uTime*2.5+hash21(g)*47.3);
  float core=exp(-d*d*1400.0), glow=exp(-d*d*55.0)*0.13;
  return (core+glow)*brt*twinkle*starColor(hash21(g+vec2(37.1,91.3)));
}

// Estrela muito brilhante com spikes de difração (como telescópios reais)
vec3 brightStar(vec2 dir, float scale, float thresh){
  vec2 g=floor(dir*scale), f=fract(dir*scale);
  float h=hash21(g);
  float brt=max(0.0,(h-thresh)/(1.0-thresh)); brt=brt*brt*brt;
  vec2 pos=hash22(g+0.5);
  vec2 d=(f-pos)*scale;
  float dist=length(d);
  float core=exp(-dist*dist*160.0);
  float glow=exp(-dist*dist*5.5)*0.38;
  // Cruz de difração (4 spikes horizontais + diagonais a 45°)
  float sx=exp(-d.y*d.y*6000.0)*exp(-abs(d.x)*2.0);
  float sy=exp(-d.x*d.x*6000.0)*exp(-abs(d.y)*2.0);
  float sd1=exp(-(d.x-d.y)*(d.x-d.y)*3000.0)*exp(-abs(d.x+d.y)*2.5)*0.5;
  float sd2=exp(-(d.x+d.y)*(d.x+d.y)*3000.0)*exp(-abs(d.x-d.y)*2.5)*0.5;
  float spikes=(sx+sy+sd1+sd2)*0.40;
  float twinkle=1.0+0.13*sin(uTime*1.8+hash21(g)*31.7);
  return (core+glow+spikes)*brt*twinkle*starColor(hash21(g+vec2(37.1,91.3)));
}

// ===========================================================================
//  COMETA — efeitos em espaço de ecrã (coma + cauda iônica)
// ===========================================================================
void addCometFX(inout vec3 col, vec2 uv, vec3 cp, float cr){
  // Ativo apenas se o cometa está à frente e tem raio real
  float vis=step(0.5,cp.z)*step(cp.z,105.0)*step(0.01,cr);

  float invZ=1.45/max(0.1,cp.z);
  vec2  spos=cp.xy*invZ;          // posição no ecrã (NDC)
  float srad=cr*invZ;             // raio aparente
  vec2  dv=uv-spos;
  float lenD=length(dv);

  // --- Coma: duas camadas (interna quente + externa fria) ---
  float inner=exp(-lenD*lenD/(srad*srad*3.5+0.00001));
  float outer=exp(-lenD*lenD/(srad*srad*20.0+0.00001));

  // --- Cauda: direcção radial para fora do centro do ecrã ---
  // (em 3D a cauda aponta para a câmara → em projecção perspectiva
  //  aparece radiando para fora a partir da posição do cometa)
  float lenSpos=max(0.001,length(spos));
  vec2  tDir=spos/lenSpos;

  float along =dot(dv, tDir);
  float perp  =dot(dv, vec2(-tDir.y,tDir.x));

  float tailStart=srad*0.75;
  float tailLen  =0.20+srad*3.8;
  float coneW    =srad*0.32+max(0.0,along-tailStart)*0.09;

  float tail=step(tailStart,along)
            *exp(-perp*perp/(coneW*coneW+0.00001))
            *exp(-max(0.0,along-tailStart)/(tailLen+0.0001));

  // Cor: coma azul-branca (poeira + gás), cauda azul (ião)
  col+=vis*(inner*0.55*vec3(0.88,0.97,1.00)
           +outer*0.22*vec3(0.48,0.73,1.00)
           +tail *0.38*vec3(0.28,0.60,1.00));
}

// Brilho 3D de quasi-miss (o raio passa perto do cometa sem colidir)
vec3 nearGlow(vec3 rd, vec3 ctr, float cr){
  float vis=step(0.01,cr)*step(0.5,ctr.z);
  float tcl=max(0.0,dot(ctr,rd));
  float d3=length(ctr-tcl*rd);
  float g=exp(-d3*d3/(max(0.0001,cr*cr)*9.0))*vis;
  return g*vec3(0.12,0.50,1.00)*0.28;
}

// ===========================================================================
//  FUNDO GALÁTICO
// ===========================================================================
vec3 background(vec3 rd, vec2 uv){

  // 1. Espaço profundo
  vec3 col=vec3(0.004,0.002,0.012);

  // 2. Faixa da Via Láctea (plano galáctico inclinado ~15°)
  float gp    =rd.y*0.80-rd.x*0.22;
  float mwB   =exp(-gp*gp*5.2);
  float mwFbm =fbm(rd.xz*1.6+vec2(uTime*0.003,0.0));
  float mw    =mwB*(0.28+0.72*mwFbm);
  col+=mw*vec3(0.085,0.065,0.16);          // halo azul-púrpura difuso
  col+=mw*mwB*vec3(0.055,0.038,0.018);     // núcleo levemente mais quente

  // Pistas de poeira escura dentro da faixa (escurecem levemente)
  float dust=fbm(rd.xz*3.5+vec2(1.2,0.0))*mwB;
  col*=1.0-dust*0.18;

  // 3. Nebulosas
  vec2 nb=rd.xy*2.0+rd.z*0.28;

  // Emissão Hα — hidrogénio ionizado (vermelho/magenta)
  float em=pow(max(0.0,fbm(nb*1.05+vec2(uTime*0.004,1.8))),2.1);
  col+=em*vec3(0.32,0.03,0.11);

  // OIII — oxigénio ionizado (ciano/teal, mais quente)
  float oiii=pow(max(0.0,fbm(nb*0.78+vec2(3.5,uTime*0.003))),2.7);
  col+=oiii*vec3(0.02,0.17,0.26);

  // Reflexão — poeira espalhando luz estelar (azul-púrpura frio)
  float ref=pow(max(0.0,fbm(nb*1.4+vec2(-2.0,0.9))),3.0);
  col+=ref*vec3(0.04,0.05,0.22)*0.60;

  // 4. Campo estelar — 3 camadas + camada de estrelas brilhantes c/ spikes
  vec2 sd=rd.xy+rd.z*0.09;
  float mwBoost=1.0+mwB*1.9;

  col+=starLayer(sd,148.0,0.921)*0.27*mwBoost;   // fundo: denso e fraco
  col+=starLayer(sd, 88.0,0.941)*0.56*mwBoost;   // médias
  col+=starLayer(sd, 42.0,0.959)*0.98;            // brilhantes
  col+=brightStar(sd, 19.0,0.973)*1.75;           // muito brilhantes + spikes

  // 5. Efeitos dos cometas sobre o fundo (coma + cauda)
  addCometFX(col,uv,uObRel[0],uObRad[0]);
  addCometFX(col,uv,uObRel[1],uObRad[1]);
  addCometFX(col,uv,uObRel[2],uObRad[2]);
  addCometFX(col,uv,uObRel[3],uObRad[3]);
  addCometFX(col,uv,uObRel[4],uObRad[4]);
  addCometFX(col,uv,uObRel[5],uObRad[5]);
  addCometFX(col,uv,uObRel[6],uObRad[6]);
  addCometFX(col,uv,uObRel[7],uObRad[7]);

  // 6. Streaks de warp — cone radial, largura e velocidade variadas
  float br=0.0;
  for(int i=0;i<60;i++){
    float fi=float(i);
    float seed=hash11(fi*0.3183);
    float ang=seed*6.28318;
    float spd=0.7+hash11(fi*0.3183+100.0)*0.6;
    float t=fract(uWarp*spd+seed);

    vec2 sdir=vec2(cos(ang),sin(ang));
    vec2 spos=sdir*t*1.8;
    vec2 dv=uv-spos;

    float dPerp=dot(dv,vec2(-sdir.y,sdir.x));
    float dPara=dot(dv,sdir);
    float slen=0.025+hash11(fi*0.3183+200.0)*0.055;

    float s=smoothstep(0.0040,0.0,abs(dPerp))
           *smoothstep(slen,0.0,abs(dPara));
    br+=s*t*t;
  }
  col+=br*vec3(0.48,0.70,1.00);

  return col;
}

// ===========================================================================
//  main
// ===========================================================================
void main(){
  vec2 uv=(gl_FragCoord.xy-0.5*uResolution)/uResolution.y;
  vec3 ro=vec3(0.0);
  vec3 rd=normalize(vec3(uv,1.45));

  vec3 bg=background(rd,uv);

  // ---- Raymarching ----
  float t=0.0;
  float mat=0.0;
  bool hit=false;
  for(int i=0;i<80;i++){
    vec3 p=ro+rd*t;
    float d=mapScene(p,mat);
    if(d<0.002){ hit=true; break; }
    t+=d;
    if(t>160.0) break;
  }

  vec3 col;
  if(hit){
    // ---- Superfície do cometa: núcleo rochoso-gelado ----
    vec3 p=ro+rd*t;
    vec3 n=calcNormal(p);

    // Textura da superfície: rocha escura com manchas de gelo
    float craterNoise=0.5+0.5*sin(p.x*5.3+p.y*4.1)*cos(p.z*3.8+p.x*3.0);
    float iceNoise   =max(0.0,sin(p.x*9.1+uTime*0.9)*cos(p.y*8.4+uTime*0.7));

    vec3 rockCol=vec3(0.09,0.08,0.07);    // cometa real: albedo ~4% (muito escuro)
    vec3 iceCol =vec3(0.52,0.78,1.00);    // gelo sublimando (azul-branco)
    vec3 surfCol=rockCol+iceCol*(craterNoise*0.18+iceNoise*0.22);

    // Iluminação: sol atrás da câmara (viajamos em direção ao cometa)
    vec3 sunDir=normalize(vec3(0.0,0.0,-1.0));
    float dif =max(0.0,dot(n,-sunDir))*0.75;
    float fill=max(0.0,dot(n,normalize(vec3(0.4,0.5,0.3))))*0.10;
    float amb =0.05;

    // Fresnel: brilho da coma na silhueta (gás sublimando)
    float ndv =clamp(dot(n,-rd),0.0,1.0);
    float fre =pow(1.0-ndv,3.5);

    // Jatos de gás ativo (pontos de sublimação — azul ciano)
    float jet=pow(iceNoise,2.2)*0.45;
    vec3 gasCol=vec3(0.22,0.62,1.00);

    col =surfCol*(amb+dif+fill)
        +fre*gasCol*1.9     // auréola da coma na borda
        +jet*gasCol*0.55;   // jatos de gás ativo

    float fog=1.0-exp(-t*0.011);
    col=mix(col,bg,fog);

  } else {
    // ---- Miss: brilho volumétrico de quasi-miss (coma 3D) ----
    vec3 ng=nearGlow(rd,uObRel[0],uObRad[0])
           +nearGlow(rd,uObRel[1],uObRad[1])
           +nearGlow(rd,uObRel[2],uObRad[2])
           +nearGlow(rd,uObRel[3],uObRad[3])
           +nearGlow(rd,uObRel[4],uObRad[4])
           +nearGlow(rd,uObRel[5],uObRad[5])
           +nearGlow(rd,uObRel[6],uObRad[6])
           +nearGlow(rd,uObRel[7],uObRad[7]);
    col=bg+ng;
  }

  // Flash de colisão e correção de gama
  col=mix(col,vec3(0.9,0.05,0.05),uHit*0.6);
  col=pow(max(col,vec3(0.0)),vec3(0.4545));
  gl_FragColor=vec4(col,1.0);
}
