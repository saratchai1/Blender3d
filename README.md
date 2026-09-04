# Blender3d — MCP + 3D Gaussian Splat Control

Control Blender through MCP with a modern 3D Gaussian Splat (3DGS) compatibility layer.

This repository does **not** vendor Blender or copy the whole upstream MCP project. It pins [`sandraschi/blender-mcp`](https://github.com/sandraschi/blender-mcp) and launches it through `blender3d-control`, which patches current Blender/KIRI 3DGS behavior at runtime.

## Pinned components

### Blender MCP

- Repository: `sandraschi/blender-mcp`
- Commit: `6b51a6b302a149354d5c7820d077827f1129bb5c`
- Upstream commit date: 2026-09-02
- Python: 3.12+

### 3DGS

- Add-on: KIRI `3DGS Render`
- Release: `5.1.0`
- Release date: 2026-08-26
- Required for this 3DGS path: Blender 5.1+
- Verified release SHA-256: `3965ef73904f15a56ea4cee65de64209faaacf7a018c1a70f7d6a4ed925f96ae`

KIRI's 5.1.0 release notes state that the package was clean-installed and tested on Windows with Blender 5.1.1 and Blender 5.2.0 LTS.

## Why this repo has a compatibility layer

The pinned Blender MCP already exposes `blender_addons`, `blender_splatting`, mesh/material/scene tools, rendering, export, and a live bridge. However, its bundled 3DGS registry currently points at legacy GitHub URLs that no longer resolve, and its splat importer targets older Blender operators.

Current KIRI uses:

```python
bpy.ops.sna.dgs_render_import_ply_e0a3a(...)
```

Modern Blender native PLY import uses:

```python
bpy.ops.wm.ply_import(...)
```

`src/blender3d_control/compat.py` bridges those into the existing upstream MCP calls, so clients can continue using `blender_splatting(...)` instead of needing a separate MCP server.

## Windows quick start

```powershell
git clone https://github.com/saratchai1/Blender3d.git
cd Blender3d

# If Git, uv and Blender are already installed:
.\scripts\setup.ps1

# Or allow setup to install missing prerequisites with winget:
.\scripts\setup.ps1 -InstallPrereqs
```

If Blender is outside the normal install path:

```powershell
.\scripts\setup.ps1 -BlenderExecutable "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

The setup script:

1. checks Git and `uv`;
2. finds Blender;
3. runs `uv sync` against the pinned MCP dependency;
4. creates local `.env` if needed;
5. generates `.mcp.generated.json` with absolute executable/repo paths;
6. runs a Blender MCP health check.

## Install 3DGS

```powershell
.\scripts\install-3dgs.ps1
```

This downloads the pinned KIRI release (~771 MB), verifies its SHA-256, caches it locally, and installs/enables it with Blender's extension command-line interface.

Then verify everything:

```powershell
.\scripts\doctor.ps1
```

Expected summary:

```text
Core MCP: READY
KIRI 3DGS: READY
```

## Start MCP

### stdio

Use this for local MCP clients:

```powershell
.\scripts\start.ps1
```

### HTTP

```powershell
.\scripts\start.ps1 -Http -Port 10849
```

HTTP defaults to `127.0.0.1`. Keep it local unless you deliberately add authentication/TLS through a proper gateway. Do not expose the raw MCP port directly to the internet.

## MCP client config

`setup.ps1` writes `.mcp.generated.json`. It uses this launcher:

```json
{
  "mcpServers": {
    "blender3d": {
      "command": "C:\\path\\to\\uv.exe",
      "args": [
        "--directory",
        "C:\\path\\to\\Blender3d",
        "run",
        "blender3d-control",
        "--stdio"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "BLENDER_EXECUTABLE": "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe"
      }
    }
  }
}
```

The repository deliberately does not overwrite your global Claude/Cursor/VS Code configuration. Copy the generated `blender3d` server entry into the MCP client you want to use.

## 3DGS MCP commands

### Install through MCP

The control launcher patches the legacy registry names to KIRI 5.1.0:

```text
blender_addons(
  operation="install_known",
  addon_name="gaussian_splat",
  enable_on_install=true
)
```

The aliases `gaussian_splat`, `3dgs_blender`, and `kiri_3dgs` all resolve to the pinned KIRI package inside this control process.

### Import Gaussian Splat PLY

```text
blender_splatting(
  operation="import_gs",
  file_path="C:\\data\\tree_scan.ply",
  setup_proxy=true
)
```

The patched importer tries KIRI first, then legacy importers, then modern Blender PLY as a geometry-only fallback. The result tells you which engine actually succeeded.

### Other existing upstream operations

```text
blender_splatting(operation="crop_and_clean", crop_type="sphere", radius=10.0)
blender_splatting(operation="generate_collision_mesh", decimation_ratio=0.1)
```

See [`docs/3DGS.md`](docs/3DGS.md) for limitations. In particular, the pinned upstream `crop_and_clean` implementation is not yet a rigorous scientific 3DGS cleaning algorithm.

## Diagnostics

```powershell
.\scripts\doctor.ps1
```

It checks:

1. Git
2. `uv`
3. Blender executable/version
4. Python package import
5. Blender MCP discovery
6. KIRI operator `sna.dgs_render_import_ply_e0a3a`
7. modern native PLY fallback `wm.ply_import`

Exit codes:

- `0`: core + KIRI 3DGS ready
- `1`: core setup problem
- `2`: core ready, KIRI 3DGS not ready

## Tree / point-cloud / DBH direction

The next project-specific layer should live in this repository, not in the pinned upstream package. The intended architecture is:

```text
MCP client
   |
blender3d-control
   |-- upstream Blender MCP tools
   |-- modern 3DGS compatibility
   `-- project-specific tree/DBH tools (next)
            |
          Blender
            |
    LAS / LAZ / PLY / 3DGS
```

For DBH, use the underlying metric point geometry as the source of truth. 3DGS is primarily the visual/context representation; Gaussian ellipse size should not be interpreted directly as trunk diameter.

Candidate next tools:

- import LAS/LAZ/PLY tree point clouds;
- isolate tree by ID/ROI;
- define standard or alternative measurement plane;
- slice trunk points;
- robust circle/ellipse/cylinder fitting;
- compute diameter + residual/confidence;
- store tree ID, method, measurement plane, coordinates and status as Blender properties;
- show `standard`, `alternative`, and `not measured` states in the viewport;
- export CSV/JSON/GeoJSON.

## Pascal integration (parked for later)

Pascal is recorded as an optional future integration, not a runtime dependency of the current Blender/3DGS stack.

Pinned Pascal components and intended roles are documented in [`integrations/pascal/`](integrations/pascal/):

- `pascalorg/editor` — semantic scene graph, plugin API, viewer, MCP and capture architecture;
- `pascalorg/pascal-blender` — Pascal scene JSON -> editable Blender objects while retaining semantic metadata;
- `pascalorg/plugin-trees` — reference for large tree sets, instancing and selection proxies.

Exact upstream commits are stored in `integrations/pascal/pascal-lock.json`. To materialize those snapshots locally later:

```powershell
.\scripts\fetch-pascal.ps1
```

They are checked out under `.external/pascal/`, which is ignored by Git. This keeps this repository small while preserving a reproducible point-in-time Pascal integration baseline.

The intended future semantic model uses a stable tree ID such as `TREE_0066` across Pascal, Blender, MCP, DBH results and exports.

## Updating upstream

Change the exact commit in `pyproject.toml`, then:

```powershell
uv lock --upgrade-package blender-mcp
uv sync
.\scripts\doctor.ps1
```

Review upstream changes before moving the pin because this repo intentionally patches specific compatibility gaps in the pinned implementation.
