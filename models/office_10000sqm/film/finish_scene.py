"""Final look-development pass on native Cycles scenes. Building geometry is unchanged."""
from __future__ import annotations
import argparse,json,math,sys,time
from pathlib import Path
import bpy
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--proof',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);a.output.mkdir(parents=True,exist_ok=True)

def color(h):
 h=h.lstrip('#');v=[int(h[i:i+2],16)/255 for i in (0,2,4)];return tuple(c/12.92 if c<.04045 else ((c+.055)/1.055)**2.4 for c in v)+(1,)

reports=[]
for path in sorted(a.input.glob('*.blend')):
 bpy.ops.wm.open_mainfile(filepath=str(path.resolve()));s=bpy.context.scene;shot=s['shot']
 # Explicit guided compositor denoising: inspectable in the delivered .blend.
 s.cycles.use_denoising=False
 s.view_layers[0].cycles.denoising_store_passes=True
 s.use_nodes=True;s.render.use_compositing=True
 nt=s.node_tree;nt.nodes.clear();rl=nt.nodes.new('CompositorNodeRLayers');den=nt.nodes.new('CompositorNodeDenoise');den.prefilter='ACCURATE';out=nt.nodes.new('CompositorNodeComposite')
 nt.links.new(rl.outputs['Image'],den.inputs['Image'])
 nt.links.new(rl.outputs['Denoising Normal'],den.inputs['Normal']);nt.links.new(rl.outputs['Denoising Albedo'],den.inputs['Albedo'])
 nt.links.new(den.outputs['Image'],out.inputs['Image'])
 s.cycles.samples=24;s.cycles.adaptive_threshold=.06;s.cycles.adaptive_min_samples=12
 for m in bpy.data.materials:
  if not m.use_nodes:continue
  bs=m.node_tree.nodes.get('Principled BSDF')
  if not bs:continue
  if 'architectural glass' in m.name.lower() or 'low-e visual' in m.name.lower():
   bs.inputs['Base Color'].default_value=color('#CADAD7');bs.inputs['Roughness'].default_value=.026;bs.inputs['Transmission Weight'].default_value=.82;bs.inputs['IOR'].default_value=1.45
  if 'Satin anodised' in m.name:
   bs.inputs['Base Color'].default_value=color('#B28D5C');bs.inputs['Metallic'].default_value=.72;bs.inputs['Roughness'].default_value=.28
  if m.name=='Context ground':bs.inputs['Base Color'].default_value=color('#66765E')
 # Remove coarse skyline placeholders and use a landscaped presentation context instead.
 for o in list(s.objects):
  if o.name.startswith(('Context skyline','Context glazed band')):bpy.data.objects.remove(o,do_unlink=True)
 for o in list(s.objects):
  if o.name.startswith('Presentation tree') and o.location.z>5:
   o.scale*=1.65
 prototypes=[o for o in s.objects if o.name.startswith('Presentation tree') and o.location.z<.1][:6]
 for i in range(37):
  for proto in prototypes[:2]:
   ob=proto.copy();ob.data=proto.data;s.collection.objects.link(ob)
   ob.name='Presentation / distant tree belt';ob.location=(-125+i*7,64+(i%4)*5,0);ob.scale=(1.45+(i%4)*.1,)*3;ob.rotation_euler.z=i*1.4
 # Keep the whole building in opening and closing compositions.
 cam=s.camera
 if shot in ['01_hero','06_dusk']:
  cam.animation_data_clear();cam.data.animation_data_clear()
  start=Vector((83,-124,47) if shot=='01_hero' else (-88,-123,47));end=Vector((67,-120,44) if shot=='01_hero' else (-105,-118,48))
  cam.data.lens=38
  for fr in range(1,97):
   u=(fr-1)/95;cam.location=start.lerp(end,u);target=Vector((0,0,26));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.dof.focus_distance=(target-cam.location).length
   cam.keyframe_insert('location',frame=fr);cam.keyframe_insert('rotation_euler',frame=fr);cam.data.keyframe_insert('dof.focus_distance',frame=fr)
  s['camera_start']=list(start);s['camera_end']=list(end)
 # Evening light is deliberately blue-hour rather than the orange test sky.
 if shot=='06_dusk':
  w=s.world.node_tree;w.nodes.clear();tex=w.nodes.new('ShaderNodeTexCoord');sep=w.nodes.new('ShaderNodeSeparateXYZ');ramp=w.nodes.new('ShaderNodeValToRGB');bg=w.nodes.new('ShaderNodeBackground');outw=w.nodes.new('ShaderNodeOutputWorld')
  ramp.color_ramp.elements[0].position=0;ramp.color_ramp.elements[0].color=(.22,.32,.47,1)
  ramp.color_ramp.elements[1].position=.8;ramp.color_ramp.elements[1].color=(.035,.085,.19,1)
  w.links.new(tex.outputs['Normal'],sep.inputs['Vector']);w.links.new(sep.outputs['Z'],ramp.inputs['Fac']);w.links.new(ramp.outputs['Color'],bg.inputs['Color']);bg.inputs['Strength'].default_value=.38;w.links.new(bg.outputs['Background'],outw.inputs['Surface'])
  light=bpy.data.lights.get('Late afternoon sun');light.energy=.9;light.color=(.56,.70,1);light.angle=math.radians(5)
  s.view_settings.exposure=.35
  bs=bpy.data.materials['Interior warm luminosity'].node_tree.nodes.get('Principled BSDF');bs.inputs['Emission Strength'].default_value=9
 else:
  sky=next(n for n in s.world.node_tree.nodes if n.type=='TEX_SKY');sky.dust_density=.4;sky.air_density=.9
 # Gentle physical light pools at the arrival canopy and terrace recesses.
 if shot=='06_dusk':
  for i,(pos,power,size) in enumerate([((0,-15,3.7),550,9),((-6,-7.5,38.9),140,3),((6,-7.5,38.9),140,3),((-6,-7.5,19.9),100,3),((6,-7.5,19.9),100,3)]):
   data=bpy.data.lights.new('Presentation warm light '+str(i),'AREA');data.energy=power;data.color=(1,.64,.3);data.shape='DISK';data.size=size
   ob=bpy.data.objects.new(data.name,data);s.collection.objects.link(ob);ob.location=pos
 s.render.resolution_percentage=100;s.frame_set(1)
 s['denoising']='Compositor OpenImageDenoise with denoising normal and albedo guides'
 s['finish']='Reviewed framing; physically shaded material refinement; presentation landscape; blue hour'
 bpy.ops.wm.save_as_mainfile(filepath=str((a.output/path.name).resolve()),compress=True)
 if a.proof:
  s.render.resolution_percentage=75;s.frame_set(48);s.render.filepath=str((a.output/(path.stem+'.png')).resolve());t=time.monotonic();bpy.ops.render.render(write_still=True)
  reports.append({'shot':shot,'seconds':time.monotonic()-t,'compositor_guided_denoising':True})
  (a.output/'finish-report.json').write_text(json.dumps(reports,indent=2))
print('FINISH_COMPLETE '+json.dumps(reports))
