import { geometry, sunPosition } from './model.mjs';
const V={sub:(a,b)=>a.map((v,i)=>v-b[i]),dot:(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),cross:(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],norm:a=>{const n=Math.hypot(...a)||1;return a.map(v=>v/n);}};
const M={
  mul(a,b){const o=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)o[c*4+r]+=a[k*4+r]*b[c*4+k];return o;},
  perspective(fov,aspect,n,f){const t=1/Math.tan(fov/2);return new Float32Array([t/aspect,0,0,0,0,t,0,0,0,0,(f+n)/(n-f),-1,0,0,2*f*n/(n-f),0]);},
  ortho(l,r,b,t,n,f){return new Float32Array([2/(r-l),0,0,0,0,2/(t-b),0,0,0,0,-2/(f-n),0,-(r+l)/(r-l),-(t+b)/(t-b),-(f+n)/(f-n),1]);},
  look(eye,target,up=[0,1,0]){const z=V.norm(V.sub(eye,target)),x=V.norm(V.cross(up,z)),y=V.cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-V.dot(x,eye),-V.dot(y,eye),-V.dot(z,eye),1]);}
};
const vertexShader=`#version 300 es
precision highp float;
layout(location=0) in vec3 aPosition;layout(location=1) in vec3 aNormal;
layout(location=2) in vec4 aM0;layout(location=3) in vec4 aM1;layout(location=4) in vec4 aM2;layout(location=5) in vec4 aM3;
layout(location=6) in vec4 aColor;layout(location=7) in vec2 aMeta;
uniform mat4 uVP;uniform mat4 uLightVP;uniform float uExplode;
out vec3 vNormal;out vec3 vWorld;out vec4 vColor;out vec4 vShadow;flat out vec2 vMeta;
void main(){mat4 model=mat4(aM0,aM1,aM2,aM3);vec4 p=model*vec4(aPosition,1.0);p.y+=max(0.0,aMeta.x-1.0)*uExplode*2.8;
vWorld=p.xyz;vNormal=normalize(mat3(aM0.xyz/dot(aM0.xyz,aM0.xyz),aM1.xyz/dot(aM1.xyz,aM1.xyz),aM2.xyz/dot(aM2.xyz,aM2.xyz))*aNormal);
vColor=aColor;vMeta=aMeta;vShadow=uLightVP*p;gl_Position=uVP*p;}`;
const fragmentShader=`#version 300 es
precision highp float;
in vec3 vNormal;in vec3 vWorld;in vec4 vColor;in vec4 vShadow;flat in vec2 vMeta;
uniform sampler2D uShadow;uniform vec3 uSun;uniform vec3 uEye;uniform float uNight;uniform float uSelected;uniform float uShadows;
out vec4 outColor;
float shadowFactor(vec3 n){vec3 p=vShadow.xyz/vShadow.w*0.5+0.5;if(p.z>1.0||p.z<0.0||p.x<0.0||p.x>1.0||p.y<0.0||p.y>1.0)return 1.0;
float bias=max(0.0006*(1.0-dot(n,uSun)),0.00016),s=0.0;vec2 size=vec2(textureSize(uShadow,0));
for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)s+=(p.z-bias>texture(uShadow,p.xy+vec2(x,y)/size).r)?0.0:1.0;return s/9.0;}
void main(){vec3 n=normalize(vNormal);vec3 view=normalize(uEye-vWorld);float kind=vColor.a;vec3 base=pow(vColor.rgb,vec3(2.2));
float diffuse=max(dot(n,uSun),0.0);float shadow=mix(1.0,shadowFactor(n),uShadows);vec3 hemi=mix(vec3(0.20,0.22,0.19),vec3(0.69,0.76,0.78),n.y*0.5+0.5);
vec3 lit=base*(hemi*0.72+vec3(1.0,0.91,0.75)*diffuse*shadow*1.7);float fres=pow(1.0-max(dot(n,view),0.0),4.0);
if(kind>0.5&&kind<1.5){vec3 ref=reflect(-view,n);vec3 env=mix(vec3(0.19,0.30,0.29),vec3(0.70,0.80,0.81),smoothstep(-0.25,0.65,ref.y));
float streak=0.93+0.07*sin(ref.x*7.0+ref.z*4.0+ref.y*14.0);lit=mix(lit,env*streak,0.30+fres*0.40);lit*=0.85+shadow*0.15;
float sparkle=pow(max(dot(ref,uSun),0.0),110.0);lit+=sparkle*shadow*0.7;
float glow=step(0.43,fract(sin(dot(floor(vWorld.xz*0.7)+floor(vWorld.y*0.3),vec2(12.9,78.2)))*43758.5));
lit=mix(lit*0.2,vec3(0.98,0.64,0.27)*(.25+glow*.55),uNight*.8);
}else if(kind>1.5&&kind<2.5){vec3 halfV=normalize(uSun+view);lit+=vec3(0.30,0.25,0.17)*pow(max(dot(n,halfV),0.0),40.0)*shadow;}
if(kind>2.5&&kind<3.5){lit*=0.90;lit+=base*max(dot(-n,uSun),0.0)*0.18;}
if(kind>3.5)lit=base*(1.0+uNight*2.5);
if(kind<0.5||kind>1.5)lit*=mix(1.0,0.35,uNight);
if(uSelected>0.0&&abs(vMeta.x-uSelected)<0.1)lit=mix(lit,vec3(0.75,0.55,0.19),0.28);
float fog=1.0-exp(-pow(length(uEye-vWorld)*0.0018,2.0));lit=mix(lit,mix(vec3(0.78,0.79,0.74),vec3(0.09,0.13,0.18),uNight),fog);
lit=lit/(lit+vec3(0.55));outColor=vec4(pow(lit,vec3(1.0/2.2)),1.0);}`;
const shadowFragment=`#version 300 es\nprecision highp float;void main(){}`;
export class OfficeRenderer {
  constructor(canvas, scene) {
    this.canvas=canvas;this.gl=canvas.getContext('webgl2',{antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
    if(!this.gl)throw new Error('อุปกรณ์นี้ไม่รองรับ WebGL 2 กรุณาเปิดด้วย Safari, Chrome หรือ Edge รุ่นปัจจุบัน');
    const gl=this.gl;this.scene=scene;this.state={cutoff:14,explode:0,facade:true,landscape:true,interior:false,night:false,selected:0,auto:false,hour:9.5,day:264,shadows:true};
    this.camera={theta:0.66,phi:0.32,radius:140,target:[0,26,0]};this.goal={...this.camera,target:[...this.camera.target]};
    this.program=this.programFor(vertexShader,fragmentShader);this.shadowProgram=this.programFor(vertexShader,shadowFragment);
    this.locations=new Map();this.batches=[];this.pointerMap=new Map();this.shadowDirty=true;this.dirty=true;this.lastTime=0;
    const makeDepth=()=>{const tex=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,tex);gl.texImage2D(gl.TEXTURE_2D,0,gl.DEPTH_COMPONENT24,2048,2048,0,gl.DEPTH_COMPONENT,gl.UNSIGNED_INT,null);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);return tex;};
    this.depthTexture=makeDepth();this.fbo=gl.createFramebuffer();gl.bindFramebuffer(gl.FRAMEBUFFER,this.fbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.TEXTURE_2D,this.depthTexture,0);gl.drawBuffers([gl.NONE]);gl.readBuffer(gl.NONE);
    if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw new Error('Shadow framebuffer unavailable');gl.bindFramebuffer(gl.FRAMEBUFFER,null);
    gl.enable(gl.DEPTH_TEST);gl.enable(gl.CULL_FACE);gl.cullFace(gl.BACK);
    this.rebuild();this.bindInput();this.resizeObserver=new ResizeObserver(()=>{this.resize();});this.resizeObserver.observe(canvas);this.resize();
    canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();cancelAnimationFrame(this.raf);this.onError?.('WebGL context lost — กรุณาโหลดหน้าใหม่');});
    this.tick=this.tick.bind(this);this.raf=requestAnimationFrame(this.tick);
  }
  programFor(vs,fs){const gl=this.gl,p=gl.createProgram();for(const [type,src] of [[gl.VERTEX_SHADER,vs],[gl.FRAGMENT_SHADER,fs]]){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));gl.attachShader(p,s);gl.deleteShader(s);}gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(p));return p;}
  loc(program,name){if(!this.locations.has(program))this.locations.set(program,{});const cache=this.locations.get(program);if(!(name in cache))cache[name]=this.gl.getUniformLocation(program,name);return cache[name];}
  set(name,value){this.state[name]=value;if(['cutoff','facade','landscape','interior'].includes(name))this.rebuild();if(['explode','hour','day'].includes(name))this.shadowDirty=true;this.dirty=true;}
  replaceScene(scene){this.scene=scene;this.rebuild();}
  rebuild(){
    const gl=this.gl;
    for(const b of this.batches){gl.deleteVertexArray(b.vao);b.buffers.forEach(v=>gl.deleteBuffer(v));}
    this.batches=[];const groups=new Map();
    for(const o of this.scene.objects){if(o.floor>this.state.cutoff)continue;if(o.layer===7&&this.state.cutoff<14)continue;if(o.layer===3&&!this.state.facade)continue;if(o.layer===4&&!this.state.landscape)continue;if(o.layer===5&&!this.state.interior)continue;if(o.layer===2&&this.state.interior)continue;
      if(!groups.has(o.shape))groups.set(o.shape,[]);groups.get(o.shape).push(o);}
    for(const [shape,objects]of groups){const g=geometry(shape),vao=gl.createVertexArray(),buffers=[];gl.bindVertexArray(vao);
      const buffer=(target,data)=>{const b=gl.createBuffer();buffers.push(b);gl.bindBuffer(target,b);gl.bufferData(target,data,gl.STATIC_DRAW);return b;};
      buffer(gl.ARRAY_BUFFER,g.positions);gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,3,gl.FLOAT,false,0,0);
      buffer(gl.ARRAY_BUFFER,g.normals);gl.enableVertexAttribArray(1);gl.vertexAttribPointer(1,3,gl.FLOAT,false,0,0);
      buffer(gl.ELEMENT_ARRAY_BUFFER,g.indices);const data=new Float32Array(objects.length*22);
      objects.forEach((o,i)=>{const mat=this.scene.materials[o.material];data.set([...o.matrix,...mat.color,mat.kind,o.floor,o.layer],i*22);});
      buffer(gl.ARRAY_BUFFER,data);for(let k=0;k<4;k++){gl.enableVertexAttribArray(2+k);gl.vertexAttribPointer(2+k,4,gl.FLOAT,false,88,k*16);gl.vertexAttribDivisor(2+k,1);}
      gl.enableVertexAttribArray(6);gl.vertexAttribPointer(6,4,gl.FLOAT,false,88,64);gl.vertexAttribDivisor(6,1);gl.enableVertexAttribArray(7);gl.vertexAttribPointer(7,2,gl.FLOAT,false,88,80);gl.vertexAttribDivisor(7,1);
      this.batches.push({vao,buffers,count:g.indices.length,instances:objects.length});
    }
    gl.bindVertexArray(null);this.shadowDirty=true;this.dirty=true;
  }
  resize(){const dpr=Math.min(window.devicePixelRatio||1,1.8),r=this.canvas.getBoundingClientRect();const w=Math.round(r.width*dpr),h=Math.round(r.height*dpr);if(w&&h&&(this.canvas.width!==w||this.canvas.height!==h)){this.canvas.width=w;this.canvas.height=h;this.dirty=true;}}
  bindInput(){
    const c=this.canvas;
    c.addEventListener('contextmenu',e=>e.preventDefault());
    c.addEventListener('pointerdown',e=>{c.setPointerCapture(e.pointerId);this.pointerMap.set(e.pointerId,{x:e.clientX,y:e.clientY});this.down={x:e.clientX,y:e.clientY,time:performance.now()};this.state.auto=false;this.onInteraction?.();});
    c.addEventListener('pointermove',e=>{if(!this.pointerMap.has(e.pointerId))return;const prev=this.pointerMap.get(e.pointerId),dx=e.clientX-prev.x,dy=e.clientY-prev.y;
      if(this.pointerMap.size===2){const other=[...this.pointerMap.entries()].find(([id])=>id!==e.pointerId)[1];const old=Math.hypot(prev.x-other.x,prev.y-other.y),now=Math.hypot(e.clientX-other.x,e.clientY-other.y);this.goal.radius=Math.max(25,Math.min(240,this.goal.radius*old/Math.max(now,1)));this.pan(dx*0.35,dy*0.35);}
      else if(e.buttons===2||e.shiftKey){this.pan(dx,dy);}else{this.goal.theta-=dx*0.006;this.goal.phi=Math.max(0.05,Math.min(1.50,this.goal.phi+dy*0.004));}
      this.pointerMap.set(e.pointerId,{x:e.clientX,y:e.clientY});this.dirty=true;
    });
    const end=e=>{const clicked=this.pointerMap.size===1&&this.down&&Math.hypot(e.clientX-this.down.x,e.clientY-this.down.y)<5&&performance.now()-this.down.time<400;this.pointerMap.delete(e.pointerId);if(clicked)this.onPick?.(this.pick(e.clientX,e.clientY));};
    c.addEventListener('pointerup',end);c.addEventListener('pointercancel',e=>this.pointerMap.delete(e.pointerId));
    c.addEventListener('wheel',e=>{e.preventDefault();this.goal.radius=Math.max(25,Math.min(240,this.goal.radius*Math.exp(e.deltaY*0.001)));this.dirty=true;},{passive:false});
    c.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','=','Home'].includes(e.key)){e.preventDefault();if(e.key==='ArrowLeft')this.goal.theta+=.1;if(e.key==='ArrowRight')this.goal.theta-=.1;if(e.key==='ArrowUp')this.goal.phi=Math.min(1.5,this.goal.phi+.08);if(e.key==='ArrowDown')this.goal.phi=Math.max(.05,this.goal.phi-.08);if(e.key==='+'||e.key==='=')this.goal.radius*=.9;if(e.key==='-')this.goal.radius*=1.1;if(e.key==='Home')this.preset('hero');this.dirty=true;}});
  }
  pan(dx,dy){const k=this.goal.radius/750;this.goal.target[0]-=Math.cos(this.goal.theta)*dx*k;this.goal.target[2]+=Math.sin(this.goal.theta)*dx*k;this.goal.target[1]+=dy*k;}
  preset(name){const ex=this.state.explode,shift=ex*18;const presets={hero:[.66,.32,140+shift*2,[0,26+shift,0]],front:[0,.16,105+shift*2,[0,26+shift,0]],east:[Math.PI/2,.21,102+shift*2,[0,26+shift,0]],top:[.0,1.48,108+shift,[0,18+shift,0]],garden:[.2,.13,55,[0,36.5+shift,3]]};
    const p=presets[name]||presets.hero;this.goal={theta:p[0],phi:p[1],radius:p[2],target:[...p[3]]};this.state.auto=false;this.dirty=true;
  }
  eye(){const c=this.camera;return [c.target[0]+c.radius*Math.sin(c.theta)*Math.cos(c.phi),c.target[1]+c.radius*Math.sin(c.phi),c.target[2]+c.radius*Math.cos(c.theta)*Math.cos(c.phi)];}
  project(point){if(!this.vp)return null;const m=this.vp,p=[...point,1],out=[0,0,0,0];for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[r]+=m[k*4+r]*p[k];const rect=this.canvas.getBoundingClientRect();return {x:(out[0]/out[3]*.5+.5)*rect.width,y:(-out[1]/out[3]*.5+.5)*rect.height,visible:out[3]>0&&Math.abs(out[0]/out[3])<1&&Math.abs(out[1]/out[3])<1};}
  pick(clientX,clientY){const r=this.canvas.getBoundingClientRect(),nx=(clientX-r.left)/r.width*2-1,ny=1-(clientY-r.top)/r.height*2;const eye=this.eye(),f=V.norm(V.sub(this.camera.target,eye)),right=V.norm(V.cross(f,[0,1,0])),up=V.cross(right,f),t=Math.tan(36*Math.PI/360);const dir=V.norm(f.map((v,i)=>v+right[i]*nx*t*r.width/r.height+up[i]*ny*t));let best=Infinity,level=0;
    for(const floor of this.scene.floors){if(floor.level>this.state.cutoff)continue;const ey=(floor.level-1)*this.state.explode*2.8,min=[-floor.width/2,floor.y+ey,-floor.depth/2],max=[floor.width/2,floor.y+floor.height+ey,floor.depth/2];let near=0,far=Infinity;
      for(let i=0;i<3;i++){if(Math.abs(dir[i])<1e-8){if(eye[i]<min[i]||eye[i]>max[i]){near=Infinity;break;}}else{let a=(min[i]-eye[i])/dir[i],b=(max[i]-eye[i])/dir[i];if(a>b)[a,b]=[b,a];near=Math.max(near,a);far=Math.min(far,b);}}if(near<=far&&near<best){best=near;level=floor.level;}}
    return level;
  }
  draw(program,vp,lightVP){const gl=this.gl;gl.useProgram(program);gl.uniformMatrix4fv(this.loc(program,'uVP'),false,vp);gl.uniformMatrix4fv(this.loc(program,'uLightVP'),false,lightVP);gl.uniform1f(this.loc(program,'uExplode'),this.state.explode);for(const b of this.batches){gl.bindVertexArray(b.vao);gl.drawElementsInstanced(gl.TRIANGLES,b.count,gl.UNSIGNED_SHORT,0,b.instances);}gl.bindVertexArray(null);}
  render(){const gl=this.gl,eye=this.eye(),sun=sunPosition(this.state.hour,this.state.day),dir=V.norm([sun.direction[0],Math.max(.06,sun.direction[1]),sun.direction[2]]),lightTarget=[0,28+this.state.explode*20,0],lightEye=lightTarget.map((v,i)=>v+dir[i]*150);
    const ext=78+this.state.explode*15,lightVP=M.mul(M.ortho(-ext,ext,-ext,ext,10,310),M.look(lightEye,lightTarget,[0,0,-1]));
    if(this.shadowDirty&&this.state.shadows){gl.bindFramebuffer(gl.FRAMEBUFFER,this.fbo);gl.viewport(0,0,2048,2048);gl.clear(gl.DEPTH_BUFFER_BIT);gl.enable(gl.POLYGON_OFFSET_FILL);gl.polygonOffset(1.2,2);this.draw(this.shadowProgram,lightVP,lightVP);gl.disable(gl.POLYGON_OFFSET_FILL);this.shadowDirty=false;}
    gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.viewport(0,0,this.canvas.width,this.canvas.height);const night=this.state.night?1:0;gl.clearColor(...(night?[.10,.14,.18,1]:[.875,.876,.845,1]));gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    this.vp=M.mul(M.perspective(36*Math.PI/180,this.canvas.width/this.canvas.height,.3,600),M.look(eye,this.camera.target));gl.useProgram(this.program);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,this.depthTexture);gl.uniform1i(this.loc(this.program,'uShadow'),0);gl.uniform3fv(this.loc(this.program,'uSun'),dir);gl.uniform3fv(this.loc(this.program,'uEye'),eye);gl.uniform1f(this.loc(this.program,'uNight'),night);gl.uniform1f(this.loc(this.program,'uSelected'),this.state.selected);gl.uniform1f(this.loc(this.program,'uShadows'),this.state.shadows?1:0);this.draw(this.program,this.vp,lightVP);this.onFrame?.();this.dirty=false;
  }
  tick(time){const dt=Math.min((time-this.lastTime)/1000,.05);this.lastTime=time;let moving=false;if(this.state.auto&&!document.hidden){this.goal.theta+=dt*.16;moving=true;}
    for(const k of ['theta','phi','radius']){const d=this.goal[k]-this.camera[k];if(Math.abs(d)>.0001){this.camera[k]+=d*.14;moving=true;}}
    this.camera.target=this.camera.target.map((v,i)=>{const d=this.goal.target[i]-v;if(Math.abs(d)>.0001)moving=true;return v+d*.14;});
    if((this.dirty||moving)&&!document.hidden)this.render();this.raf=requestAnimationFrame(this.tick);
  }
  screenshot(){this.render();return this.canvas.toDataURL('image/png');}
  destroy(){cancelAnimationFrame(this.raf);this.resizeObserver.disconnect();const gl=this.gl;for(const b of this.batches){gl.deleteVertexArray(b.vao);b.buffers.forEach(v=>gl.deleteBuffer(v));}gl.deleteProgram(this.program);gl.deleteProgram(this.shadowProgram);gl.deleteTexture(this.depthTexture);gl.deleteFramebuffer(this.fbo);}
}
