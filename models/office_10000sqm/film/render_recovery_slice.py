"""Render four native frames to recover an interrupted 32-frame camera segment."""
from __future__ import annotations
import argparse,hashlib,json,sys,time
from pathlib import Path
import bpy
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--part',type=int,required=True);p.add_argument('--slice',type=int,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if a.part not in [0,1,2] or not 0<=a.slice<8:raise ValueError('Invalid native frame range')
s=bpy.context.scene
assert s.render.engine=='CYCLES' and s.camera and s.camera.animation_data
assert s.frame_start==1 and s.frame_end==96 and any(n.type=='DENOISE' for n in s.node_tree.nodes)
a.output.mkdir(parents=True,exist_ok=True)
s.render.resolution_x=1280;s.render.resolution_y=720;s.render.resolution_percentage=100;s.cycles.samples=24
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.compression=15
s.render.use_persistent_data=True;s.render.fps=24
report={'status':'IN_PROGRESS','shot':s['shot'],'part':a.part,'slice':a.slice,'engine':'CYCLES','blender':bpy.app.version_string,'source_scene_sha256':s['source_scene_sha256'],'width':1280,'height':720,'fps':24,'samples':24,'denoising':s['denoising'],'frames':[]}
t0=time.monotonic();first=a.part*32+a.slice*4+1
for i in range(first,first+4):
 s.frame_set(i);path=a.output/f'frame_{i:04d}.png';s.render.filepath=str(path.resolve());t=time.monotonic();bpy.ops.render.render(write_still=True)
 if not path.is_file() or path.stat().st_size<1000:raise RuntimeError(f'Rendered frame {i} missing')
 report['frames'].append({'frame':i,'camera_position':list(s.camera.location),'camera_rotation':list(s.camera.rotation_euler),'seconds':round(time.monotonic()-t,3),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 (a.output/'slice-report.json').write_text(json.dumps(report,indent=2))
 print(f'ACTUAL_RECOVERY_FRAME {i}/96 ELAPSED {time.monotonic()-t0:.1f}s',flush=True)
assert len(report['frames'])==4 and len({tuple(f['camera_position']) for f in report['frames']})==4
assert len({f['sha256'] for f in report['frames']})==4
report['status']='PASS';report['render_seconds']=time.monotonic()-t0
(a.output/'slice-report.json').write_text(json.dumps(report,indent=2))
print('NATIVE_SLICE_COMPLETE '+json.dumps({k:v for k,v in report.items() if k!='frames'}))
