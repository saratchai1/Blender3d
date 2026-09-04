# House 200 sqm — Blender + Pascal POC

This POC proves a shared semantic/geometry workflow:

```text
house_spec.json
      |
      v
Pascal scene generator
      |
      +--> native Pascal scene graph JSON
      |       level / wall / zone / slab / door / window / roof
      |
      v
Blender builder
      |
      +--> house_200sqm.blend
      +--> house_200sqm.glb
      `--> house_200sqm-preview.png
```

## Program

- Style: Modern Tropical
- Footprint: 10 x 10 m = 100 sqm
- Levels: 2
- Gross floor area: 200 sqm
- Floor-to-floor: 3.2 m
- Wall height: 3.0 m
- Wall thickness: 0.15 m
- Bedrooms: 4 including the ground-floor guest/office
- Service/bath areas: ground + upper
- Gable roof with 0.8 m overhang

### Ground floor — 100 sqm semantic zones

| Zone | Area |
|---|---:|
| Living Room | 27.6 sqm |
| Dining + Stair | 18.4 sqm |
| Kitchen | 21.6 sqm |
| Guest / Office | 16.2 sqm |
| Bath + Laundry | 16.2 sqm |
| **Total** | **100.0 sqm** |

### Upper floor — 100 sqm semantic zones

| Zone | Area |
|---|---:|
| Master Bedroom | 25.0 sqm |
| Bedroom 2 | 25.0 sqm |
| Bedroom 3 | 20.0 sqm |
| Family Hall | 15.0 sqm |
| Bath + Wardrobe | 15.0 sqm |
| **Total** | **100.0 sqm** |

The room area table is a gross programming partition. Wall thicknesses and the stair void mean net usable floor area is lower, which is expected.

## Why Pascal is in the middle

The Blender script deliberately does **not** read `house_spec.json` directly. The spec is first converted into native Pascal nodes and validated, then Blender consumes that generated Pascal graph. This forces both systems to share the same IDs and relationships.

Examples:

```text
Pascal node                 Blender semantic anchor
-------------------------------------------------------
wall_g_south                wall_g_south
window_g_south_living       window_g_south_living
door_g_main                 door_g_main
zone_u_master               zone_u_master
```

Generated Blender objects carry custom properties such as:

```text
pascal_id
pascal_type
pascal_name
pascal_metadata
```

Derived geometry pieces such as wall segments and window frame bars carry:

```text
derived_from_pascal_id
```

The full source Pascal graph is also embedded in the `.blend` Text datablock:

```text
PASCAL_SCENE_JSON
```

This gives us a stable path for future MCP commands such as "move the master-bedroom window 0.5 m" without asking the AI to infer which mesh is the window.

## Build on Windows

Prerequisites:

```powershell
.\scripts\setup.ps1 -InstallPrereqs
```

Then build the POC:

```powershell
.\scripts\build-house-200sqm.ps1
```

Optional:

```powershell
# Skip preview render for a faster build.
.\scripts\build-house-200sqm.ps1 -NoPreview

# Explicit Blender executable.
.\scripts\build-house-200sqm.ps1 `
  -BlenderExecutable "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

Outputs:

```text
.generated/house_200sqm/house_200sqm.pascal.json
models/house_200sqm/output/house_200sqm.blend
models/house_200sqm/output/house_200sqm.glb
models/house_200sqm/output/house_200sqm-preview.png
```

Generated outputs are local artifacts and are not intended to be committed.

## Pascal schema compatibility

The generator targets the node contract documented by the pinned Pascal integration:

```text
pascalorg/pascal-blender
feca6f28cec9378123240115d20c6cf3971588c9
```

It uses actual Pascal node types rather than a made-up house schema:

- `site`
- `building`
- `level`
- `slab`
- `ceiling`
- `wall`
- `zone`
- `door`
- `window`
- `roof`
- `roof-segment`

The Pascal integration itself remains parked/optional for the main Blender MCP stack. Fetch the pinned Pascal repositories later with:

```powershell
.\scripts\fetch-pascal.ps1
```

## Current modeling scope

Implemented in the Blender POC:

- semantic level and room hierarchy;
- slabs and ceilings;
- rectangular stair void;
- 16-step stair derived from the `Dining + Stair` zone;
- exterior and interior walls;
- openings physically cut by segmented wall generation;
- parametric door leaves/frames;
- parametric window frames, mullions and glass;
- gable roof;
- site plane;
- materials, camera and lighting;
- `.blend`, `.glb`, and preview export;
- Pascal IDs preserved in Blender custom properties.

Not yet intended as construction/BIM documentation:

- structural sizing;
- MEP;
- code compliance;
- detailed foundations;
- waterproofing/roof build-up;
- furniture/catalog assets;
- exact net-area certification.

The purpose of this model is to validate the **AI-native semantic house workflow**, not to replace architectural/structural design review.
