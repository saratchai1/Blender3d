# Blender3d Project Skill

## Purpose

This file is the operating contract and project knowledge map for AI agents working in `saratchai1/Blender3d`.

The project is not just a Blender scene. It is intended to become an agent-driven AEC/3D workflow spanning interactive web 3D, Blender automation, BIM/IFC, semantic scene data, 3D Gaussian Splatting, realistic rendering/animation, quantity takeoff, BOQ, and auditable 2D/3D quantity reconciliation.

Agents must preserve working pipelines, distinguish repository-verifiable implementation from plans, and never present conceptual geometry or inferred quantities as construction-certified information.

---

## 1. Canonical repository

- Repository: `saratchai1/Blender3d`
- Treat repository code, tests, generated validation reports, workflow configuration, and current documentation as evidence of implementation.
- Conversation/project context describes intent and desired direction, but it is not proof that a feature is implemented.
- Before claiming a capability exists, inspect the current repository state.
- Prefer extending existing pipelines over creating disconnected demos.

### Status vocabulary

Use these labels when describing project state:

- **Implemented** — repository-verifiable and usable in the current codebase.
- **Experimental** — code exists but has important limitations or incomplete validation.
- **In Progress** — active implementation exists but is not complete enough to call implemented.
- **Planned** — intended architecture or requested work with no complete repository implementation yet.
- **Assumption** — a design input that has not been independently verified.
- **Known Issue** — a verified limitation, defect, or missing requirement.

Never silently promote Planned or Experimental work to Implemented.

---

## 2. System architecture

Target architecture:

```text
                         AI Agent
                            |
              +-------------+-------------+
              |                           |
         Blender MCP                 OpenTakeoff MCP
              |                           |
      Blender / 3DGS                2D Plans / PDF
              |                           |
              +----------+        Measurements
              |          |               |
           Blender     Pascal            |
              |     Semantic Scene       |
              |          |               |
              +----------+---------------+
                         |
                  Unified BIM Identity
                         |
                       IFC4
                         |
                Quantity Reconciliation
                         |
                   Classified BOQ
                         |
             +-----------+-----------+
             |           |           |
            XLSX        CSV     Web Dashboard
             |                       |
             +---- Quantity / Cost / Audit ----+
```

This is the architectural direction. Individual links must still be marked Planned until repository code implements them.

---

## 3. Blender MCP

### Implemented baseline

The repository controls Blender through a pinned upstream Blender MCP package with a local compatibility/control layer.

Current repository documentation identifies:

- upstream: `sandraschi/blender-mcp`
- pinned commit: `6b51a6b302a149354d5c7820d077827f1129bb5c`
- Python 3.12+
- local launcher/control layer: `blender3d-control`

The upstream MCP already provides Blender scene, mesh, material, render, export, add-on, splatting, and live bridge capabilities. The local repository should contain project-specific compatibility and future AEC/tree tooling rather than modifying upstream unnecessarily.

### Windows workflow

Preferred setup sequence:

```powershell
.\scripts\setup.ps1
.\scripts\install-3dgs.ps1
.\scripts\doctor.ps1
```

Use the repository-generated MCP configuration instead of hard-coding paths when possible.

### Security rule

The HTTP MCP endpoint defaults to localhost and should remain local unless deliberately placed behind an authenticated TLS-capable gateway.

Do not expose a raw Blender/MCP control port directly to the public Internet.

---

## 4. 3D Gaussian Splatting

### Implemented baseline

The project uses KIRI `3DGS Render` as the modern 3DGS path.

Repository baseline:

- KIRI 3DGS Render 5.1.0
- intended Blender 5.1+ path
- compatibility layer bridges current KIRI operators into the pinned Blender MCP splatting interface
- modern native Blender PLY import is available as a geometry fallback

The compatibility layer exists because the pinned upstream MCP references legacy 3DGS installation/import behavior.

### Scientific/measurement rule

**3DGS is primarily a visual/context representation.**

Never infer a physical trunk diameter, building dimension, DBH, or engineering quantity directly from Gaussian ellipse/splat size.

For metric measurements, use underlying metric point geometry or explicit BIM geometry as the source of truth.

For tree/DBH work, preferred sources are LAS/LAZ/PLY metric point clouds and robust geometric fitting.

### Tree/point-cloud direction

Planned project-specific tools include:

- import LAS/LAZ/PLY point clouds;
- isolate a tree by stable ID or ROI;
- define standard or alternative measurement plane;
- slice trunk points;
- robust circle/ellipse/cylinder fitting;
- compute diameter, residual, and confidence;
- persist tree ID, coordinates, method, plane, and measurement status as semantic properties;
- distinguish `standard`, `alternative`, and `not measured` states;
- export CSV/JSON/GeoJSON.

Stable IDs such as `TREE_0066` should remain stable across scene data, Blender, MCP operations, measurement outputs, and exports.

---

## 5. Pascal integration

Pascal is an optional semantic/scene layer and is not currently a required runtime dependency of the Blender/3DGS stack.

