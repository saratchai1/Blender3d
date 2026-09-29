# Blender Architecture Teaching Template

Template สำหรับสอน workflow **GitHub → Blender → GLB/Web 3D → Animation → IFC4 → BOQ** โดยไม่ต้อง commit โปรแกรม Blender เข้า repository

> GitHub repository เก็บ source code และ workflow เท่านั้น เมื่อ Actions ทำงาน ระบบจะสร้าง Ubuntu runner ชั่วคราว ดาวน์โหลด Blender 4.5 LTS ทำงาน แล้วอัปโหลดผลลัพธ์เป็น artifact

## สิ่งที่ผู้เรียนจะได้

- JSON building specification เป็น source of truth
- Blender/Python procedural modeling
- editable `.blend`
- web-ready `.glb`
- interactive Three.js viewer
- real 3D camera animation → MP4
- conceptual IFC4 hierarchy
- transparent concept BOQ CSV
- GitHub Actions automation
- GitHub Pages deployment

## Quick start บนเครื่อง

ต้องมี Git, Blender 4.5 LTS, Python 3.12 และ FFmpeg

```bash
git clone <YOUR-REPO-URL>
cd blender-architecture-template
python -m unittest tests/test_spec.py
BLENDER_BIN=blender ./scripts/build-local.sh
```

Windows PowerShell:

```powershell
$env:BLENDER_BIN = "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe"
.\\scripts\\build-local.ps1
```

IFC:

```bash
pip install -r requirements.txt
python bim/export_ifc.py --spec spec/building.json --output dist/building.ifc
```

Animation:

```bash
blender --background dist/building.blend --python blender/render_animation.py -- --output-dir dist/render --engine EEVEE --seconds 8 --fps 24
ffmpeg -framerate 24 -i dist/render/frames/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart dist/animation.mp4
```

## GitHub Actions

| Workflow | Trigger | ผลลัพธ์ |
|---|---|---|
| CI | push / PR | ตรวจ spec + Python syntax |
| Build 3D Model | main / manual | `.blend`, `.glb`, `boq.csv` |
| Export IFC4 | main / manual | `building.ifc` |
| Render Animation | manual | real 3D `animation.mp4` + animated `.blend` |
| Deploy Interactive 3D | main / manual | GitHub Pages |

Animation เป็น manual เพราะการ render ใช้ compute มาก โดยเฉพาะ Cycles

## Repository structure

```text
.
├── spec/building.json
├── blender/build_model.py
├── blender/render_animation.py
├── bim/export_ifc.py
├── boq/export_boq.py
├── web/
├── tests/
├── scripts/
└── .github/workflows/
```

## GitHub ลงอะไรให้ชั่วคราว

- Blender 4.5 LTS — modeling / materials / cameras / Eevee / Cycles
- Python 3.12 — tests / IFC tooling
- IfcOpenShell — IFC4 export workflow
- FFmpeg — MP4 encoding workflow
- GitHub Pages Actions — interactive 3D deployment

Cycles และ Eevee มากับ Blender ไม่ต้องลงแยก

Template นี้ไม่ต้องใช้ 3ds Max, Twinmotion, V-Ray, Corona, Lumion หรือ Unreal Engine

## Scope

โมเดล, IFC และ BOQ ใน template เป็น **concept / educational output** เท่านั้น ไม่ใช่แบบก่อสร้าง, statutory GFA, tender quantity, structural design หรือ energy certification.

ดูแผนการสอนได้ที่ `TEACHING_GUIDE.md`
