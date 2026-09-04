from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx

KIRI_VERSION = "5.1.0"
KIRI_EXTENSION_ID = "dgs_render_by_kiri_engine"
KIRI_MODULE = "bl_ext.user_default.dgs_render_by_kiri_engine"
KIRI_RELEASE_URL = (
    "https://github.com/Kiri-Innovation/3dgs-render-blender-addon/"
    "releases/download/v5.1.0/3dgs_render_by_kiri_engine_5.1.0.zip"
)
KIRI_SHA256 = "3965ef73904f15a56ea4cee65de64209faaacf7a018c1a70f7d6a4ed925f96ae"


def find_blender_executable() -> str | None:
    configured = os.environ.get("BLENDER_EXECUTABLE", "").strip().strip('"')
    if configured and Path(configured).is_file():
        return str(Path(configured).resolve())

    discovered = shutil.which("blender")
    if discovered:
        return discovered

    system = platform.system().lower()
    candidates: list[Path] = []
    if system == "windows":
        base = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Blender Foundation"
        if base.exists():
            candidates.extend(base.glob("Blender */blender.exe"))
            candidates.extend(base.glob("Blender*/blender.exe"))
    elif system == "darwin":
        candidates.append(Path("/Applications/Blender.app/Contents/MacOS/Blender"))
    else:
        candidates.extend([Path("/usr/bin/blender"), Path("/usr/local/bin/blender")])

    existing = sorted((p for p in candidates if p.is_file()), reverse=True)
    return str(existing[0]) if existing else None


