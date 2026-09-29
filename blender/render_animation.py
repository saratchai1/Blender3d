"""Render a real 3D camera animation from dist/building.blend.

The script renders PNG frames. FFmpeg encodes them to MP4.
"""
from __future__ import annotations
import argparse, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

def cli():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,default=Path("dist/render"))
    p.add_argument("--engine",choices=["EEVEE","CYCLES"],default="EEVEE")
    p.add_argument("--seconds",type=float,default=8)
    p.add_argument("--fps",type=int,default=24)
    p.add_argument("--width",type=int,default=1280)
    p.add_argument("--height",type=int,default=720)
    p.add_argument("--samples",type=int,default=32)
    argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    return p.parse_args(argv)

def look_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

def key(cam,frame,loc,target,lens):
    cam.location=loc;cam.data.lens=lens;look_at(cam,target)
    cam.keyframe_insert(data_path="location",frame=frame)
    cam.keyframe_insert(data_path="rotation_euler",frame=frame)
    cam.data.keyframe_insert(data_path="lens",frame=frame)

def main():
    a=cli();s=bpy.context.scene;out=a.output_dir.resolve();frames=out/"frames";frames.mkdir(parents=True,exist_ok=True)
    zmax=max((o.location.z for o in s.objects),default=20)+4;target=(0,0,zmax*.48)
    s.render.engine="BLENDER_EEVEE_NEXT" if a.engine=="EEVEE" else "CYCLES"
    if a.engine=="CYCLES":s.cycles.samples=a.samples;s.cycles.use_denoising=True
    s.render.resolution_x=a.width;s.render.resolution_y=a.height;s.render.resolution_percentage=100;s.render.fps=a.fps
    s.render.image_settings.file_format="PNG";s.render.filepath=str(frames/"frame_")
    s.frame_start=1;s.frame_end=max(2,round(a.seconds*a.fps))
    world=s.world or bpy.data.worlds.new("World");s.world=world;world.use_nodes=True
    bg=world.node_tree.nodes.get("Background")
    if bg:bg.inputs["Color"].default_value=(.055,.075,.105,1);bg.inputs["Strength"].default_value=.45
    sd=bpy.data.lights.new("Teaching Sun","SUN");sd.energy=3;sd.angle=math.radians(4)
    sun=bpy.data.objects.new("Teaching Sun",sd);s.collection.objects.link(sun);sun.rotation_euler=(math.radians(28),math.radians(-20),math.radians(-35))
    ad=bpy.data.lights.new("Teaching Fill","AREA");ad.energy=1200;ad.shape="DISK";ad.size=18
    area=bpy.data.objects.new("Teaching Fill",ad);s.collection.objects.link(area);area.location=(-20,-25,zmax*.75);look_at(area,target)
    cd=bpy.data.cameras.new("Cinematic Camera");cam=bpy.data.objects.new("Cinematic Camera",cd);s.collection.objects.link(cam);s.camera=cam
    cd.dof.use_dof=True;cd.dof.aperture_fstop=5.6
    f=s.frame_end;r=58
    shots=[(1,(r,-r,zmax*.68),target,48),(round(f*.25),(0,-68,zmax*.36),(0,0,zmax*.34),42),(round(f*.5),(-58,-22,zmax*.58),target,52),(round(f*.75),(-30,55,zmax*.78),(0,0,zmax*.56),50),(f,(62,42,zmax*.70),target,55)]
    for item in shots:key(cam,*item)
    if cam.animation_data and cam.animation_data.action:
        for fc in cam.animation_data.action.fcurves:
            for pt in fc.keyframe_points:pt.interpolation="BEZIER"
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"building-animated.blend"))
    bpy.ops.render.render(animation=True)
    print(f"Rendered {s.frame_end} frames to {frames}")

if __name__=="__main__":main()
