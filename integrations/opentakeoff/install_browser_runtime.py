#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PDFJS_MAJOR_MINOR = "4.10."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    upstream = args.upstream.resolve()
    output = args.output.resolve()
    web = upstream / "web"
    pdfjs = web / "node_modules" / "pdfjs-dist"
    package = pdfjs / "package.json"
    if not package.is_file():
        raise SystemExit("pdfjs-dist is not installed; run the pinned OpenTakeoff npm ci/build first")
    version = str(json.loads(package.read_text(encoding="utf-8")).get("version") or "")
    if not version.startswith(EXPECTED_PDFJS_MAJOR_MINOR):
        raise SystemExit(f"unexpected pdfjs-dist version {version!r}; expected pinned 4.10.x runtime")

    src = ROOT / "web" / "opentakeoff-poc"
    runtime = src / "browser-auto-boq.mjs"
    if not runtime.is_file():
        raise SystemExit("browser-auto-boq.mjs is missing")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime, output / runtime.name)

    vendor = output / "vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    for name in ("pdf.mjs", "pdf.worker.mjs"):
        source = pdfjs / "build" / name
        if not source.is_file():
            raise SystemExit(f"missing pinned PDF.js asset: {source}")
        shutil.copy2(source, vendor / name)

    manifest = {
        "schema": "blender3d.browser_auto_boq_runtime.v1",
        "pdfjs_version": version,
        "source": "pinned Kentucky-ai/opentakeoff web dependency",
        "runtime": "browser-auto-boq.mjs",
        "worker": "vendor/pdf.worker.mjs",
        "network_dependency": False,
        "reference_data_dependency": False,
    }
    (output / "browser-runtime-info.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("BROWSER_AUTO_BOQ_RUNTIME_INSTALLED", json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
