# Teaching Guide

## Learning path

### Lesson 1 — One source of truth
ให้นักเรียนแก้ `spec/building.json` ก่อน อธิบาย dimension, storeys, facade spacing และ PV assumptions

### Lesson 2 — Blender automation
รัน `blender/build_model.py` แบบ headless อธิบายว่า GitHub ไม่ได้เก็บ Blender ติดตั้งค้างไว้ แต่ดาวน์โหลดลง runner ชั่วคราว

### Lesson 3 — GLB and web 3D
Deploy `web/` ไป GitHub Pages แล้วหมุนโมเดลเดียวกันใน browser โดยเครื่องผู้ชมไม่ต้องลง Blender

### Lesson 4 — Real animation
รัน workflow `Render Animation` เปรียบเทียบ Eevee กับ Cycles วิดีโอเกิดจาก 3D frames จริง ไม่ใช่ pan/zoom ภาพนิ่ง

### Lesson 5 — IFC and BOQ
รัน `Export IFC4` ตรวจ hierarchy ของ 6 storeys แล้วเทียบกับ `boq.csv` พร้อมอภิปราย concept quantity vs tender quantity

## Suggested assignment

1. เปลี่ยนอาคารเป็น 8 ชั้น
2. ปรับ footprint ให้ concept area รวมอยู่ระหว่าง 3,000–3,500 m²
3. ออกแบบ fin spacing ใหม่
4. Render animation 8 วินาที
5. Export IFC และ BOQ
6. ระบุว่าเลขไหน measured, derived หรือ assumption

## Assessment rubric

- Reproducible model build: 25%
- Architectural intent / facade design: 20%
- Camera and presentation: 20%
- IFC / quantity traceability: 20%
- Documentation and limitations: 15%
