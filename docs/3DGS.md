# 3D Gaussian Splat workflow

## Supported path in this repository

This control repo uses:

- Blender `5.1+` for the KIRI extension path.
- KIRI **3DGS Render 5.1.0** release package.
- `sandraschi/blender-mcp` pinned to commit `6b51a6b302a149354d5c7820d077827f1129bb5c`.
- `blender3d_control.compat` to bridge modern Blender/KIRI operators into the upstream MCP tools.

KIRI 3DGS Render 5.1.0 was published on 2026-08-26 and its release notes state that it was clean-installed and tested on Windows with Blender 5.1.1 and Blender 5.2.0 LTS.

## Why the compatibility layer exists

The pinned upstream Blender MCP has useful Gaussian Splat MCP tools, but its bundled 3DGS registry currently points to repositories that are no longer available at those URLs. Its import handler also tries older operators such as:

- `bpy.ops.import_scene.gaussian_splat`
- `bpy.ops.import_mesh.fastgs`
- `bpy.ops.import_mesh.ply`

Modern Blender uses `bpy.ops.wm.ply_import` for native PLY import, while current KIRI 3DGS Render exposes:

```python
bpy.ops.sna.dgs_render_import_ply_e0a3a(filepath="...")
```

`blender3d_control.compat` patches the upstream process at runtime so existing MCP calls can use the current KIRI operator without vendoring or editing the upstream source tree.

## Install

Run the base setup first:

```powershell
.\scripts\setup.ps1
```

Then install KIRI 3DGS:

```powershell
.\scripts\install-3dgs.ps1
```

The installer:

1. detects Blender;
2. requires Blender 5.1+;
3. downloads the pinned KIRI 3DGS Render 5.1.0 release ZIP;
4. verifies SHA-256 `3965ef73904f15a56ea4cee65de64209faaacf7a018c1a70f7d6a4ed925f96ae`;
5. installs it with Blender's `extension install-file` command into `user_default`;
6. requests enable-on-install;
7. caches the verified package locally so it is not downloaded again unnecessarily.

The release ZIP is large (about 771 MB) because it includes platform/runtime wheels required by the Blender extension.

## Verify

```powershell
.\scripts\doctor.ps1
```

The Blender-side check looks for:

```text
sna.dgs_render_import_ply_e0a3a
```

and also records whether the modern native fallback is available:

```text
wm.ply_import
```

`doctor.ps1` exits:

- `0` — core MCP and KIRI 3DGS are ready;
- `1` — core setup is broken/missing;
- `2` — core MCP is ready but KIRI 3DGS is not ready.

## MCP calls

### Install from MCP

With the `blender3d-control` launcher, the upstream registry name is patched so this existing MCP call installs KIRI instead of the dead legacy target:

```text
blender_addons(
  operation="install_known",
  addon_name="gaussian_splat",
  enable_on_install=true
)
```

Aliases patched to the same KIRI release:

- `gaussian_splat`
- `3dgs_blender`
- `kiri_3dgs`

### Import PLY

```text
blender_splatting(
  operation="import_gs",
  file_path="C:\\data\\tree_scan.ply",
  setup_proxy=true
)
```

The patched importer tries, in order:

1. KIRI 3DGS Render operator;
2. legacy `import_scene.gaussian_splat`;
3. legacy FastGS operator;
4. Blender 5.x `wm.ply_import` as a geometry-only fallback;
5. legacy Blender PLY fallback.

The result reports which engine/operator actually succeeded. Do not treat a native PLY fallback as proof that Gaussian rendering is active.

### WorldLabs-style one-call flow

```text
blender_splatting(
  operation="worldlabs",
  file_path="C:\\data\\scan.ply"
)
```

The pinned upstream `worldlabs` probe does not know the KIRI `sna.*` namespace. The compatibility layer therefore makes its legacy auto-install step idempotent: if KIRI is already installed, it returns success quickly and then the patched importer uses KIRI.

### Crop / clean

```text
blender_splatting(
  operation="crop_and_clean",
  crop_type="sphere",
  radius=10.0
)
```

Important: in the pinned upstream version this operation mainly creates a Blender modifier scaffold; it is not yet a rigorous 3DGS point-deletion implementation. Do not use it as an irreversible scientific cleaning step without validating the output.

### Collision mesh

```text
blender_splatting(
  operation="generate_collision_mesh",
  decimation_ratio=0.1,
  smoothing_iterations=2
)
```

This is useful for interaction/visualization but is **not** a DBH measurement algorithm.

## Compatible PLY expectations

KIRI's current importer validates the Gaussian fields needed for a 3DGS scan. Core fields include:

```text
f_dc_0
f_dc_1
f_dc_2
opacity
scale_0
scale_1
scale_2
rot_0
rot_1
rot_2
rot_3
```

Higher-order spherical-harmonic `f_rest_*` attributes are optional for degree-0 splats.

A normal point-cloud PLY without these Gaussian attributes can still be imported by Blender's native PLY importer, but it is not automatically a valid 3DGS scene.

## DBH / tree-analysis rule

For tree measurement, keep the analysis representation separate from the visual 3DGS representation:

- 3DGS: best for visual inspection and scene context;
- original LAS/LAZ/PLY points: preferred source for quantitative geometry;
- derived mesh: optional helper, not the source of truth for DBH;
- measurement result: store method, height/plane definition, fit residual, point count, confidence, tree ID, and world coordinates.

This avoids measuring the apparent size of Gaussian ellipses instead of the underlying trunk geometry.

## Security

The KIRI extension executes Python inside Blender and ships bundled Python wheels. Treat add-ons and scene/input files as executable-adjacent content: pin releases, verify hashes, and avoid importing untrusted files on a machine containing sensitive data.