Pinned Pascal references are stored under `integrations/pascal/`.

Intended roles:

- `pascalorg/editor` — semantic scene graph, plugin/viewer/MCP/capture architecture;
- `pascalorg/pascal-blender` — Pascal scene JSON to editable Blender objects while retaining semantic metadata;
- `pascalorg/plugin-trees` — reference for large tree sets, instancing, and selection proxies.

Pascal should complement Blender rather than replace Blender.

The desired pattern is:

```text
semantic object / stable ID
        |
     Pascal
        |
     Blender
        |
  IFC / analysis / render
```

Do not make Pascal a mandatory dependency for unrelated Blender operations unless there is a concrete technical reason.

---

## 6. House 200 m² prototype

The repository contains a 200 m² house prototype used to explore Blender + Pascal workflows.

Relevant paths include:

- `models/house_200sqm/house_spec.json`
- `models/house_200sqm/pascal/`
- `models/house_200sqm/blender/`
- `scripts/build-house-200sqm.ps1`

Treat this as a prototype/reference pipeline, not automatically as the architecture for every future building model.

---

## 7. SOLSTICE 14 office

### Design brief

SOLSTICE 14 is the current office-building concept:

- 14 above-ground occupied storeys
- conceptual total floor area: 10,000 m²
- modern tropical architectural language
- energy-conscious design intent
- interactive WebGL 2 model
- exportable GLB
- semantic scene JSON
- Blender import path
- IFC4 export path
- animation/render tooling

### Area schedule

Conceptual schedule:

| Floors | Use | Floor plate | Area/floor | Subtotal |
|---|---|---:|---:|---:|
| 1 | Lobby, cafe, arrival | 40 x 25 m | 1,000 m² | 1,000 m² |
| 2 | Conference, co-working | 40 x 25 m | 1,000 m² | 1,000 m² |
| 3–12 | Flexible office, gardens at L05/L10 | 34 x 20 m | 680 m² | 6,800 m² |
| 13–14 | Executive / meeting suites | 30 x 20 m | 600 m² | 1,200 m² |
| Total | 14 occupied levels | | | 10,000 m² |

The 10,000 m² value is a conceptual floor-plate total, not certified statutory GFA or net lettable area.

### Geometry/design facts

Current documented concept includes:

- ground floor-to-floor about 5.0 m;
- second floor about 4.5 m;
- remaining floors about 3.8 m;
- roof datum about +55.1 m;
- plant-screen height about 58.4 m;
- hypothetical 68 x 58 m site;
- no designed basement/parking structure;
- facade shading/fins;
- blue-green glazing;
- sky/recessed gardens;
- landscaped podium/roof elements;
- PV array;
- schematic lift/stair/core/furniture elements.

### Energy strategy

These are design targets/intent, not measured performance:

- external shading;
- Low-E glazing intent;
- initial SHGC target roughly 0.25–0.30;
- 96 modeled PV modules at assumed 450 W each = 43.2 kWp DC nameplate;
- daylight-responsive dimming intent;
- occupancy controls intent;
- efficient zoned cooling intent;
- floor-level metering intent.

Do not claim annual PV yield, energy savings percentage, EUI, OTTV compliance, LEED/TREES certification, net zero, daylight autonomy, glare compliance, or EnergyPlus validation unless a real analysis has been implemented and verified.

### Web 3D rule

The office web application must remain **actual interactive 3D**, not a rendered still or fake rotating image.

Useful interactions include orbit, zoom, pan, floor selection, facade/landscape visibility, envelope opening, fin-depth adjustment, explode, section, sun/shadow presets, day/night presentation, and GLB export.

Presentation rendering can coexist with the interactive model, but must not replace it.

---

## 8. GLB and semantic scene

The office build pipeline can generate:

- standalone/offline web application;
- `solstice-14.glb`;
- semantic `office.scene.json`.

The semantic scene is important because downstream IFC and quantity workflows should not rely only on visually inspecting a GLB mesh.

One world unit equals one metre in the documented web model.

Coordinate basis in the web model:

- X = east
- Y = up
- Z = south

---

## 9. Blender import and rendering

The exact exported GLB can be imported into Blender and saved as an organized `.blend` using the repository import script.

Blender is the preferred layer for:

- material refinement;
- lighting;
- camera choreography;
- environment/context;
- realistic still rendering;
- realistic animation;
- presentation-quality output;
- further editable geometry work where appropriate.

### Rendering quality rule

When the user requests a presentation render or animation, do not stop at a diagnostic viewport image unless explicitly requested.

Aim for architectural-visualization quality:

- deliberate camera composition;
- physically plausible materials;
- controlled daylight/artificial light;
- realistic reflections and glazing;
- landscape/context where appropriate;
- temporal pacing for animation;
- high enough sampling/resolution for presentation use.

Technical screenshots and validation renders should be labeled as such and not presented as final visualization.

---

## 10. IFC4 BIM pipeline

### Implemented baseline

SOLSTICE 14 has an IFC4 export pipeline using IfcOpenShell.

