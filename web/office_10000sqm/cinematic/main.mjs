import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { FXAAPass } from 'three/addons/postprocessing/FXAAPass.js';
import { buildWorld } from './world.mjs';
import { SHOTS, SHOT_SECONDS, DURATION, shotAt, rail } from './tour.mjs';
const $=id=>document.getElementById(id), mobile=matchMedia('(max-width:800px)').matches;
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
let toastTimer;
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3600);}
function fatal(error){console.error(error);$('loading').hidden=false;$('load-text').textContent='เปิดฉาก 3D ไม่สำเร็จ: '+(error.message||String(error));document.querySelector('.loader-line').hidden=true;const button=document.createElement('button');button.textContent='โหลดใหม่';button.style.cssText='border:1px solid #aabb99;padding:12px 28px;margin-top:20px';button.onclick=()=>location.reload();$('loading').append(button);}
try {
  const canvas=$('canvas');
  const renderer=new T.WebGLRenderer({canvas,antialias:false,alpha:false,powerPreference:'high-performance',preserveDrawingBuffer:false});
  renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=true;
  const camera=new T.PerspectiveCamera(37,innerWidth/innerHeight,.15,2200);
  const world=buildWorld(renderer,mobile),scene=world.scene;
  const controls=new OrbitControls(camera,canvas);controls.enabled=false;controls.enableDamping=true;controls.dampingFactor=.08;controls.minDistance=8;controls.maxDistance=240;controls.maxPolarAngle=Math.PI*.49;controls.minPolarAngle=.08;controls.target.set(0,26,0);
  const composer=new EffectComposer(renderer);
  const renderPass=new RenderPass(scene,camera);composer.addPass(renderPass);
  const ao=new SSAOPass(scene,camera,innerWidth,innerHeight);ao.kernelRadius=1.8;ao.minDistance=.001;ao.maxDistance=.07;ao.enabled=!mobile;composer.addPass(ao);
  const bloom=new UnrealBloomPass(new T.Vector2(innerWidth,innerHeight),.16,.38,1.25);composer.addPass(bloom);
  composer.addPass(new OutputPass());composer.addPass(new FXAAPass());
  const state={ready:false,time:0,playing:!reduced,exploring:false,look:'golden',baseLook:'golden',quality:mobile?'balanced':'high',shot:-1,frames:0,version:'cinematic-1.0.1',error:null};
  let last=performance.now(),dirty=true,uiHidden=false,resizeQueued=false,fpsElapsed=0,fpsFrames=0;
  function configureSize(){
    const w=innerWidth,h=innerHeight,cap=state.quality==='high'?1.6:1.0;
    const ratio=Math.min(devicePixelRatio||1,cap,Math.sqrt(2304000/(w*h)));
    renderer.setPixelRatio(ratio);renderer.setSize(w,h,false);composer.setPixelRatio(ratio);composer.setSize(w,h);ao.setSize(Math.round(w*ratio*.6),Math.round(h*ratio*.6));
    camera.aspect=w/h;camera.updateProjectionMatrix();cameraRail();dirty=true;
  }
  function look(name){state.look=name;world.setLook(name);renderer.shadowMap.needsUpdate=true;bloom.strength=name==='blue'?.29:.13;document.querySelectorAll('[data-look]').forEach(b=>{const on=b.dataset.look===name;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});dirty=true;}
  function updateShot(force=false){const id=shotAt(state.time);if(id===state.shot&&!force)return;state.shot=id;const shot=SHOTS[id];$('shot-number').textContent=`${String(id+1).padStart(2,'0')} / ${shot.label}`;$('shot-title').innerHTML=shot.title;$('shot-subtitle').innerHTML=shot.subtitle;document.querySelectorAll('[data-shot]').forEach(b=>{const on=Number(b.dataset.shot)===id;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});const next=id===5?'blue':state.baseLook;if(state.look!==next)look(next);}
  function cameraRail(){
    if(state.exploring)return;
    const shot=SHOTS[shotAt(state.time)],u=(state.time%SHOT_SECONDS)/SHOT_SECONDS,point=rail(shot.positions,u),target=new T.Vector3(...shot.target);
    camera.position.set(...point);
    const narrow=innerWidth/innerHeight<.8;
    if(narrow){camera.position.sub(target).multiplyScalar(shot.name==='overview'||shot.name==='bluehour'?1.35:1.3).add(target);camera.fov=shot.fov+9;camera.setViewOffset(innerWidth,innerHeight,0,innerHeight*.15,innerWidth,innerHeight);}else{camera.fov=shot.fov;camera.setViewOffset(innerWidth,innerHeight,-innerWidth*.13,innerHeight*.015,innerWidth,innerHeight);}
    camera.lookAt(target);camera.updateProjectionMatrix();
  }
  function setPlaying(on){state.playing=on;$('play').setAttribute('aria-pressed',String(on));$('play').setAttribute('aria-label',on?'หยุดชั่วคราว':'เล่นภาพยนตร์');$('pause-icon').toggleAttribute('hidden',!on);$('play-icon').toggleAttribute('hidden',on);last=performance.now();dirty=true;}
  function explore(on){
    state.exploring=on;controls.enabled=on;document.body.classList.toggle('exploring',on);$('explore-hint').hidden=!on;$('explore').setAttribute('aria-pressed',String(on));$('film').setAttribute('aria-pressed',String(!on));$('explore').classList.toggle('active',on);$('film').classList.toggle('active',!on);$('status').textContent=on?'FREE EXPLORATION':'LIVE 3D FILM';
    if(on){setPlaying(false);camera.clearViewOffset();controls.target.set(...SHOTS[state.shot].target);controls.update();}else{cameraRail();setPlaying(true);}dirty=true;
  }
  function seek(seconds,play=state.playing){state.time=Math.max(0,Math.min(DURATION-.01,Number(seconds)||0));if(state.exploring)explore(false);updateShot();cameraRail();setPlaying(play);dirty=true;}
  function next(delta){seek(((state.shot+delta+SHOTS.length)%SHOTS.length)*SHOT_SECONDS+.7);}
  function quality(){const high=state.quality!=='high';state.quality=high?'high':'balanced';ao.enabled=high&&!mobile;world.setQuality(high);renderer.shadowMap.needsUpdate=true;$('quality').innerHTML=`${high?'HIGH':'BALANCED'} <span>↗</span>`;configureSize();toast(high?'คุณภาพสูง: เงาละเอียดและ reflection':'โหมดลื่นไหล: ลดความละเอียดและเอฟเฟกต์บางส่วน');}
  function hideUI(){uiHidden=!uiHidden;document.body.classList.toggle('ui-hidden',uiHidden);$('restore-ui').hidden=!uiHidden;}
  async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else if(document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();else toast('เบราว์เซอร์นี้ไม่รองรับเต็มจอ ใช้แนวนอนเพื่อชมภาพกว้างขึ้น');}catch{toast('เปิดเต็มจอไม่สำเร็จ ลองเปิดเว็บในเบราว์เซอร์โดยตรง');}}
  $('play').onclick=()=>{if(state.exploring)explore(false);else setPlaying(!state.playing);};$('restart').onclick=()=>seek(0,true);$('film').onclick=()=>explore(false);$('explore').onclick=()=>explore(!state.exploring);$('quality').onclick=quality;$('fullscreen').onclick=fullscreen;$('hide-ui').onclick=hideUI;$('restore-ui').onclick=hideUI;
  $('timeline').oninput=e=>seek(e.target.value,state.playing);document.querySelectorAll('[data-shot]').forEach(b=>b.onclick=()=>seek(Number(b.dataset.shot)*SHOT_SECONDS+.7,true));
  document.querySelectorAll('[data-look]').forEach(b=>b.onclick=()=>{state.baseLook=b.dataset.look;look(b.dataset.look);});
  let wasPlaying=false;
  $('info').onclick=()=>{wasPlaying=state.playing;setPlaying(false);$('details').showModal();};$('close-info').onclick=()=>$('details').close();$('details').addEventListener('close',()=>setPlaying(wasPlaying));
  window.addEventListener('keydown',e=>{if($('details').open||['INPUT','BUTTON','A','SELECT'].includes(document.activeElement.tagName))return;if(e.code==='Space'){e.preventDefault();setPlaying(!state.playing);}if(e.key==='ArrowRight'){e.preventDefault();next(1);}if(e.key==='ArrowLeft'){e.preventDefault();next(-1);}if(e.key.toLowerCase()==='h')hideUI();if(e.key.toLowerCase()==='f')fullscreen();});
  window.addEventListener('resize',()=>{if(resizeQueued)return;resizeQueued=true;requestAnimationFrame(()=>{resizeQueued=false;configureSize();});});
  document.addEventListener('visibilitychange',()=>{last=performance.now();});
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();state.error='WebGL context lost';state.ready=false;fatal(new Error('ระบบกราฟิกหยุดทำงาน กรุณาโหลดหน้าใหม่'));});
  controls.addEventListener('change',()=>dirty=true);
  window.__cinematic={state,seek,getState:()=>({...state,camera:camera.position.toArray(),quaternion:camera.quaternion.toArray(),renderer:renderer.info.render,stats:world.statistics,canvas:[canvas.width,canvas.height],windTime:world.wind.value,threeRevision:T.REVISION,glError:renderer.getContext().getError()}),setLook:look};
  updateShot();configureSize();setPlaying(state.playing);$('quality').innerHTML=`${state.quality.toUpperCase()} <span>↗</span>`;
  renderer.compile(scene,camera);renderer.shadowMap.needsUpdate=true;composer.render();
  state.ready=true;last=performance.now();$('loading').hidden=true;
  if(reduced)toast('ตั้งค่าลดการเคลื่อนไหวอยู่ กด ▶ เพื่อเริ่มภาพยนตร์');
  function tick(now){requestAnimationFrame(tick);if(!state.ready||state.error||document.hidden)return;const elapsed=Math.max(0,(now-last)/1000),dt=Math.min(elapsed,.15);last=now;
    if(state.playing&&!state.exploring){state.time=(state.time+elapsed)%DURATION;updateShot();cameraRail();}else if(state.exploring)controls.update();
    if(!state.playing&&!dirty)return;
    if(state.playing)world.wind.value+=dt;
    const local=state.time%SHOT_SECONDS,fade=state.exploring?0:Math.max(0,(.35-local)/.35,(local-(SHOT_SECONDS-.35))/.35)*.92;$('cut').style.opacity=String(fade);
    $('timeline').value=state.time;$('timeline').style.setProperty('--progress',`${state.time/DURATION*100}%`);$('timeline').setAttribute('aria-valuetext',`${Math.floor(state.time)} วินาที`);$('current-time').textContent=`${String(Math.floor(state.time/60)).padStart(2,'0')}:${String(Math.floor(state.time%60)).padStart(2,'0')}`;
    composer.render();state.frames++;state.renderedTime=state.time;dirty=false;fpsFrames++;fpsElapsed+=elapsed;if(fpsElapsed>2){state.fps=Math.round(fpsFrames/fpsElapsed);fpsElapsed=0;fpsFrames=0;}
  }
  requestAnimationFrame(tick);
} catch(error){fatal(error);}
