from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from .compat import apply_compatibility_patches, find_blender_executable, install_kiri_3dgs


def _prepare_blender_environment() -> None:
    blender = find_blender_executable()
    if not blender:
        return

    os.environ["BLENDER_EXECUTABLE"] = blender
    blender_dir = str(Path(blender).parent)
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if blender_dir not in path_parts:
        os.environ["PATH"] = blender_dir + os.pathsep + os.environ.get("PATH", "")


def main() -> None:
    _prepare_blender_environment()
    apply_compatibility_patches()

    if "--install-3dgs" in sys.argv[1:]:
        result = asyncio.run(install_kiri_3dgs(enable_after=True))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(0 if result.get("status") == "SUCCESS" else 1)

    # Import only after the compatibility patches are installed. The upstream CLI
    # imports its server at module import time, which registers the MCP tools.
    from blender_mcp.cli import main as upstream_main

    upstream_main()


if __name__ == "__main__":
    main()