The IFC is intended to be more useful than a GLB-to-IFC mesh wrapper. Preserve:

```text
IfcProject
  -> IfcSite
    -> IfcBuilding
      -> 14 x IfcBuildingStorey
        -> IfcSpace
        -> architectural elements
```

There must be exactly 14 building storeys for the current SOLSTICE 14 concept unless the design itself changes.

### Current conceptual BIM mapping

| Source | IFC class |
|---|---|
| floor plates | `IfcSlab` |
| columns | `IfcColumn` |
| core / lift-bank mass | `IfcWall` |
| stairs | `IfcStair` |
| curtain glazing | `IfcCurtainWall` |
| fins / shades / spandrels | `IfcShadingDevice` |
| roof / canopy / parapet / roof screen | `IfcRoof` |
| PV array | `IfcBuildingElementProxy` with photovoltaic object type |
| indicative furniture | `IfcFurniture` |
| landscape/hardscape | `IfcBuildingElementProxy` |

Presentation entourage such as people and cars should not become BIM assets unless there is a deliberate downstream use.

### Coordinate conversion

Documented conversion from web coordinates to IFC:

```text
IFC X = web X
IFC Y = -web Z
IFC Z = web Y
```

### IFC property/provenance rule

Preserve or improve project/storey/source property sets so downstream systems can determine:

- design status;
- storey;
- conceptual area basis;
- source category;
- source geometry count;
- source layer/floor;
- energy-analysis status;
- PV assumptions where applicable.

### Validation gate

IFC publication should fail rather than silently publish when required spatial hierarchy, storeys, conceptual spaces, major BIM classes, geometry tessellation, or critical project assumptions are invalid.

---

## 11. IFC limitations

The current SOLSTICE 14 model is a **concept model**.

Known missing construction-level information includes, among other things:

- complete room layouts;
- detailed doors/openings;
- complete fire/egress design;
- accessible design verification;
- detailed structural system and connections;
- detailed MEP;
- facade engineering/maintenance design;
- parking/transport design;
- surveyed/georeferenced site;
- statutory GFA verification;
- construction LOD;
- procurement-ready specifications.

Therefore:

- do not call the IFC construction-ready;
- do not call quantities final procurement quantities;
- do not claim permitting/code compliance;
- do not claim certified GFA;
- do not infer missing building systems simply because an IFC file exists.

---

## 12. Quantity takeoff and BOQ direction

The user wants a usable BOQ/takeoff workflow, not only a visually attractive model.

The project should ultimately support two complementary quantity sources:

1. **3D/BIM quantities** from semantic model/IFC geometry.
2. **2D drawing takeoff** from construction drawings using OpenTakeoff or equivalent tooling.

These sources are for reconciliation and audit. They are **not automatically additive**.

### Critical anti-double-counting rule

If the same floor finish, wall, slab, opening, facade area, fixture, or other work item exists in both IFC and 2D takeoff, never sum both quantities blindly.

Each BOQ line should identify a quantity-source policy such as:

- IFC authoritative;
- 2D authoritative;
- reconciled;
- manual override;
- estimate/assumption.

Store both observed quantities when useful, but choose one approved quantity for pricing.

---

## 13. OpenTakeoff integration

### Current status

**Planned Integration** unless current repository code proves otherwise.

Upstream project: `Kentucky-ai/opentakeoff`.

OpenTakeoff is a takeoff/measurement engine for building plans with a browser canvas and an MCP interface. It should be treated as the project's 2D takeoff layer, not as a replacement for Blender or IFC.

### Useful OpenTakeoff capabilities

Depending on the pinned upstream version and feature gates, capabilities include:

- load/orient plan sheets;
- inspect sheet context and vectors;
- read/search sheet text;
- set sheet scale;
- polygon/area measurement;
- line measurement;
- surface measurement;
- counts;
- repeated-symbol sweep;
- schedule-row sweep;
- derived base quantities;
- transitions;
- rule application;
- sheet graph / tag / schedule resolution;
- edit/audit measurements;
- annotations and verdicts;
- RFIs;
- takeoff summary;
- takeoff/report export;
- marked PDF export;
- DXF export;
- takeoff import.

OpenTakeoff feature availability can change. Inspect the pinned upstream version before relying on a tool count or a gated automatic room-detection feature.

### Integration pattern

Preferred product UX:

```text
3D Model | 2D Drawings / Takeoff | BOQ | Review / Revision
```

Each measurement/BOQ item should be traceable to as much of the following as possible:

- project;
- building;
- storey;
- room/zone;
- trade/work category;
- unit;
- IFC GUID/semantic object ID where applicable;
- drawing/sheet ID;
- 2D measurement geometry;
- measurement method;
- author/agent;
- review status;
- revision;
- assumptions/issues.

### Human review

AI-proposed takeoff should remain distinguishable from human-approved takeoff.

Prefer an explicit review lifecycle such as:

```text
PROPOSED -> REVIEWED -> APPROVED
                   \-> REJECTED / NEEDS_RFI