# SOLSTICE 14 — IFC4 BIM export

This directory exports the same validated SOLSTICE 14 concept scene to **IFC4** using IfcOpenShell 0.8.3. The IFC is intended to be substantially more useful than a GLB-to-IFC mesh wrapper: it keeps a spatial BIM hierarchy, storey metadata, conceptual floor areas, BIM classes and custom property sets.

## Output

After the `office14` GitHub Action passes, the published file is:

`web/office_10000sqm/assets/solstice-14-office.ifc`

A machine-readable validation report is published beside it as:

`web/office_10000sqm/assets/solstice-14-office.ifc.validation.json`

The same files are included in the `solstice-14-office-10000sqm` workflow artifact.

## Spatial structure

```text
IfcProject  SOLSTICE 14
└─ IfcSite  Concept Site
   └─ IfcBuilding  SOLSTICE 14 Office
      ├─ IfcBuildingStorey  Level 01
      │  ├─ IfcSpace  L01 Concept Floor Area
      │  └─ architectural elements
      ├─ ...
      └─ IfcBuildingStorey  Level 14
```

There are exactly 14 `IfcBuildingStorey` entities. Each storey receives a conceptual `IfcSpace` carrying its proposed use and area data. The sum of `GrossConceptArea` is tested to equal exactly **10,000 m²**.

## BIM mapping

Thousands of small WebGL primitives are consolidated into per-storey BIM groups so the IFC remains practical to open and navigate instead of becoming a 4,500-item entourage dump.

| Source content | IFC class |
|---|---|
| Floor plates | `IfcSlab` |
| Columns | `IfcColumn` |
| Core / lift-bank mass | `IfcWall` |
| Stair enclosures and treads | `IfcStair` |
| Curtain glazing | `IfcCurtainWall` |
| External fins / shades / spandrels | `IfcShadingDevice` |
| Roof / canopy / parapet / roof screen | `IfcRoof` |
| Photovoltaic array | `IfcBuildingElementProxy`, ObjectType=`Photovoltaic array` |
| Indicative furniture | `IfcFurniture` |
| Terrace/site landscape and hardscape | `IfcBuildingElementProxy` |

People and cars are deliberately omitted from IFC because they are presentation entourage, not BIM assets.

## Coordinates and geometry

The web model uses X=east, Y=up, Z=south. IFC uses the conventional X=east, Y=north, Z=up. Export therefore applies:

```text
IFC X = web X
IFC Y = -web Z
IFC Z = web Y
```

Geometry is grouped tessellated IFC4 representation. Elements are storey-contained and placed at the corresponding storey elevation in metres. This keeps the actual designed shape, including rotated facade fins, rather than substituting generic bounding boxes.

The site remains explicitly **hypothetical**. Bangkok is only a climate/sun-study assumption, so the IFC does not pretend to contain a surveyed georeference.

## Property sets

`Pset_SolsticeProject` records conceptual GFA, number of storeys, roof datum, coordinate basis and the fact that energy performance has **not** been simulated.

`Pset_SolsticeStorey` records level number, elevation, floor-to-floor height, floor-plate area, enclosed conceptual area, covered sky-garden area and proposed use.

`Pset_SolsticeArea` is attached to each conceptual `IfcSpace` and carries the area basis. These are concept floor-plate figures, not certified statutory GFA or net lettable area.

`Pset_SolsticeSource` records source category, number of source 3D objects consolidated into that BIM element, source floor/layers, geometry type and design status.

`Pset_SolsticePV` records 96 modeled modules × assumed 450 W = 43.2 kWp DC nameplate. It explicitly does not claim annual generation.

## Generate locally

```sh
node web/office_10000sqm/tools/build.mjs
python -m pip install ifcopenshell==0.8.3
python models/office_10000sqm/export_ifc.py \
  --scene .generated/office_10000sqm/office.scene.json \
  --output .generated/office_10000sqm/solstice-14-office.ifc
python models/office_10000sqm/validate_ifc.py \
  .generated/office_10000sqm/solstice-14-office.ifc
```

## Validation gate

The workflow fails instead of publishing if any of the following are wrong:

- schema is not IFC4;
- project/site/building hierarchy is missing;
- storey count/elevations are wrong;
- 14 conceptual spaces are not present;
- conceptual area does not total exactly 10,000 m²;
- slab, column, curtain-wall, shading or stair classes are missing;
- fewer than 60 represented BIM products are present;
- IfcOpenShell cannot tessellate any represented product;
- a storey lacks sufficient contained architectural elements;
- the PV group does not carry 96 modules / 43.2 kWp.

This makes the published IFC a tested BIM exchange file, but it is still a **concept model**. It has no detailed doors, rooms, fire-rating, structural connections, MEP, code-compliant stairs/egress, surveyed coordinates or construction LOD. Use it for design coordination, visualization, quantity exploration and further BIM development — not for permitting or construction.
