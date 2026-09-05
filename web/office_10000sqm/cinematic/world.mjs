import * as T from 'three';
import { Sky } from 'three/addons/objects/Sky.js';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { makeScene, FLOORS } from '../model.mjs';

// Presentation-only geometry and materials. The shared metric building is not edited.
export function buildWorld(renderer, mobile) {
  const source=makeScene(), scene=new T.Scene();
  scene.fog=new T.FogExp2(0xaabfc5,0.0025);
  const architecture=new T.Group(),context=new T.Group();scene.add(architecture,context);
  const wind={value:0};let seed=739;
  const random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
  function tex(size,paint){const c=document.createElement('canvas');c.width=c.height=size;paint(c.getContext('2d'),size);const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());return t;}
  const grain=tex(256,(ctx,s)=>{const d=ctx.createImageData(s,s);for(let i=0;i<d.data.length;i+=4){const k=165+random()*65;d.data.set([k,k,k,255],i);}ctx.putImageData(d,0,0);});grain.wrapS=grain.wrapT=T.RepeatWrapping;grain.repeat.set(8,8);grain.colorSpace=T.NoColorSpace;
  const paving=tex(512,(ctx,s)=>{ctx.fillStyle='#c2bfaf';ctx.fillRect(0,0,s,s);for(let y=0;y<8;y++)for(let x=0;x<8;x++){const b=177+random()*23;ctx.fillStyle=`rgb(${b+10},${b+8},${b})`;ctx.fillRect(x*64+1,y*64+1,62,62);}for(let i=0;i<20000;i++){const b=random()>.5?255:60;ctx.fillStyle=`rgba(${b},${b},${b},0.10)`;ctx.fillRect(random()*s,random()*s,1,1);}});paving.wrapS=paving.wrapT=T.RepeatWrapping;paving.repeat.set(6,5);
  const woodTex=tex(256,(ctx,s)=>{ctx.fillStyle='#8f7150';ctx.fillRect(0,0,s,s);for(let i=0;i<700;i++){ctx.fillStyle=`rgba(${40+random()*50},${25+random()*35},15,0.12)`;ctx.fillRect(random()*s,0,random()*1.2,s);}for(let i=0;i<4;i++){ctx.fillStyle='#544331';ctx.fillRect(i*64,0,1,s);}});woodTex.wrapS=woodTex.wrapT=T.RepeatWrapping;woodTex.repeat.set(3,1);
  const leafTex=tex(128,(ctx,s)=>{ctx.clearRect(0,0,s,s);for(let i=0;i<9;i++){const a=i*2.4,cx=64+Math.cos(a)*31,cy=64+Math.sin(a)*31;ctx.save();ctx.translate(cx,cy);ctx.rotate(a);const g=ctx.createLinearGradient(-18,0,18,0);g.addColorStop(0,'#647640');g.addColorStop(.48,'#adba79');g.addColorStop(1,'#728847');ctx.fillStyle=g;ctx.beginPath();ctx.ellipse(0,0,21,8,0,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#b4c98788';ctx.lineWidth=.8;ctx.beginPath();ctx.moveTo(-19,0);ctx.lineTo(19,0);ctx.stroke();ctx.restore();}});
  const mats={
    ivory:new T.MeshStandardMaterial({color:0xe5dfd0,roughness:.55,bumpMap:grain,bumpScale:.012}),
    stone:new T.MeshStandardMaterial({color:0xb4b4a6,roughness:.68,bumpMap:grain,bumpScale:.035}),
    glass:new T.MeshPhysicalMaterial({color:0x9db6b6,metalness:.28,roughness:.11,transmission:.22,thickness:.13,ior:1.48,envMapIntensity:1.1,clearcoat:1,clearcoatRoughness:.1}),
    glassLight:new T.MeshPhysicalMaterial({color:0xc3d1c9,metalness:.25,roughness:.14,transmission:.25,thickness:.13,envMapIntensity:1.05,clearcoat:1}),
    bronze:new T.MeshStandardMaterial({color:0xab8961,metalness:.78,roughness:.27,envMapIntensity:1.05}),
    dark:new T.MeshStandardMaterial({color:0x283738,metalness:.5,roughness:.38}),
    wood:new T.MeshStandardMaterial({map:woodTex,roughness:.56,bumpMap:grain,bumpScale:.025}),
    lawn:new T.MeshStandardMaterial({color:0x4f663d,roughness:1,bumpMap:grain,bumpScale:.07}),
    road:new T.MeshStandardMaterial({color:0x4b5253,roughness:.94,bumpMap:grain,bumpScale:.06}),
    solar:new T.MeshPhysicalMaterial({color:0x102732,metalness:.58,roughness:.18,clearcoat:1}),
    light:new T.MeshStandardMaterial({color:0xffe2b6,emissive:0xffd597,emissiveIntensity:2.3,roughness:.5}),
    interior:new T.MeshStandardMaterial({color:0x9b8b73,roughness:.79}),
    paving:new T.MeshStandardMaterial({map:paving,roughness:.6,bumpMap:grain,bumpScale:.023}),
    leaves:new T.MeshStandardMaterial({map:leafTex,alphaTest:.42,side:T.DoubleSide,roughness:.87,emissive:0x293018,emissiveIntensity:.2}),
    context:new T.MeshStandardMaterial({color:0xa3adaa,roughness:.92}),
    contextGlass:new T.MeshStandardMaterial({color:0x638186,roughness:.3,metalness:.5}),
    glow:new T.MeshStandardMaterial({color:0xb3ad94,emissive:0xffc482,emissiveIntensity:.12,roughness:.85}),
    soil:new T.MeshStandardMaterial({color:0x3d4834,roughness:1}),
  };
  mats.leaves.onBeforeCompile=shader=>{shader.uniforms.uWindTime=wind;shader.vertexShader='uniform float uWindTime;\n'+shader.vertexShader;shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>',`#include <begin_vertex>
#ifdef USE_INSTANCING
float phase=instanceMatrix[3].x*.79+instanceMatrix[3].z*.61;
transformed.x+=sin(uWindTime*1.1+phase+position.y*3.0)*.07*(position.y+.5);
transformed.z+=cos(uWindTime*.85+phase)*.04;
#endif`);};
  mats.leaves.customProgramCacheKey=()=> 'solstice-leaf-wind-v1';
  const geos={box:new T.BoxGeometry(1,1,1),round:new RoundedBoxGeometry(1,1,1,1,.045),sphere:new T.SphereGeometry(1,16,10),cylinder:new T.CylinderGeometry(.5,.5,1,10),leaf:new T.PlaneGeometry(1,1)};
  const groups=new Map(),obj=new T.Object3D(),matrix=new T.Matrix4(),c=new T.Color();
  function instance(geometry,material,mat,color=null,isContext=false){const key=`${geometry}/${material}/${isContext}`;if(!groups.has(key))groups.set(key,{geometry,material,context:isContext,items:[]});groups.get(key).items.push({matrix:mat.clone(),color});}
  function add(shape,material,p,s,rot=[0,0,0],color=null,ctx=false){obj.position.set(...p);obj.scale.set(...s);obj.rotation.set(...rot);obj.updateMatrix();instance(shape,material,obj.matrix,color,ctx);}
  const box=(m,p,s,r=[0,0,0],col=null,ctx=false)=>add('box',m,p,s,r,col,ctx);
  function branch(a,b,r,ctx=false){const start=new T.Vector3(...a),end=new T.Vector3(...b);obj.position.copy(start).add(end).multiplyScalar(.5);obj.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),end.clone().sub(start).normalize());obj.scale.set(r,end.distanceTo(start),r);obj.updateMatrix();instance('cylinder','wood',obj.matrix,null,ctx);}
  const trees=source.objects.filter(o=>o.name==='Tree trunk'),shrubs=[];
  let kept=0;
  for(const o of source.objects){
    if(['leaf','leafLight'].includes(o.material)||o.name.startsWith('Tree ')||o.name.startsWith('Visitor')||o.name.startsWith('Electric car')||o.name==='Car wheel'||o.name==='Plaza joint')continue;
    if(o.material==='water')continue;
    if(o.name==='Shrub'){shrubs.push(o);continue;}
    matrix.fromArray(o.matrix);let mat=o.material,shape=o.shape;
    if(o.name==='Paved plaza')mat='paving';
    if(o.name==='Entry light line')mat='light';
    if(mat==='bronze'||o.name.includes('column'))shape='round';
    if(!mats[mat])mat='stone';
    instance(shape,mat,matrix);kept++;
  }
  // A few muted city blocks outside the hypothetical site provide genuine reflection context.
  box('context',[0,-1.32,0],[900,.2,900],[0,0,0],0xb7b9ac,true);
  box('road',[0,-.18,34],[850,.15,10],[0,0,0],null,true);
  for(let i=0;i<24;i++){
    const ang=i*2.39996,r=90+random()*220,x=Math.cos(ang)*r,z=Math.sin(ang)*r;
    if(z>0&&Math.abs(x)<65)continue;
    const h=9+random()*43,w=12+random()*21,d=12+random()*22;
    box('context',[x,h/2-1.3,z],[w,h,d],[0,0,0],c.setHSL(.14,.04,.52+random()*.22).getHex(),true);
    for(let y=2;y<h;y+=3.4){box('contextGlass',[x,y-1.3,z+d/2+.015],[w-.9,1.5,.03],[0,0,0],null,true);box('contextGlass',[x+w/2+.015,y-1.3,z],[.03,1.5,d-.9],[0,0,0],null,true);}
  }
  // Glazing sees real room surfaces and illumination rather than a solid coloured tower.
  for(const f of FLOORS){
    const w=f.width,d=f.depth,h=f.height,y=f.y;
    box('interior',[0,y+.34,0],[w-.7,.025,d-.7]);
    for(const sign of [-1,1]){
      const skip=f.terrace>0&&sign===1;
      for(let i=0;i<Math.floor(w/3.2);i++){
        const x=-w/2+2+i*3.2;if(skip&&Math.abs(x)<9)continue;
        box('glow',[x,y+h*.53,sign*(d/2-1.4)],[2.45,h-.95,.05],[0,0,0],c.setRGB(.68+random()*.2,.59+random()*.18,.45+random()*.14).getHex());
        if(i%2===0)box('light',[x,y+h-.29,sign*(d/2-1.7)],[1.65,.025,.07]);
      }
    }
  }
  function tree(x,y,z,scale=1,ctx=false){
    const h=3.25*scale,r=1.95*scale;
    branch([x,y,z],[x+.12*scale,y+h,z],.22*scale,ctx);
    for(let i=0;i<13;i++){
      const a=i*2.399+random(),rr=r*(.6+random()*.45),by=y+h*.48+random()*h*.35;
      branch([x,by,z],[x+Math.cos(a)*rr, y+h*(.8+random()*.4),z+Math.sin(a)*rr],.04*scale,ctx);
    }
    const count=mobile?170:280;
    for(let i=0;i<count;i++){
      const a=random()*Math.PI*2,rr=Math.sqrt(random())*r,hh=(random()-.35)*2.2*scale;
      const px=x+Math.cos(a)*rr,pz=z+Math.sin(a)*rr,py=y+h+hh*(1-rr/r*.4);
      const ss=(.47+random()*.42)*scale;
      add('leaf','leaves',[px,py,pz],[ss,ss,ss],[(random()-.5)*Math.PI,random()*Math.PI*2,random()*Math.PI],c.setHSL(.20+random()*.055,.24+random()*.23,.35+random()*.22).getHex(),ctx);
    }
  }
  for(const t of trees){const m=t.matrix,scale=Math.hypot(...m.slice(0,3))/.18,y=m[13]-m[5]/2;tree(m[12],y,m[14],scale);}
  for(let i=0;i<30;i++){const a=i*.67,rr=50+random()*170,x=Math.sin(a)*rr,z=-25-Math.abs(Math.cos(a)*rr);tree(x,-1.2,z,1+random()*1.8,true);}
  // Shrub leaf masses retain original planter locations, without low-poly balls.
  for(const o of source.objects.filter(o=>o.name==='Shrub')){
    const m=o.matrix;for(let i=0;i<(mobile?7:12);i++)add('leaf','leaves',[m[12]+(random()-.5)*m[0]*2,m[13]+(random()-.5)*m[5],m[14]+(random()-.5)*m[10]], [.45,.45,.45],[random()*3,random()*6,random()*3],0x819c62);
  }
  // Grasses are actual instanced geometry, not a ground-plane photograph.
  const blade=new T.BufferGeometry();blade.setAttribute('position',new T.Float32BufferAttribute([-.08,0,0,.08,0,0,.025,.75,.03,0,1,.08],3));blade.setIndex([0,1,2,0,2,3]);blade.computeVertexNormals();geos.grass=blade;
  mats.grass=new T.MeshStandardMaterial({color:0x536b32,side:T.DoubleSide,roughness:1});
  for(const bed of [{x:26,z:-5,w:8.5,d:36},{x:0,z:-23,w:43,d:7},{x:-26,z:-19,w:10,d:11}]){
    for(let i=0;i<(mobile?600:1500);i++){const s=.14+random()*.2;add('grass','grass',[bed.x+(random()-.5)*bed.w,.105,bed.z+(random()-.5)*bed.d],[s,s,s],[0,random()*6.28,0],c.setHSL(.2+random()*.06,.25+random()*.16,.24+random()*.15).getHex());}
  }
  // Garden rail panels add legibility in close views, without changing slab dimensions.
  for(const n of [5,10]){const y=FLOORS[n-1].y;box('glassLight',[0,y+.85,10.02],[17.9,1.0,.035]);}
  // Architectural accent lighting (visualisation only).
  for(const x of [-6.3,6.3])box('light',[x,3.81,15.4],[.04,.03,5.6]);
  for(const n of [5,10])box('light',[0,FLOORS[n-1].y+.48,10.08],[17.7,.04,.035]);
  const warmLights=[];
  for(const [x,y,z,power]of [[-5,3.7,15.5,45],[5,3.7,15.5,45],[0,36.8,8,60]]){const l=new T.PointLight(0xffd5a2,power,11,2);l.position.set(x,y,z);scene.add(l);warmLights.push(l);}
  // An understated entrance nameplate is real scene geometry.
  const signTex=tex(512,(ctx,s)=>{ctx.clearRect(0,0,s,s);ctx.fillStyle='#ddd1b6';ctx.textAlign='center';ctx.font='34px Georgia';ctx.fillText('S O L S T I C E   1 4',s/2,280);});
  const sign=new T.Mesh(new T.PlaneGeometry(8,8),new T.MeshBasicMaterial({map:signTex,transparent:true,depthWrite:false}));sign.position.set(0,3.14,18.46);architecture.add(sign);
  // Install each group as instanced meshes. No thousands-of-draw-calls bottleneck.
  let instances=0;
  for(const g of groups.values()){
    const mesh=new T.InstancedMesh(geos[g.geometry],mats[g.material],g.items.length);
    g.items.forEach((x,i)=>{mesh.setMatrixAt(i,x.matrix);if(x.color!==null)mesh.setColorAt(i,new T.Color(x.color));});
    mesh.instanceMatrix.needsUpdate=true;if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true;
    mesh.name=`${g.context?'context':'model'}-${g.material}-${g.geometry}`;mesh.castShadow=!['glow','light','glass','glassLight','grass'].includes(g.material);mesh.receiveShadow=!['light','glow'].includes(g.material);mesh.frustumCulled=false;
    (g.context?context:architecture).add(mesh);instances+=g.items.length;
  }
  const sky=new Sky();sky.scale.setScalar(4000);scene.add(sky);
  sky.material.uniforms.turbidity.value=3.1;sky.material.uniforms.rayleigh.value=1.4;sky.material.uniforms.mieCoefficient.value=.004;sky.material.uniforms.mieDirectionalG.value=.82;
  const hemi=new T.HemisphereLight(0xc1dcea,0x9a967c,1.15);scene.add(hemi);
  const sun=new T.DirectionalLight(0xffe8c5,3.0);sun.position.set(-55,75,80);sun.target.position.set(0,22,0);scene.add(sun,sun.target);
  sun.castShadow=true;sun.shadow.mapSize.set(mobile?2048:4096,mobile?2048:4096);sun.shadow.camera.left=-56;sun.shadow.camera.right=56;sun.shadow.camera.top=58;sun.shadow.camera.bottom=-58;sun.shadow.camera.near=1;sun.shadow.camera.far=230;sun.shadow.bias=-.00014;sun.shadow.normalBias=.045;sun.shadow.radius=2.5;sun.shadow.autoUpdate=false;sun.shadow.needsUpdate=true;
  // Actual planar reflection of the building; ripple distortion changes every frame.
  const reflection=new Reflector(new T.PlaneGeometry(6.5,20.5),{clipBias:.003,textureWidth:mobile?256:768,textureHeight:mobile?256:768,color:0x6a8c8a,multisample:0});
  reflection.rotation.x=-Math.PI/2;reflection.position.set(-25,.171,5);reflection.material.uniforms.uRipple=wind;
  reflection.material.fragmentShader=reflection.material.fragmentShader.replace('uniform vec3 color;','uniform vec3 color;\nuniform float uRipple;').replace('vec4 base = texture2DProj( tDiffuse, vUv );','vec4 waveUv = vUv; waveUv.xy += vec2(sin(vUv.x*170.0+uRipple*.6),cos(vUv.y*145.0+uRipple*.47))*.00065*vUv.w; vec4 base = texture2DProj( tDiffuse, waveUv );');
  scene.add(reflection);
  const pmrem=new T.PMREMGenerator(renderer),cubeTarget=new T.WebGLCubeRenderTarget(128,{type:T.HalfFloatType,generateMipmaps:true,minFilter:T.LinearMipmapLinearFilter});const cubeCamera=new T.CubeCamera(1,1600,cubeTarget);cubeCamera.position.set(0,29,0);let environment=null;
  const looks={day:{sun:[-40,95,65],power:3.1,hemi:1.5,exposure:1.0,fog:0xaebfc4,emission:.025,rayleigh:1.25},golden:{sun:[-68,53,72],power:3.5,hemi:1.16,exposure:1.02,fog:0xb5bbaa,emission:.12,rayleigh:1.7},blue:{sun:[-80,7,55],power:.3,hemi:1.1,exposure:1.23,fog:0x718d9f,emission:2.15,rayleigh:2.7}};
  function setLook(name){
    const l=looks[name]||looks.golden;sun.position.set(...l.sun);sun.intensity=l.power;sun.color.set(name==='blue'?0xa5c9ec:name==='golden'?0xffdbad:0xfff4dd);hemi.intensity=l.hemi;hemi.color.set(name==='blue'?0x98b5d7:0xc1d8e0);sky.material.uniforms.sunPosition.value.copy(sun.position).normalize();sky.material.uniforms.rayleigh.value=l.rayleigh;scene.fog.color.set(l.fog);renderer.toneMappingExposure=l.exposure;
    mats.glow.emissiveIntensity=l.emission;mats.light.emissiveIntensity=name==='blue'?4.5:1.2;warmLights.forEach(x=>x.intensity=name==='blue'?75:12);
    architecture.visible=false;reflection.visible=false;scene.environment=null;cubeCamera.update(renderer,scene);const rt=pmrem.fromCubemap(cubeTarget.texture);scene.environment=rt.texture;environment?.dispose();environment=rt;architecture.visible=true;reflection.visible=true;sun.shadow.needsUpdate=true;
  }
  setLook('golden');
  return {scene,source,architecture,context,wind,mats,sun,reflection,setLook,statistics:{sourceObjects:source.objects.length,buildingSourceObjects:kept,renderInstances:instances,instancedBatches:groups.size,storeys:source.floors.length,conceptArea:source.floors.reduce((s,f)=>s+f.area,0)},setQuality(high){sun.shadow.mapSize.set(high&&!mobile?4096:2048,high&&!mobile?4096:2048);sun.shadow.map?.dispose();sun.shadow.map=null;sun.shadow.needsUpdate=true;reflection.visible=high;}};
}
