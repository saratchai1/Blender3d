from __future__ import annotations
import argparse, math, sys
from pathlib import Path
import bpy
from mathutils import Vector


def args():
    av=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True); p.add_argument('--export-glb',type=Path); p.add_argument('--preview',type=Path); return p.parse_args(av)

def mat(name,color,rough=.55,metal=0,alpha=1,trans=0):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name); m.diffuse_color=(*color,alpha); m.use_nodes=True
    b=m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value=(*color,alpha)
        if 'Roughness' in b.inputs:b.inputs['Roughness'].default_value=rough
        if 'Metallic' in b.inputs:b.inputs['Metallic'].default_value=metal
        if 'Alpha' in b.inputs:b.inputs['Alpha'].default_value=alpha
        if trans and 'Transmission Weight' in b.inputs:b.inputs['Transmission Weight'].default_value=trans
    return m

def get_col(name):
    c=bpy.data.collections.get(name)
    if not c:c=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c)
    return c

def box(name,loc,dims,m,rot=(0,0,0),bevel=.02,col=None,semantic=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc,rotation=rot); o=bpy.context.object; o.name=name; o.dimensions=dims; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.clear(); o.data.materials.append(m)
    if bevel:
        md=o.modifiers.new('Soft edges','BEVEL'); md.width=bevel; md.segments=2
    if semantic:o['derived_from_pascal_id']=semantic
    if col:
        for c in list(o.users_collection):c.objects.unlink(o)
        col.objects.link(o)
    return o

def cyl(name,loc,r,depth,m,col):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=r,depth=depth,location=loc); o=bpy.context.object;o.name=name;o.data.materials.append(m)
    for c in list(o.users_collection):c.objects.unlink(o)
    col.objects.link(o);return o

def ball(name,loc,r,m,col):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=r,location=loc);o=bpy.context.object;o.name=name;o.data.materials.append(m)
    for c in list(o.users_collection):c.objects.unlink(o)
    col.objects.link(o);return o

