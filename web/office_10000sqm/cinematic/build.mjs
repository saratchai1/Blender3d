/** Same-origin runtime builder. Three.js stays pinned and is not a CDN runtime dependency. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
const source=path.dirname(fileURLToPath(import.meta.url));
const repo=path.resolve(source,'../../..');
const dest=path.resolve(process.argv[2]||path.join(repo,'.generated/pages/cinematic'));
if(dest===repo||repo.startsWith(dest+path.sep))throw new Error('Unsafe output directory');
let runtime=process.env.THREE_ROOT;
if(!runtime){const tmp=path.join(repo,'.generated/three-0.180.0');fs.mkdirSync(tmp,{recursive:true});execFileSync('npm',['pack','--ignore-scripts','three@0.180.0'],{cwd:tmp,stdio:'inherit'});execFileSync('tar',['-xzf','three-0.180.0.tgz'],{cwd:tmp});runtime=path.join(tmp,'package');}
const version=JSON.parse(fs.readFileSync(path.join(runtime,'package.json'))).version;
if(version!=='0.180.0')throw new Error(`Expected three@0.180.0; got ${version}`);
fs.mkdirSync(dest,{recursive:true});
for(const name of ['index.html','cinematic.css','main.mjs','world.mjs','tour.mjs']){let data=fs.readFileSync(path.join(source,name),'utf8');if(name==='world.mjs')data=data.replace("from '../model.mjs'","from './model.mjs'");fs.writeFileSync(path.join(dest,name),data);}
fs.copyFileSync(path.join(source,'../model.mjs'),path.join(dest,'model.mjs'));
const vendor=path.join(dest,'vendor');fs.mkdirSync(path.join(vendor,'build'),{recursive:true});
for(const name of ['three.module.min.js','three.core.min.js'])fs.copyFileSync(path.join(runtime,'build',name),path.join(vendor,'build',name));
fs.copyFileSync(path.join(runtime,'LICENSE'),path.join(vendor,'LICENSE'));
const seen=new Set();
function copyAddon(file){if(seen.has(file))return;seen.add(file);const input=path.join(runtime,'examples/jsm',file),output=path.join(vendor,'examples/jsm',file);const data=fs.readFileSync(input,'utf8');fs.mkdirSync(path.dirname(output),{recursive:true});fs.copyFileSync(input,output);for(const match of data.matchAll(/(?:from\s*|import\s*)['"](\.[^'"]+)['"]/g)){copyAddon(path.posix.normalize(path.posix.join(path.posix.dirname(file),match[1])));}}
for(const f of ['controls/OrbitControls.js','objects/Sky.js','objects/Reflector.js','geometries/RoundedBoxGeometry.js','postprocessing/EffectComposer.js','postprocessing/RenderPass.js','postprocessing/SSAOPass.js','postprocessing/UnrealBloomPass.js','postprocessing/OutputPass.js','postprocessing/FXAAPass.js'])copyAddon(f);
fs.writeFileSync(path.join(dest,'build.json'),JSON.stringify({version:'cinematic-1.0.0',sourceCommit:process.env.GITHUB_SHA||'local-review',three:version,addonModules:seen.size,animationSeconds:72,shots:6,runtimeExternalRequests:false},null,2));
console.log(JSON.stringify({destination:dest,three:version,addonModules:seen.size}));
