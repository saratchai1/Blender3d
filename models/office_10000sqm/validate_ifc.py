#!/usr/bin/env python3
"""Strict semantic and geometry checks for the SOLSTICE 14 IFC4 export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
from ifcopenshell.util.element import get_psets


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("ifc",type=Path); args=parser.parse_args()
    if not args.ifc.is_file() or args.ifc.stat().st_size < 10000:
        raise AssertionError("IFC file is missing or implausibly small")
    model=ifcopenshell.open(str(args.ifc))
    assert model.schema == "IFC4", model.schema
    projects=model.by_type("IfcProject"); sites=model.by_type("IfcSite"); buildings=model.by_type("IfcBuilding"); storeys=model.by_type("IfcBuildingStorey")
    assert len(projects)==1 and len(sites)==1 and len(buildings)==1
    assert len(storeys)==14, len(storeys)
    storeys=sorted(storeys,key=lambda s:s.Elevation or 0)
    assert [round(float(s.Elevation or 0),1) for s in storeys] == [0.0,5.0,9.5,13.3,17.1,20.9,24.7,28.5,32.3,36.1,39.9,43.7,47.5,51.3]
    spaces=model.by_type("IfcSpace"); assert len(spaces)==14
    area_total=0.0
    for space in spaces:
        p=get_psets(space).get("Pset_SolsticeArea",{})
        area_total += float(p.get("GrossConceptArea",0))
    assert abs(area_total-10000.0)<1e-6, area_total
    project_pset=get_psets(projects[0]).get("Pset_SolsticeProject",{})
    assert float(project_pset.get("GrossConceptFloorArea",0))==10000.0
    assert int(project_pset.get("OccupiedStoreys",0))==14
    assert project_pset.get("EnergySimulated") is False
    assert model.by_type("IfcSlab"), "No slabs"
    assert model.by_type("IfcColumn"), "No columns"
    assert model.by_type("IfcCurtainWall"), "No curtain walls"
    assert model.by_type("IfcShadingDevice"), "No shading devices"
    assert model.by_type("IfcStair"), "No stairs"
    represented=[p for p in model.by_type("IfcProduct") if getattr(p,"Representation",None)]
    assert len(represented)>=60, len(represented)
    # Verify that every represented product can be tessellated by IfcOpenShell's geometry engine.
    settings=ifcopenshell.geom.settings()
    geometry_failures=[]; checked=0; triangles=0
    for product in represented:
        try:
            shape=ifcopenshell.geom.create_shape(settings,product)
            verts=len(shape.geometry.verts)//3; faces=len(shape.geometry.faces)//3
            if verts <= 0 or faces <= 0: raise ValueError("empty shape")
            checked += 1; triangles += faces
        except Exception as exc:
            geometry_failures.append(f"{product.is_a()} #{product.id()} {product.Name}: {exc}")
    assert not geometry_failures, "\n".join(geometry_failures[:20])
    # Each storey must contain at least the floor slab and facade/structure content.
    empty=[]
    for s in storeys:
        contained=[]
        for rel in getattr(s,"ContainsElements",[]) or []: contained.extend(rel.RelatedElements)
        if len(contained)<4: empty.append((s.Name,len(contained)))
    assert not empty, empty
    pv=[e for e in model.by_type("IfcBuildingElementProxy") if getattr(e,"ObjectType",None)=="Photovoltaic array"]
    assert len(pv)==1
    pv_pset=get_psets(pv[0]).get("Pset_SolsticePV",{})
    assert int(pv_pset.get("ModuleCount",0))==96
    assert abs(float(pv_pset.get("DCNameplateCapacitykWp",0))-43.2)<1e-6
    result={"status":"PASS","schema":model.schema,"bytes":args.ifc.stat().st_size,"entities":len(list(model)),"storeys":len(storeys),"spaces":len(spaces),"representedProducts":checked,"triangles":triangles,"grossConceptArea":area_total,"pvModules":96}
    print(json.dumps(result,indent=2))


if __name__=="__main__": main()
