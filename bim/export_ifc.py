"""Export a small conceptual IFC4 model from the same JSON spec.
Requires: pip install 'ifcopenshell>=0.8,<0.9'
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import ifcopenshell
from ifcopenshell import guid

def point(m,xyz):return m.create_entity("IfcCartesianPoint",Coordinates=tuple(float(v) for v in xyz))
def direction(m,xyz):return m.create_entity("IfcDirection",DirectionRatios=tuple(float(v) for v in xyz))
def axis3(m,xyz=(0,0,0)):return m.create_entity("IfcAxis2Placement3D",Location=point(m,xyz),Axis=direction(m,(0,0,1)),RefDirection=direction(m,(1,0,0)))
def placement(m,xyz=(0,0,0),relative_to=None):return m.create_entity("IfcLocalPlacement",PlacementRelTo=relative_to,RelativePlacement=axis3(m,xyz))
def aggregates(m,parent,children):return m.create_entity("IfcRelAggregates",GlobalId=guid.new(),OwnerHistory=None,Name=None,Description=None,RelatingObject=parent,RelatedObjects=list(children))
def box_rep(m,ctx,w,d,h):
    p2=m.create_entity("IfcAxis2Placement2D",Location=m.create_entity("IfcCartesianPoint",Coordinates=(0.0,0.0)))
    prof=m.create_entity("IfcRectangleProfileDef",ProfileType="AREA",ProfileName=None,Position=p2,XDim=float(w),YDim=float(d))
    solid=m.create_entity("IfcExtrudedAreaSolid",SweptArea=prof,Position=axis3(m),ExtrudedDirection=direction(m,(0,0,1)),Depth=float(h))
    shape=m.create_entity("IfcShapeRepresentation",ContextOfItems=ctx,RepresentationIdentifier="Body",RepresentationType="SweptSolid",Items=[solid])
    return m.create_entity("IfcProductDefinitionShape",Name=None,Description=None,Representations=[shape])
def main():
    p=argparse.ArgumentParser();p.add_argument("--spec",type=Path,required=True);p.add_argument("--output",type=Path,default=Path("dist/building.ifc"));a=p.parse_args()
    s=json.loads(a.spec.read_text(encoding="utf-8"));m=ifcopenshell.file(schema="IFC4")
    units=m.create_entity("IfcUnitAssignment",Units=[m.create_entity("IfcSIUnit",UnitType="LENGTHUNIT",Prefix=None,Name="METRE"),m.create_entity("IfcSIUnit",UnitType="AREAUNIT",Prefix=None,Name="SQUARE_METRE"),m.create_entity("IfcSIUnit",UnitType="VOLUMEUNIT",Prefix=None,Name="CUBIC_METRE")])
    ctx=m.create_entity("IfcGeometricRepresentationContext",ContextIdentifier="Body",ContextType="Model",CoordinateSpaceDimension=3,Precision=1e-5,WorldCoordinateSystem=axis3(m),TrueNorth=direction(m,(0,1,0)))
    project=m.create_entity("IfcProject",GlobalId=guid.new(),OwnerHistory=None,Name=s["name"],Description="Teaching template",ObjectType=None,LongName=None,Phase=None,RepresentationContexts=[ctx],UnitsInContext=units)
    site=m.create_entity("IfcSite",GlobalId=guid.new(),OwnerHistory=None,Name="Teaching Site",Description=None,ObjectType=None,ObjectPlacement=placement(m),Representation=None,LongName=None,CompositionType="ELEMENT",RefLatitude=None,RefLongitude=None,RefElevation=None,LandTitleNumber=None,SiteAddress=None)
    building=m.create_entity("IfcBuilding",GlobalId=guid.new(),OwnerHistory=None,Name=s["name"],Description=None,ObjectType=None,ObjectPlacement=placement(m),Representation=None,LongName=None,CompositionType="ELEMENT",ElevationOfRefHeight=None,ElevationOfTerrain=None,BuildingAddress=None)
    aggregates(m,project,[site]);aggregates(m,site,[building])
    n=int(s["storeys"]);fh=float(s["floor_height_m"]);w=float(s["footprint"]["width_m"]);d=float(s["footprint"]["depth_m"]);t=float(s["slab_thickness_m"]);storeys=[]
    for level in range(1,n+1):
        z=(level-1)*fh
        st=m.create_entity("IfcBuildingStorey",GlobalId=guid.new(),OwnerHistory=None,Name=f"Level {level:02d}",Description=None,ObjectType=None,ObjectPlacement=placement(m,(0,0,z)),Representation=None,LongName=None,CompositionType="ELEMENT",Elevation=z)
        slab=m.create_entity("IfcSlab",GlobalId=guid.new(),OwnerHistory=None,Name=f"L{level:02d} Concept Slab",Description="Teaching concept quantity",ObjectType=None,ObjectPlacement=placement(m,(-w/2,-d/2,z)),Representation=box_rep(m,ctx,w,d,t),Tag=None,PredefinedType="FLOOR")
        m.create_entity("IfcRelContainedInSpatialStructure",GlobalId=guid.new(),OwnerHistory=None,Name=None,Description=None,RelatedElements=[slab],RelatingStructure=st);storeys.append(st)
    aggregates(m,building,storeys)
    a.output.parent.mkdir(parents=True,exist_ok=True);m.write(str(a.output));print(f"Wrote IFC4 with {len(storeys)} storeys: {a.output}")
if __name__=="__main__":main()