def _blender_version(blender: str) -> tuple[int, int, int] | None:
    try:
        result = subprocess.run(
            [blender, "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except OSError:
        return None

    first_line = (result.stdout or result.stderr).splitlines()[0] if (result.stdout or result.stderr) else ""
    match = re.search(r"Blender\s+(\d+)\.(\d+)(?:\.(\d+))?", first_line)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_dir() -> Path:
    if platform.system().lower() == "windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = base / "Blender3dControl" / "cache"
    else:
        path = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "blender3d-control"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _download_kiri_release() -> Path:
    target = _cache_dir() / f"3dgs_render_by_kiri_engine_{KIRI_VERSION}.zip"
    if target.exists() and _sha256(target) == KIRI_SHA256:
        return target

    partial = target.with_suffix(".zip.part")
    if partial.exists():
        partial.unlink()

    with httpx.Client(follow_redirects=True, timeout=None) as client:
        with client.stream("GET", KIRI_RELEASE_URL) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    handle.write(chunk)

    actual = _sha256(partial)
    if actual != KIRI_SHA256:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"KIRI 3DGS checksum mismatch: expected {KIRI_SHA256}, got {actual}")

    partial.replace(target)
    return target


def _extension_is_installed(blender: str) -> bool:
    result = subprocess.run(
        [blender, "--command", "extension", "list"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}".lower()
    return KIRI_EXTENSION_ID.lower() in output


def _install_kiri_sync(enable_after: bool = True) -> dict[str, Any]:
    blender = find_blender_executable()
    if not blender:
        return {
            "status": "ERROR",
            "error": "Blender executable not found. Set BLENDER_EXECUTABLE first.",
        }

    version = _blender_version(blender)
    if version is None:
        return {"status": "ERROR", "error": f"Could not determine Blender version from {blender}"}
    if version < (5, 1, 0):
        return {
            "status": "ERROR",
            "error": (
                f"KIRI 3DGS Render {KIRI_VERSION} requires Blender 5.1+. "
                f"Detected Blender {version[0]}.{version[1]}.{version[2]}."
            ),
        }

    if _extension_is_installed(blender):
        return {
            "status": "SUCCESS",
            "message": f"KIRI 3DGS Render {KIRI_VERSION} is already installed.",
            "addon_name": "gaussian_splat",
            "extension_id": KIRI_EXTENSION_ID,
            "blender": blender,
        }

    try:
        package = _download_kiri_release()
    except Exception as exc:
        return {"status": "ERROR", "error": f"Failed to download KIRI 3DGS release: {exc}"}

    command = [
        blender,
        "--command",
        "extension",
        "install-file",
        "-r",
        "user_default",
    ]
    if enable_after:
        command.append("-e")
    command.append(str(package))

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    if result.returncode != 0:
        return {
            "status": "ERROR",
            "error": output[-2000:] or f"Blender extension installer exited {result.returncode}",
            "command": command,
        }

    return {
        "status": "SUCCESS",
        "message": f"Installed KIRI 3DGS Render {KIRI_VERSION}.",
        "extension_id": KIRI_EXTENSION_ID,
        "package": str(package),
        "blender": blender,
        "installer_output": output[-2000:],
    }


async def install_kiri_3dgs(enable_after: bool = True) -> dict[str, Any]:
    return await asyncio.to_thread(_install_kiri_sync, enable_after)


async def import_gaussian_splat_compat(
    file_path: str,
    sh_degree: int = 3,
    setup_proxy: bool = True,
) -> dict[str, Any]:
    del sh_degree

    source = Path(file_path)
    if not file_path:
        return {"status": "error", "message": "file_path is required"}
    if not source.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}
    if source.suffix.lower() not in {".ply", ".spz"}:
        return {"status": "error", "message": "Unsupported format. Expected .ply or .spz"}

    from blender_mcp.utils.blender_executor import get_blender_executor

    script = f'''
import bpy, json, os

file_path = {json.dumps(str(source.resolve()))}
setup_proxy = {str(bool(setup_proxy))}
before = set(obj.name for obj in bpy.data.objects)
imported = False
engine = None
attempts = []

# Modern KIRI 3DGS Render extension (Blender 5.1+).
if file_path.lower().endswith(".ply"):
    try:
        bpy.ops.sna.dgs_render_import_ply_e0a3a(filepath=file_path)
        imported = True
        engine = "kiri_3dgs_render"
    except Exception as exc:
        attempts.append("KIRI operator: " + str(exc))

# Legacy/community Gaussian Splat importers supported by upstream blender-mcp.
if not imported:
    try:
        bpy.ops.import_scene.gaussian_splat(filepath=file_path)
        imported = True
        engine = "import_scene.gaussian_splat"
    except Exception as exc:
        attempts.append("import_scene.gaussian_splat: " + str(exc))

if not imported:
    try:
        bpy.ops.import_mesh.fastgs(filepath=file_path)
        imported = True
        engine = "import_mesh.fastgs"
    except Exception as exc:
        attempts.append("import_mesh.fastgs: " + str(exc))

# Modern Blender native PLY fallback. This preserves point attributes but is not a
# full Gaussian renderer unless KIRI (or another 3DGS extension) is active.
if not imported and file_path.lower().endswith(".ply"):
    try:
        bpy.ops.wm.ply_import(filepath=file_path)
        imported = True
        engine = "wm.ply_import_fallback"
        attempts.append("WARNING: imported with Blender native PLY operator; Gaussian rendering was not initialized.")
    except Exception as exc:
        attempts.append("wm.ply_import: " + str(exc))

if not imported:
    try:
        bpy.ops.import_mesh.ply(filepath=file_path)
        imported = True
        engine = "import_mesh.ply_fallback"
        attempts.append("WARNING: imported with legacy native PLY operator; Gaussian rendering was not initialized.")
    except Exception as exc:
        attempts.append("import_mesh.ply: " + str(exc))

if not imported:
    print("GS_RESULT:" + json.dumps({{
        "status": "error",
        "message": "No compatible Gaussian Splat importer succeeded.",
        "attempts": attempts,
        "fix": "Install KIRI 3DGS Render using blender_addons(operation='install_known', addon_name='gaussian_splat')."
    }}))
else:
    new_objects = [obj for obj in bpy.data.objects if obj.name not in before]
    obj = bpy.context.active_object
    if obj is None or (obj.name in before and new_objects):
        obj = new_objects[-1] if new_objects else obj

    point_count = 0
    if obj is not None and obj.data is not None:
        if obj.type == "POINTCLOUD" and hasattr(obj.data, "points"):
            point_count = len(obj.data.points)
        elif obj.type == "MESH" and hasattr(obj.data, "vertices"):
            point_count = len(obj.data.vertices)

    proxy_name = None
    if setup_proxy and obj is not None:
        dims = tuple(max(float(v), 0.01) for v in obj.dimensions)
        bpy.ops.mesh.primitive_cube_add(size=1, location=obj.location)
        proxy = bpy.context.active_object
        proxy.name = obj.name + "_MCP_PROXY"
        proxy.display_type = "WIRE"
        proxy.hide_render = True
        proxy.dimensions = dims
        proxy["blender3d_control_proxy_for"] = obj.name
        proxy_name = proxy.name
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

    print("GS_RESULT:" + json.dumps({{
        "status": "success",
        "engine": engine,
        "object_name": obj.name if obj else None,
        "point_count": point_count,
        "file_path": file_path,
        "proxy_name": proxy_name,
        "attempts": attempts,
    }}))
'''

    try:
        output = await get_blender_executor().execute_script(script, script_name="import_gs_blender3d_compat")
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    for line in output.splitlines():
        if line.startswith("GS_RESULT:"):
            return json.loads(line[len("GS_RESULT:") :])
    return {"status": "error", "message": f"Blender produced no GS result. Output: {output[-1200:]}"}


def apply_compatibility_patches() -> None:
    """Patch the pinned upstream at runtime without vendoring its source tree."""
    from blender_mcp.handlers import addon_handler, splatting_handler

    if getattr(addon_handler, "_blender3d_control_patched", False):
        return

    original_installer = addon_handler.install_addon_from_url

    async def install_addon_from_url_compat(addon_url: str, enable_after: bool = True) -> dict[str, Any]:
        if (
            addon_url == KIRI_RELEASE_URL
            or "Kiri-Innovation/3dgs-render-blender-addon" in addon_url
            or "3dgs_render_by_kiri_engine" in addon_url
        ):
            return await install_kiri_3dgs(enable_after=enable_after)
        return await original_installer(addon_url, enable_after=enable_after)

    addon_handler.install_addon_from_url = install_addon_from_url_compat
    addon_handler.KNOWN_ADDONS["gaussian_splat"] = (
        KIRI_RELEASE_URL,
        f"KIRI 3DGS Render {KIRI_VERSION} - modern Blender 5.1+ Gaussian Splat renderer/editor",
    )
    addon_handler.KNOWN_ADDONS["3dgs_blender"] = addon_handler.KNOWN_ADDONS["gaussian_splat"]
    addon_handler.KNOWN_ADDONS["kiri_3dgs"] = addon_handler.KNOWN_ADDONS["gaussian_splat"]

    splatting_handler.import_gaussian_splat = import_gaussian_splat_compat
    addon_handler._blender3d_control_patched = True