def sloped_roof_prism(name,x0,z0,x1,z1,y0,y1,thickness,m,col,semantic):
    # Explicit vertices avoid transform/rotation ambiguity and guarantee both roof planes meet at the ridge.
    v=[
        (x0,y0,z0),(x1,y0,z1),(x1,y1,z1),(x0,y1,z0),
        (x0,y0,z0-thickness),(x1,y0,z1-thickness),(x1,y1,z1-thickness),(x0,y1,z0-thickness),
    ]
    f=[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    mesh=bpy.data.meshes.new(name+'_mesh'); mesh.from_pydata(v,[],f); mesh.update()
    o=bpy.data.objects.new(name,mesh); col.objects.link(o); o.data.materials.append(m); o['derived_from_pascal_id']=semantic
    bevel=o.modifiers.new('Roof edge softening','BEVEL'); bevel.width=.018; bevel.segments=2
    return o

def remove_old_visual_noise():
    for o in list(bpy.data.objects):
        n=o.name.lower()
        if n.startswith('rseg_house_200sqm_') or n.endswith('_zone') or n.endswith('_label') or n=='site_ground':
            bpy.data.objects.remove(o,do_unlink=True)

def recolor_base(M):
    # Reuse semantic geometry, but correct the palette to architectural materials.
    for o in bpy.data.objects:
        if not getattr(o,'data',None) or not hasattr(o.data,'materials') or not o.data.materials:continue
        n=o.name.lower()
        if '_glass' in n:o.data.materials[0]=M['glass']
        elif '_frame_' in n:o.data.materials[0]=M['charcoal']
        elif '_leaf' in n:o.data.materials[0]=M['wood']
        elif '_seg_' in n:o.data.materials[0]=M['stucco']
        elif 'slab_' in n or '_part_' in n:o.data.materials[0]=M['concrete']
        elif 'stair_step' in n:o.data.materials[0]=M['wood']

def add_roof(C,M):
    W=D=10.; over=.85; rise=2.0; eave=6.42; ridge=eave+rise; y0=-over; y1=D+over
    sloped_roof_prism('rseg_house_200sqm_west',-over,eave,W/2,ridge,y0,y1,.14,M['roof'],C,'rseg_house_200sqm')
    sloped_roof_prism('rseg_house_200sqm_east',W/2,ridge,W+over,eave,y0,y1,.14,M['roof'],C,'rseg_house_200sqm')
    box('roof_ridge',(W/2,D/2,ridge+.025),(.20,D+2*over+.12,.16),M['charcoal'],bevel=.025,col=C,semantic='rseg_house_200sqm')
    box('roof_gutter_w',(-over,D/2,eave-.05),(.16,D+2*over,.18),M['charcoal'],bevel=.02,col=C,semantic='rseg_house_200sqm')
    box('roof_gutter_e',(W+over,D/2,eave-.05),(.16,D+2*over,.18),M['charcoal'],bevel=.02,col=C,semantic='rseg_house_200sqm')

def add_facade(C,M):
    # Base and floor reveal
    box('arch_plinth',(5,5,.10),(10.36,10.36,.20),M['stone'],bevel=.03,col=C)
    for k,(x,y,dx,dy) in enumerate([(5,-.10,10.3,.14),(10.10,5,.14,10.3),(5,10.10,10.3,.14),(-.10,5,.14,10.3)]):
        box(f'arch_floor_band_{k}',(x,y,3.28),(dx,dy,.18),M['charcoal'],bevel=.02,col=C)
    # Main porch and canopy at door_g_main
    box('arch_entry_step',(7.7,-.68,.15),(2.5,1.30,.24),M['stone'],bevel=.04,col=C,semantic='door_g_main')
    box('arch_entry_canopy',(7.7,-.78,2.78),(2.75,1.65,.16),M['charcoal'],bevel=.04,col=C,semantic='door_g_main')
    for x in (6.48,8.92):box('arch_entry_post_'+str(x),(x,-1.22,1.43),(.12,.12,2.86),M['charcoal'],bevel=.02,col=C,semantic='door_g_main')
    # Upper front balcony shades the living room below.
    box('arch_balcony_slab',(2.7,-.68,3.22),(4.65,1.28,.18),M['concrete'],bevel=.04,col=C,semantic='zone_u_master')
    box('arch_balcony_glass',(2.7,-1.24,3.86),(4.40,.035,1.05),M['glass'],bevel=0,col=C,semantic='zone_u_master')
    box('arch_balcony_toprail',(2.7,-1.26,4.40),(4.62,.075,.08),M['charcoal'],bevel=.02,col=C,semantic='zone_u_master')
    for i,x in enumerate((.5,1.35,2.2,3.05,3.9,4.85)):box(f'arch_balcony_post_{i}',(x,-1.25,3.87),(.045,.045,1.04),M['charcoal'],bevel=.005,col=C,semantic='zone_u_master')
    # Timber fins give the stair/entry volume a tropical identity.
    for i in range(8):box(f'arch_timber_fin_{i}',(5.35+i*.20,-.17,4.86),(.085,.18,2.42),M['wood_light'],bevel=.015,col=C,semantic='zone_g_dining_stair')
    # Rear shading ledge
    box('arch_rear_awning',(2.4,10.42,2.48),(3.4,.85,.13),M['charcoal'],bevel=.03,col=C,semantic='zone_g_kitchen')

def add_site(C,M):
    box('site_ground_v2',(5,5,-.12),(20,20,.20),M['site'],bevel=0,col=C)
    box('site_driveway',(7.7,-4.0,.01),(3.25,8.2,.07),M['path'],bevel=.035,col=C)
    box('site_walk',(4.9,-1.55,.015),(2.1,2.0,.075),M['path'],bevel=.035,col=C)
    for j,(x,y,s) in enumerate([(0,-2.7,1),(10.8,-2.8,.9),(-1.0,7.8,1.1),(11.1,8.0,1.0)]):
        cyl(f'plant_trunk_{j}',(x,y,.8*s),.09*s,1.6*s,M['wood'],C); ball(f'plant_crown_{j}',(x,y,1.95*s),.82*s,M['plant'],C)

def camera_light():
    sc=bpy.context.scene; sc.render.resolution_x=1400;sc.render.resolution_y=1000;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.render.film_transparent=False
    try:sc.render.engine='BLENDER_EEVEE_NEXT'
    except:pass
    w=sc.world or bpy.data.worlds.new('World');sc.world=w;w.color=(.035,.045,.055)
    for o in list(bpy.data.objects):
        if o.type in {'LIGHT','CAMERA'}:bpy.data.objects.remove(o,do_unlink=True)
    bpy.ops.object.light_add(type='SUN',location=(3,-6,13));sun=bpy.context.object;sun.data.energy=2.8;sun.rotation_euler=(math.radians(32),math.radians(-18),math.radians(-30))
    bpy.ops.object.light_add(type='AREA',location=(3,-8,8));a=bpy.context.object;a.data.energy=1100;a.data.size=7
    bpy.ops.object.light_add(type='AREA',location=(11,7,9));a=bpy.context.object;a.data.energy=650;a.data.size=6
    bpy.ops.object.camera_add(location=(15.5,-18.0,10.8));cam=bpy.context.object;target=Vector((5,4.8,3.55));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=52;sc.camera=cam

def main():
    a=args();C=get_col('40_Architecture_v2');S=get_col('00_Site_v2')
    M={
      'stucco':mat('V2_Stucco',(.93,.91,.85),.82),'charcoal':mat('V2_Charcoal',(.055,.065,.075),.34,.18),'concrete':mat('V2_Concrete',(.36,.37,.37),.78),'stone':mat('V2_Stone',(.54,.49,.41),.88),'wood':mat('V2_Wood',(.34,.16,.065),.48),'wood_light':mat('V2_WoodLight',(.49,.25,.10),.50),'glass':mat('V2_Glass',(.10,.30,.41),.08,alpha=.30,trans=.72),'roof':mat('V2_Roof',(.075,.085,.09),.38,.12),'site':mat('V2_Site',(.18,.29,.17),.95),'path':mat('V2_Path',(.50,.48,.43),.88),'plant':mat('V2_Plant',(.10,.28,.12),.90)}
    remove_old_visual_noise();recolor_base(M);add_roof(C,M);add_facade(C,M);add_site(S,M);camera_light();bpy.context.scene['model_version']='house_200sqm_v2_modern_tropical_mesh_roof'
    a.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()))
    if a.export_glb:a.export_glb.parent.mkdir(parents=True,exist_ok=True);bpy.ops.export_scene.gltf(filepath=str(a.export_glb.resolve()),export_format='GLB',export_extras=True)
    if a.preview:a.preview.parent.mkdir(parents=True,exist_ok=True);bpy.context.scene.render.filepath=str(a.preview.resolve());bpy.ops.render.render(write_still=True)
    print('HOUSE_V2_ENHANCE_OK')
if __name__=='__main__':main()
