# Pascal integration staging

This directory records the Pascal components we may use later with the Blender3d control stack.

The repository intentionally does **not** vendor the full Pascal source tree. Instead, `pascal-lock.json` pins exact upstream commits and `scripts/fetch-pascal.ps1` can reproduce those snapshots under a local ignored directory when development starts.

## Why keep Pascal here

Potential roles in this project:

- semantic scene graph for tree inventory;
- Pascal JSON -> Blender editable object bridge;
- high-volume tree rendering patterns from `plugin-trees`;
- future web viewer for measured / alternative / not-measured trees;
- future MCP-facing semantic node layer;
- capture/point-cloud layer architecture reference.

## Pinned upstream components

See `pascal-lock.json` for exact commits.

| Component | Intended use |
| --- | --- |
| `pascalorg/editor` | semantic nodes, plugin API, viewer, MCP and capture architecture |
| `pascalorg/pascal-blender` | import Pascal scene JSON into Blender while preserving metadata |
| `pascalorg/plugin-trees` | instanced tree rendering and selection/proxy patterns |

All three upstream repositories were MIT licensed when this snapshot was recorded. Re-check licensing before redistributing copied upstream source or shipping a derived product.

## Fetch the pinned snapshots

From the repository root on Windows:

```powershell
.\scripts\fetch-pascal.ps1
```

The script clones each component and checks out the exact commit recorded in `pascal-lock.json` under:

```text
.external/pascal/
```

That directory is intentionally git-ignored. The canonical reproducibility record is the lock file, not a copied vendor tree.

To refresh from newer upstream commits later, review the changes first, then update `pascal-lock.json` deliberately.

## Planned Mangrove semantic model

A future Pascal plugin should use stable tree IDs shared with the DBH pipeline and Blender objects. A minimal node contract could look like:

```json
{
  "id": "TREE_0066",
  "type": "mangrove:tree",
  "position": [0.0, 0.0, 0.0],
  "properties": {
    "dbhCm": 12.6,
    "measurementMethod": "alternative",
    "confidence": 0.91,
    "species": "Rhizophora",
    "measurementStatus": "measured"
  }
}
```

Likely custom node kinds:

- `mangrove:tree`
- `mangrove:plot`
- `mangrove:dbh-measurement`
- `mangrove:point-cloud`
- `mangrove:survey-marker`

The intended rule is one stable tree ID across web/Pascal/MCP/Blender/export rather than separate object identities in each system.

## Current status

This is a **parked integration**, not a production dependency. The existing Blender MCP + KIRI 3DGS stack remains independent of Pascal.

When Pascal work resumes, start with `pascal-blender` and a small `mangrove:tree` plugin proof of concept before attempting to move large LAS/LAZ datasets into the Pascal viewer.
