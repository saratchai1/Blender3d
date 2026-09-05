"""Render one complete native camera shot. Called after opening its .blend.
blender -b 01_hero.blend -t 4 --python render_shot.py -- --output frames
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from pathlib import Path
import bpy

p=argparse.ArgumentParser()
p.add_argument('--output',type=Path,required=True)
p.add_argument('--width',type=int,default=1280)
p.add_argument('--height',type=int,default=720)
p.add_argument('--samples',type=int,default=32)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if not (320<=a.width<=4096 and 180<=a.height<=2160 and 1<=a.samples<=1024):raise ValueError('Invalid render settings')
a.output.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene
assert s.render.engine=='CYCLES'
assert s.camera and s.camera.animation_data
assert s.frame_start==1 and s.frame_end==96
s.render.resolution_x=a.width;s.render.resolution_y=a.height;s.render.resolution_percentage=100
s.cycles.samples=a.samples
s.render.use_persistent_data=True
s.render.image_settings.file_format='PNG'
s.render.image_settings.color_mode='RGB'
s.render.image_settings.compression=15
s.render.fps=24
report={'engine':'CYCLES','blender':bpy.app.version_string,'shot':s['shot'],'fps':24,'width':a.width,'height':a.height,'samples':a.samples,'source_scene_sha256':s['source_scene_sha256'],'frames':[]}
t0=time.monotonic()
for i in range(s.frame_start,s.frame_end+1):
    s.frame_set(i)
    path=a.output/f'frame_{i:04d}.png'
    s.render.filepath=str(path.resolve())
    t=time.monotonic();bpy.ops.render.render(write_still=True)
    if not path.is_file() or path.stat().st_size<1000:raise RuntimeError(f'Missing rendered frame {i}')
    report['frames'].append({'frame':i,'camera_position':list(s.camera.location),'camera_rotation':list(s.camera.rotation_euler),'seconds':round(time.monotonic()-t,3),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (a.output/'shot-report.json').write_text(json.dumps(report,indent=2))
    print(f'ACTUAL_FRAME {i}/96 elapsed={time.monotonic()-t0:.1f}s',flush=True)
assert len({tuple(f['camera_position']) for f in report['frames']})==96
assert len({f['sha256'] for f in report['frames']})==96
report['render_seconds']=time.monotonic()-t0
report['status']='PASS'
(a.output/'shot-report.json').write_text(json.dumps(report,indent=2))
print('SHOT_COMPLETE '+json.dumps({k:v for k,v in report.items() if k!='frames'}),flush=True)
