#!/usr/bin/env python3
"""Export SOLSTICE 14 semantic scene JSON to a compact, usable IFC4 model.

The exporter preserves the 14-storey spatial tree and groups thousands of WebGL
primitives into BIM-oriented per-storey elements. Web coordinates (X east, Y up,
Z south) are converted to normal IFC coordinates (X east, Y north, Z up).

Requires IfcOpenShell 0.8.3.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import ifcopenshell
import ifcopenshell.api
import numpy as np

STATUS = "Concept design only; not for construction, permitting or procurement"


def api(name: str, model, **kwargs):
    return ifcopenshell.api.run(name, model, **kwargs)


def unit_geometry(shape: str):
    """Return vertices/faces around origin, matching the web model dimensions."""
    if shape == "box":
        vertices = [
            (-.5,-.5,-.5),(.5,-.5,-.5),(.5,.5,-.5),(-.5,.5,-.5),
            (-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5),
        ]
        faces = [
            (0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)
        ]
        return vertices, faces
    if shape == "cylinder":
        seg = 10
        vertices = []
        for y in (-.5,.5):
            for i in range(seg):
                a = 2*math.pi*i/seg
                vertices.append((.5*math.cos(a),y,.5*math.sin(a)))
        faces = []
        for i in range(seg):
            j=(i+1)%seg
            faces.append((i,j,seg+j,seg+i))
        faces.append(tuple(range(seg-1,-1,-1)))
        faces.append(tuple(seg+i for i in range(seg)))
        return vertices, faces
    if shape == "sphere":
        rows, cols = 6, 10
        vertices=[(0,.5,0)]
        for r in range(1,rows):
            a=math.pi*r/rows
            for c in range(cols):
                b=2*math.pi*c/cols
                vertices.append((.5*math.sin(a)*math.cos(b),.5*math.cos(a),.5*math.sin(a)*math.sin(b)))
        bottom=len(vertices); vertices.append((0,-.5,0)); faces=[]
        for c in range(cols): faces.append((0,1+c,1+(c+1)%cols))
        for r in range(rows-2):
            base=1+r*cols; nxt=base+cols
            for c in range(cols):
                j=(c+1)%cols; faces.append((base+c,nxt+c,nxt+j,base+j))
        base=1+(rows-2)*cols
        for c in range(cols): faces.append((base+c,bottom,base+(c+1)%cols))
        return vertices, faces
    raise ValueError(f"Unsupported primitive shape: {shape}")


def transform_vertex(vertex, matrix, storey_elevation: float):
    x,y,z=vertex; m=matrix
    wx=m[0]*x+m[4]*y+m[8]*z+m[12]
    wy=m[1]*x+m[5]*y+m[9]*z+m[13]
    wz=m[2]*x+m[6]*y+m[10]*z+m[14]
    # Web: +Z south / +Y up. IFC: +Y north / +Z up.
    return (wx,-wz,wy-storey_elevation)


def classify(obj):
    name=obj["name"].lower(); layer=int(obj["layer"]); floor=int(obj["floor"])
    if any(k in name for k in ("visitor","electric car","car wheel")):
        return None
    if floor == 0:
        if any(k in name for k in ("tree","shrub","planting","garden","lawn")) or layer == 4:
            return ("Site landscape","IfcBuildingElementProxy")
        return ("Site hardscape","IfcBuildingElementProxy")
    if "pv " in name or name.startswith("pv") or "solar" in name:
        return ("Photovoltaic array","IfcBuildingElementProxy")
    if layer == 2 or "glazing" in name or "curtain" in name:
        return ("Curtain wall","IfcCurtainWall")
    if layer == 3 or "fin" in name or "shade" in name or "spandrel" in name:
        return ("External shading","IfcShadingDevice")
    if "column" in name:
        return ("Columns","IfcColumn")
    if "stair" in name:
        return ("Stairs","IfcStair")
    if "floor plate" in name:
        return ("Floor slab","IfcSlab")
    if "roof" in name or "canopy" in name or "parapet" in name or "plant screen" in name:
        return ("Roof and canopy","IfcRoof")
    if layer == 6 or "lift bank" in name:
        return ("Core walls / lift bank","IfcWall")
    if layer == 5:
        return ("Indicative furniture","IfcFurniture")
    if layer == 4:
        return ("Terrace landscape","IfcBuildingElementProxy")
    return ("Primary building fabric","IfcBuildingElementProxy")


def combined_mesh(objects: Iterable[dict], elevation: float):
    vertices=[]; faces=[]
    cache={}
    for obj in objects:
        if obj["shape"] not in cache: cache[obj["shape"]]=unit_geometry(obj["shape"])
        base_vertices, base_faces=cache[obj["shape"]]; offset=len(vertices)
        vertices.extend(transform_vertex(v,obj["matrix"],elevation) for v in base_vertices)
        faces.extend(tuple(offset+i for i in face) for face in base_faces)
    return vertices, faces


def add_pset(model, product, name, properties):
    pset=api("pset.add_pset",model,product=product,name=name)
    api("pset.edit_pset",model,pset=pset,properties=properties)


def place(model, product, z: float=0.0):
    matrix=np.eye(4); matrix[2,3]=z
    api("geometry.edit_object_placement",model,product=product,matrix=matrix,is_si=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--scene",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    scene=json.loads(args.scene.read_text(encoding="utf-8"))
    floors=scene["floors"]; spec=scene["spec"]
    if len(floors)!=14 or sum(float(f["area"]) for f in floors)!=10000:
        raise ValueError("Refusing IFC export: source scene is not the validated 14-storey / 10,000 m² design")

    model=api("project.create_file",None,version="IFC4")
    model.header.file_name.name=args.output.name
    model.header.file_name.description=("SOLSTICE 14 conceptual BIM export",)
    project=api("root.create_entity",model,ifc_class="IfcProject",name="SOLSTICE 14")
    project.Description="Modern tropical office concept — 14 storeys / 10,000 m²"
    units=[api("unit.add_si_unit",model,unit_type=t) for t in ("LENGTHUNIT","AREAUNIT","VOLUMEUNIT")]
    api("unit.assign_unit",model,units=units)
    model_ctx=api("context.add_context",model,context_type="Model")
    body_ctx=api("context.add_context",model,context_type="Model",context_identifier="Body",target_view="MODEL_VIEW",parent=model_ctx)

    site=api("root.create_entity",model,ifc_class="IfcSite",name="Concept Site")
    site.Description="Hypothetical 68 × 58 m design site; Bangkok climate assumption only, not surveyed geolocation"
    building=api("root.create_entity",model,ifc_class="IfcBuilding",name="SOLSTICE 14 Office")
    building.Description=STATUS
    api("aggregate.assign_object",model,products=[site],relating_object=project)
    api("aggregate.assign_object",model,products=[building],relating_object=site)
    place(model,site); place(model,building)
    add_pset(model,project,"Pset_SolsticeProject",{
        "GrossConceptFloorArea":10000.0,
        "OccupiedStoreys":14,
        "CoveredSkyGardenArea":144.0,
        "RoofDatum":55.1,
        "CoordinateBasis":"IFC X east, Y north, Z up; converted from web X east, Y up, Z south",
        "EnergySimulated":False,
        "ModelStatus":STATUS,
    })

    storeys={}
    for f in floors:
        n=int(f["level"]); elevation=float(f["y"])
        storey=api("root.create_entity",model,ifc_class="IfcBuildingStorey",name=f"Level {n:02d}")
        storey.Description=str(f["use"]); storey.Elevation=elevation
        api("aggregate.assign_object",model,products=[storey],relating_object=building); place(model,storey,elevation)
        storeys[n]=storey
        add_pset(model,storey,"Pset_SolsticeStorey",{
            "LevelNumber":n,"Elevation":elevation,"FloorToFloorHeight":float(f["height"]),
            "FloorPlateArea":float(f["area"]),"EnclosedConceptArea":float(f["enclosed"]),
            "CoveredSkyGardenArea":float(f["terrace"]),"ProposedUse":str(f["use"]),
        })
        space=api("root.create_entity",model,ifc_class="IfcSpace",name=f"L{n:02d} Concept Floor Area")
        space.Description=str(f["use"])
        api("aggregate.assign_object",model,products=[space],relating_object=storey); place(model,space,elevation)
        add_pset(model,space,"Pset_SolsticeArea",{
            "GrossConceptArea":float(f["area"]),"EnclosedConceptArea":float(f["enclosed"]),
            "CoveredSkyGardenArea":float(f["terrace"]),"AreaBasis":"Concept floor plate; not statutory GFA or net lettable area",
        })

    groups=defaultdict(list)
    for obj in scene["objects"]:
        key=classify(obj)
        if key is not None: groups[(int(obj["floor"]),*key)].append(obj)

    created=[]
    for (floor,category,ifc_class),objects in sorted(groups.items()):
        elevation=float(floors[floor-1]["y"]) if floor else 0.0
        vertices,faces=combined_mesh(objects,elevation)
        if not vertices or not faces: continue
        element=api("root.create_entity",model,ifc_class=ifc_class,name=f"L{floor:02d} {category}" if floor else category)
        element.Description=STATUS
        if hasattr(element,"ObjectType") and ifc_class=="IfcBuildingElementProxy": element.ObjectType=category
        if ifc_class=="IfcSlab" and hasattr(element,"PredefinedType"): element.PredefinedType="FLOOR"
        representation=api("geometry.add_mesh_representation",model,context=body_ctx,vertices=[vertices],faces=[faces],unit_scale=1.0)
        api("geometry.assign_representation",model,product=element,representation=representation)
        container=storeys[floor] if floor else site
        api("spatial.assign_container",model,products=[element],relating_structure=container)
        place(model,element,elevation)
        add_pset(model,element,"Pset_SolsticeSource",{
            "Category":category,"SourceObjectCount":len(objects),"SourceFloor":floor,
            "SourceLayers":",".join(str(v) for v in sorted({int(o["layer"]) for o in objects})),
            "GeometryType":"Grouped tessellated geometry","DesignStatus":STATUS,
        })
        if category=="Photovoltaic array":
            count=sum(1 for o in objects if o["name"]=="PV module 450 W target")
            add_pset(model,element,"Pset_SolsticePV",{
                "ModuleCount":count,"AssumedModulePowerW":450.0,"DCNameplateCapacitykWp":count*0.45,
                "PerformanceStatus":"Nameplate assumption only; no annual yield simulation",
            })
        created.append(element)

    args.output.parent.mkdir(parents=True,exist_ok=True)
    model.write(str(args.output))
    print(json.dumps({
        "schema":model.schema,"output":str(args.output),"storeys":len(storeys),
        "spaces":len(model.by_type("IfcSpace")),"groupedElements":len(created),
        "sourceObjects":len(scene["objects"]),"ifcEntities":len(list(model)),
        "grossConceptArea":sum(float(f["area"]) for f in floors),
    },indent=2))


if __name__=="__main__":
    main()
