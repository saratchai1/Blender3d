"""Create a cinematic SOLSTICE 14 animation from the tested GLB.
Usage:
 blender --background --python models/office_10000sqm/render_animation.py -- --input web/office_10000sqm/assets/solstice-14.glb --output render/solstice14.mp4 --engine BLENDER_EEVEE_NEXT --frames 480
For higher fidelity use --engine BLENDER_EEVEE_NEXT at 1920x1080/30 fps, or switch to CYCLES locally when a GPU is available.
"""
from __future__ import annotations
import argparse, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

def look_at(obj, target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

def key(cam, frame, loc, target, lens):
    cam.location=loc; cam.data.lens=lens; look_at(cam,target); cam.keyframe_insert('location',frame=frame); cam.keyframe_insert('rotation_euler',frame=frame); cam.data.keyframe_insert('lens',frame=frame)

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--engine',default='BLENDER_EEVEE_NEXT');p.add_argument('--frames',type=int,default=480);a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.import_scene.gltf(filepath=str(a.input.resolve()))
    s=bpy.context.scene;s.render.engine=a.engine;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.fps=30;s.render.image_settings.file_format='FFMPEG';s.render.ffmpeg.format='MPEG4';s.render.ffmpeg.codec='H264';s.render.ffmpeg.constant_rate_factor='MEDIUM';s.render.filepath=str(a.output.resolve());s.frame_start=1;s.frame_end=a.frames
    if hasattr(s,'eevee'): s.eevee.taa_render_samples=64
    s.world.color=(0.08,0.11,0.14)
    sun_data=bpy.data.lights.new('Sun','SUN');sun_data.energy=3.2;sun_data.angle=math.radians(4);sun=bpy.data.objects.new('Sun',sun_data);s.collection.objects.link(sun);sun.rotation_euler=(math.radians(28),math.radians(-18),math.radians(-38))
    area_data=bpy.data.lights.new('Sky fill','AREA');area_data.energy=1800;area_data.shape='DISK';area_data.size=25;area=bpy.data.objects.new('Sky fill',area_data);s.collection.objects.link(area);area.location=(-22,-30,45);look_at(area,(0,0,24))
    cd=bpy.data.cameras.new('Cinematic Camera');cam=bpy.data.objects.new('Cinematic Camera',cd);s.collection.objects.link(cam);s.camera=cam;cd.dof.use_dof=True;cd.dof.focus_distance=80;cd.dof.aperture_fstop=5.6
    f=a.frames;shots=[(1,(72,-82,42),(0,0,25),47),(int(f*.24),(-66,-72,34),(0,0,26),52),(int(f*.48),(-52,50,47),(0,0,31),55),(int(f*.70),(38,39,31),(0,0,35),48),(int(f*.86),(24,-31,23),(0,0,23),42),(f,(70,-84,46),(0,0,28),50)]
    for fr,loc,tgt,lens in shots:key(cam,fr,loc,tgt,lens)
    if cam.animation_data and cam.animation_data.action:
        for fc in cam.animation_data.action.fcurves:
            for kp in fc.keyframe_points:kp.interpolation='BEZIER'
    a.output.resolve().parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve().with_suffix('.blend')));bpy.ops.render.render(animation=True)
    print(f'Rendered {a.frames} frames to {a.output}')
if __name__=='__main__':main()
