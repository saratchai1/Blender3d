$ErrorActionPreference = "Stop"
$Blender = if ($env:BLENDER_BIN) { $env:BLENDER_BIN } else { "blender" }
& $Blender --background --python blender/build_model.py -- --spec spec/building.json --output-dir dist
python boq/export_boq.py --spec spec/building.json --output dist/boq.csv
try {
  python -c "import ifcopenshell"
  python bim/export_ifc.py --spec spec/building.json --output dist/building.ifc
} catch {
  Write-Host "IfcOpenShell not installed; skipping IFC. Run: pip install -r requirements.txt"
}
