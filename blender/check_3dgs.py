import json

import bpy


def operator_exists(path: str) -> bool:
    target = bpy.ops
    try:
        for part in path.split("."):
            target = getattr(target, part)
        target.get_rna_type()
        return True
    except Exception:
        return False


enabled_modules = sorted(addon.module for addon in bpy.context.preferences.addons)
interesting_modules = [
    module
    for module in enabled_modules
    if any(token in module.lower() for token in ("dgs", "3dgs", "gaussian", "splat", "kiri"))
]

operators = {
    "kiri_import": operator_exists("sna.dgs_render_import_ply_e0a3a"),
    "gaussian_splat_import": operator_exists("import_scene.gaussian_splat"),
    "fastgs_import": operator_exists("import_mesh.fastgs"),
    "modern_ply_import": operator_exists("wm.ply_import"),
    "legacy_ply_import": operator_exists("import_mesh.ply"),
}

result = {
    "blender_version": ".".join(str(part) for part in bpy.app.version),
    "enabled_3dgs_modules": interesting_modules,
    "operators": operators,
    "kiri_ready": operators["kiri_import"],
    "native_ply_fallback_ready": operators["modern_ply_import"] or operators["legacy_ply_import"],
}

print("BLENDER3D_3DGS_DIAGNOSTIC=" + json.dumps(result, sort_keys=True))
raise SystemExit(0 if result["kiri_ready"] else 2)
