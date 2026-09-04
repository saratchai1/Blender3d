from __future__ import annotations
import argparse, sys
from pathlib import Path
import bpy


def parse_args():
    av=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--export-glb',type=Path);p.add_argument('--preview',type=Path);return p.parse_args(av)

def collection(name):
    c=bpy.data.collections.get(name)
    if not c:c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c)
    return c

def gable(name,y,thickness,mat,col):
    # Vertical triangular infill at each gable end, matching the explicit roof mesh.
    z0=6.38;zr=8.42;x0=0.0;x1=10.0;xm=5.0
    ya=y-thickness/2;yb=y+thickness/2
    verts=[(x0,ya,z0),(x1,ya,z0),(xm,ya,zr),(x0,yb,z0),(xm,yb,zr),(x1,yb,z0)]
    faces=[(0,1,2),(3,4,5),(0,3,5,1),(1,5,4,2),(2,4,3,0)]
    mesh=bpy.data.meshes.new(name+'_mesh');mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);col.objects.link(o);o.data.materials.append(mat);o['derived_from_pascal_id']='rseg_house_200sqm'
    bevel=o.modifiers.new('Gable edge softening','BEVEL');bevel.width=.012;bevel.segments=2
    return o

def box(name,loc,dims,mat,col):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dims;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat)
    for c in list(o.users_collection):c.objects.unlink(o)
    col.objects.link(o);o['derived_from_pascal_id']='rseg_house_200sqm';return o

def main():
    a=parse_args();col=collection('40_Architecture_v3')
    stucco=bpy.data.materials.get('V2_Stucco');charcoal=bpy.data.materials.get('V2_Charcoal')
    if not stucco or not charcoal:raise RuntimeError('v2 architectural materials are missing')
    for n in ('arch_gable_south','arch_gable_north','arch_gable_base_south','arch_gable_base_north'):
        o=bpy.data.objects.get(n)
        if o:bpy.data.objects.remove(o,do_unlink=True)
    gable('arch_gable_south',0.0,.15,stucco,col);gable('arch_gable_north',10.0,.15,stucco,col)
    box('arch_gable_base_south',(5,-.02,6.40),(10.18,.20,.14),charcoal,col)
    box('arch_gable_base_north',(5,10.02,6.40),(10.18,.20,.14),charcoal,col)
    bpy.context.scene['model_version']='house_200sqm_v3_reviewed'
    a.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()))
    if a.export_glb:
        a.export_glb.parent.mkdir(parents=True,exist_ok=True);bpy.ops.export_scene.gltf(filepath=str(a.export_glb.resolve()),export_format='GLB',export_extras=True)
    if a.preview:
        a.preview.parent.mkdir(parents=True,exist_ok=True);bpy.context.scene.render.filepath=str(a.preview.resolve());bpy.ops.render.render(write_still=True)
    print('HOUSE_V3_FINALIZE_OK')
if __name__=='__main__':main()
