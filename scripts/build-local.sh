#!/usr/bin/env bash
set -euo pipefail
BLENDER_BIN="${BLENDER_BIN:-blender}"
"$BLENDER_BIN" --background --python blender/build_model.py -- --spec spec/building.json --output-dir dist
python3 boq/export_boq.py --spec spec/building.json --output dist/boq.csv
if python3 -c 'import ifcopenshell' >/dev/null 2>&1; then
  python3 bim/export_ifc.py --spec spec/building.json --output dist/building.ifc
else
  echo 'IfcOpenShell not installed; skipping IFC. Run: pip install -r requirements.txt'
fi
