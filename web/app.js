import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/loaders/GLTFLoader.js';

const canvas=document.querySelector('#view');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;renderer.outputColorSpace=THREE.SRGBColorSpace;
const scene=new THREE.Scene();scene.background=new THREE.Color(0x0c1210);scene.fog=new THREE.FogExp2(0x0c1210,.008);
const camera=new THREE.PerspectiveCamera(38,1,.1,500);camera.position.set(45,-48,32);
const controls=new OrbitControls(camera,canvas);controls.target.set(0,0,10);controls.enableDamping=true;controls.autoRotate=true;controls.autoRotateSpeed=.7;
scene.add(new THREE.HemisphereLight(0xcfe1d2,0x253026,2.2));
const sun=new THREE.DirectionalLight(0xffe6b8,4);sun.position.set(-25,-35,55);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);scene.add(sun);
new GLTFLoader().load('./assets/building.glb',({scene:model})=>{model.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true}});scene.add(model)},undefined,e=>console.error('GLB load failed',e));
function resize(){const r=canvas.getBoundingClientRect(),d=Math.min(devicePixelRatio,2),w=Math.max(1,Math.round(r.width*d)),h=Math.max(1,Math.round(r.height*d));if(canvas.width!==w||canvas.height!==h){renderer.setSize(r.width,r.height,false);camera.aspect=r.width/r.height;camera.updateProjectionMatrix()}}
function frame(){resize();controls.update();renderer.render(scene,camera);requestAnimationFrame(frame)}frame();
