"""Build an editable metric office model from spec/building.json.

Run:
  blender --background --python blender/build_model.py -- --spec spec/building.json --output-dir dist
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import bpy

def cli():
    p=argparse.ArgumentParser()
    p.add_argument("--spec",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,default=Path("dist"))
    argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    return p.parse_args(argv)

def set_principled(mat, **values):
    mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf:return
    aliases={"base_color":["Base Color"],"metallic":["Metallic"],"roughness":["Roughness"],"transmission":["Transmission Weight","Transmission"],"alpha":["Alpha"]}
    for key,value in values.items():
        for name in aliases.get(key,[key]):
            sock=bsdf.inputs.get(name)
            if sock is not None:
                sock.default_value=value
                break

def material(name,color,metallic=0,roughness=.5,transmission=0,alpha=1):
    m=bpy.data.materials.new(name)
    set_principled(m,base_color=(*color,1),metallic=metallic,roughness=roughness,transmission=transmission,alpha=alpha)
    if alpha<1:m.surface_render_method="DITHERED"
    return m

def box(name,loc,dims,mat,collection=None,props=None):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o=bpy.context.object;o.name=name;o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mat)
    for k,v in (props or {}).items():o[k]=v
    if collection:
        for c in list(o.users_collection):c.objects.unlink(o)
        collection.objects.link(o)
    return o

def main():
    a=cli(); spec=json.loads(a.spec.read_text(encoding="utf-8"))
    bpy.ops.object.select_all(action="SELECT");bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.unit_settings.system="METRIC";scene.unit_settings.scale_length=1
    scene["project_name"]=spec["name"];scene["design_status"]="Teaching concept - not for construction"
    w=float(spec["footprint"]["width_m"]);d=float(spec["footprint"]["depth_m"])
    n=int(spec["storeys"]);h=float(spec["floor_height_m"]);slab=float(spec["slab_thickness_m"])
    col=float(spec["column_size_m"]);spacing=float(spec["facade"]["fin_spacing_m"]);fin=float(spec["facade"]["fin_depth_m"])
    concrete=material("Concrete warm",(.62,.60,.54),roughness=.72)
    glass=material("Low-E concept glass",(.08,.23,.28),roughness=.15,transmission=.38,alpha=.72)
    bronze=material("Bronze fins",(.42,.22,.08),metallic=.72,roughness=.28)
    dark=material("Dark metal",(.04,.05,.05),metallic=.65,roughness=.32)
    green=material("Landscape",(.12,.28,.10),roughness=.9)
    solar=material("PV",(.015,.04,.09),metallic=.3,roughness=.18)
    box("Site",(0,0,-.1),(float(spec["site"]["width_m"]),float(spec["site"]["depth_m"]),.2),green,props={"ifc_class":"IfcSite"})
    building=bpy.data.collections.new("Building");scene.collection.children.link(building)
    for level in range(1,n+1):
        c=bpy.data.collections.new(f"L{level:02d}");building.children.link(c)
        z0=(level-1)*h; zmid=z0+h/2
        box(f"L{level:02d}_Slab",(0,0,z0+slab/2),(w,d,slab),concrete,c,{"ifc_class":"IfcSlab","storey":level})
        for x in (-w/2+.7,w/2-.7):
            for y in (-d/2+.7,d/2-.7):
                box(f"L{level:02d}_Column",(x,y,zmid),(col,col,h-slab),concrete,c,{"ifc_class":"IfcColumn","storey":level})
        clear=h-.55; gz=z0+.3+clear/2
        nx=max(2,math.ceil(w/spacing));ny=max(2,math.ceil(d/spacing));bx=w/nx;by=d/ny
        for side in (-1,1):
            y=side*d/2
            for i in range(nx):
                x=-w/2+bx*(i+.5)
                box(f"L{level:02d}_Glass_NS",(x,y,gz),(bx-.06,.08,clear),glass,c,{"ifc_class":"IfcCurtainWall","storey":level})
                box(f"L{level:02d}_Fin_NS",(x-bx/2,y+side*fin/2,gz),(.08,fin,clear),bronze,c,{"ifc_class":"IfcShadingDevice","storey":level})
        for side in (-1,1):
            x=side*w/2
            for i in range(ny):
                y=-d/2+by*(i+.5)
                box(f"L{level:02d}_Glass_EW",(x,y,gz),(.08,by-.06,clear),glass,c,{"ifc_class":"IfcCurtainWall","storey":level})
                box(f"L{level:02d}_Fin_EW",(x+side*fin/2,y-by/2,gz),(fin,.08,clear),bronze,c,{"ifc_class":"IfcShadingDevice","storey":level})
    rz=n*h
    box("Roof",(0,0,rz+slab/2),(w,d,slab),concrete,building,{"ifc_class":"IfcRoof"})
    pv=spec["pv"];rows=int(pv["rows"]);cols=int(pv["columns"]);pw,pd=1.1,1.9;sx,sy=pw+.25,pd+.35
    x0=-(cols-1)*sx/2;y0=-(rows-1)*sy/2
    for r in range(rows):
        for cc in range(cols):
            o=box("PV_Module",(x0+cc*sx,y0+r*sy,rz+.6),(pw,pd,.06),solar,building,{"ifc_class":"IfcBuildingElementProxy","object_type":"Photovoltaic module"})
            o.rotation_euler.x=math.radians(8)
    box("Entrance_Canopy",(0,-d/2-2,3.2),(10,4,.22),dark,building,{"ifc_class":"IfcRoof"})
    a.output_dir.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str((a.output_dir/"building.blend").resolve()))
    bpy.ops.export_scene.gltf(filepath=str((a.output_dir/"building.glb").resolve()),export_format="GLB")
    meta={"name":spec["name"],"storeys":n,"gross_concept_area_m2":w*d*n,"height_m":h*n,"pv_modules":rows*cols,"design_status":"Teaching concept - not for construction"}
    (a.output_dir/"model-meta.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print(json.dumps(meta))

if __name__=="__main__":main()
