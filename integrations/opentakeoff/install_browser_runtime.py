#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PDFJS_MAJOR_MINOR = "4.10."
RUNTIME_MODULES = (
    "browser-auto-boq.mjs",
    "browser-auto-boq-hybrid.mjs",
    "browser-backend-runtime.mjs",
)


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
    output.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_MODULES:
        runtime = src / name
        if not runtime.is_file():
            raise SystemExit(f"{name} is missing")
        shutil.copy2(runtime, output / name)

    poc = output / "poc.js"
    if not poc.is_file():
        raise SystemExit("generated poc.js is missing; build the POC first")
    text = poc.read_text(encoding="utf-8")
    old = "import('./browser-auto-boq.mjs')"
    new = "import('./browser-auto-boq-hybrid.mjs')"
    if text.count(old) != 1:
        raise SystemExit(f"expected one browser runtime import, found {text.count(old)}")
    poc.write_text(text.replace(old, new), encoding="utf-8")

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
        "runtime": "browser-auto-boq-hybrid.mjs",
        "runtime_modules": list(RUNTIME_MODULES),
        "worker": "vendor/pdf.worker.mjs",
        "backend_policy": "PYTHON_VALIDATED_PROFILE_FIRST_BROWSER_FAIL_CLOSED_FALLBACK",
        "backend_configuration": "?boq_backend=https://.../api/auto-boq or localStorage/global runtime value",
        "reference_data_dependency": False,
    }
    (output / "browser-runtime-info.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("BROWSER_AUTO_BOQ_RUNTIME_INSTALLED", json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
