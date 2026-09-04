# Blender3d — MCP + 3D Gaussian Splat Control

This repository is the control layer for running Blender through MCP and working with 3D Gaussian Splatting (3DGS).

It intentionally **does not vendor Blender or copy the whole upstream MCP project**. Instead, it pins the upstream [`sandraschi/blender-mcp`](https://github.com/sandraschi/blender-mcp) package to a known commit and provides reproducible setup, launch, MCP-client configuration, and 3DGS diagnostics.

## Pinned upstream

- Repository: `sandraschi/blender-mcp`
- Commit: `6b51a6b302a149354d5c7820d077827f1129bb5c`
- Upstream date: 2026-09-02
- Python: 3.12+
- Blender: 3.0+

The pinned upstream exposes Blender MCP tools including `blender_addons`, `blender_splatting`, mesh/material/scene tools, rendering, export, and an optional live Blender bridge.

## What this repo gives you

- Reproducible `uv` environment pinned to a specific Blender MCP commit.
- Windows setup and launcher scripts.
- macOS/Linux-compatible Python project layout.
- Generated local MCP configuration without overwriting your global client settings.
- Blender executable auto-detection on Windows.
- 3DGS add-on diagnostics.
- Documented Gaussian Splat import/cleanup/collision workflow.
- A clean base for adding tree/point-cloud/DBH measurement tools later.

## Windows quick start

Clone this repository, then open PowerShell in the repo:

```powershell
git clone https://github.com/saratchai1/Blender3d.git
cd Blender3d

# Check prerequisites and create the local environment.
.\scripts\setup.ps1

# If Git/uv are missing, allow the script to install them with winget.
.\scripts\setup.ps1 -InstallPrereqs
```

If Blender is installed in a non-standard location:

```powershell
.\scripts\setup.ps1 -BlenderExecutable "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
```

The setup script runs `uv sync`, detects Blender, runs the upstream Blender health check, and generates `.mcp.generated.json` containing the absolute local repo path.

## Start MCP

For a stdio MCP client such as Claude Desktop, Cursor, VS Code/Codex-compatible MCP clients:

```powershell
.\scripts\start.ps1
```

For the upstream HTTP mode:

```powershell
.\scripts\start.ps1 -Http -Port 10849
```

HTTP mode is intended for **local development**. Do not expose port `10849` directly to the public internet without an authentication/reverse-proxy layer.

## MCP client configuration

After running setup, inspect:

```text
.mcp.generated.json
```

It will look like this, with the real absolute path filled in automatically:

```json
{
  "mcpServers": {
    "blender3d": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\path\\to\\Blender3d",
        "run",
        "blender-mcp",
        "--stdio"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "BLENDER_EXECUTABLE": "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe"
      }
    }
  }
}
```

Copy the `blender3d` server entry into your MCP client's config. The setup script deliberately does **not** edit a global Claude/Cursor/VS Code configuration automatically.

## Enable 3D Gaussian Splatting

Once the MCP server is connected, use the upstream add-on manager:

```text
blender_addons(
  operation="install_known",
  addon_name="gaussian_splat",
  enable_on_install=true
)
```

The upstream registry currently maps `gaussian_splat` to Stuffmatic FastGS. An alternative registry entry is `3dgs_blender`.

Then verify the installed add-ons:

```text
blender_addons(operation="list_installed")
```

For a normal Gaussian Splat file:

```text
blender_splatting(
  operation="import_gs",
  file_path="C:\\data\\scan.ply",
  setup_proxy=true
)
```

The upstream `worldlabs` operation can attempt the add-on setup automatically before importing:

```text
blender_splatting(
  operation="worldlabs",
  file_path="C:\\data\\scan.ply"
)
```

See [`docs/3DGS.md`](docs/3DGS.md) for the full flow.

## Diagnostics

Run:

```powershell
.\scripts\doctor.ps1
```

It checks:

1. `git`
2. `uv`
3. Blender executable discovery
4. `blender-mcp --check-blender`
5. Blender-side 3DGS-related add-ons/operators

A healthy MCP install and a healthy 3DGS add-on are separate checks; this makes failures easier to isolate.

## Tree / point-cloud / DBH direction

This repo is structured so the next layer can add project-specific Blender tools without modifying the upstream MCP package. Candidate modules include:

- import tree point clouds / splats;
- select or isolate an individual tree;
- define a measurement plane;
- slice trunk points around the measurement plane;
- robust circle/ellipse/cylinder fit;
- compute DBH or alternative-diameter measurements;
- attach tree ID, confidence, measurement method, and coordinates as Blender object properties;
- show measured / alternative / not-measured states in the viewport;
- export results to CSV/JSON/GeoJSON.

Those project-specific algorithms should live in this repository and call Blender through `bpy`/MCP, while upstream Blender MCP remains pinned as infrastructure.

## Updating upstream

Change the exact Git commit in `pyproject.toml`, then run:

```powershell
uv lock --upgrade-package blender-mcp
uv sync
.\scripts\doctor.ps1
```

Do not move the upstream pin blindly; review its changelog and run the diagnostics first.
