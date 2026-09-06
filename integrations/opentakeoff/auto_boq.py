#!/usr/bin/env python3
"""Automatic quantity extraction from vector construction PDFs.

The extractor deliberately has no access to benchmark BOQ/reference pages or
reference quantities. A profile may describe drawing-page roles, scales and
legend template regions because those are inputs visible on the drawing set.
All evidence emitted by this module must point at allowed drawing pages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import fitz
import numpy as np

SCHEMA = "blender3d.auto_boq.v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def m_per_point(scale_ratio: float) -> float:
    # 1 pt = 1/72 inch on paper. At 1:R, real metres = paper inches * 0.0254 * R.
    return 0.0254 * float(scale_ratio) / 72.0


@dataclass(frozen=True)
class GuardedPdf:
    doc: fitz.Document
    max_source_page: int

    def page(self, page_no: int) -> fitz.Page:
        if page_no < 1 or page_no > self.max_source_page:
            raise ValueError(
                f"source-page guard: page {page_no} is outside drawing pages 1..{self.max_source_page}"
            )
        return self.doc[page_no - 1]


def iter_line_segments(page: fitz.Page) -> Iterable[tuple[float, float, float, float, float]]:
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            op = item[0]
            if op == "l":
                p1, p2 = item[1], item[2]
                yield p1.x, p1.y, p2.x, p2.y, math.hypot(p2.x - p1.x, p2.y - p1.y)
            elif op == "re":
                r = item[1]
                for x1, y1, x2, y2 in (
                    (r.x0, r.y0, r.x1, r.y0),
                    (r.x1, r.y0, r.x1, r.y1),
                    (r.x1, r.y1, r.x0, r.y1),
                    (r.x0, r.y1, r.x0, r.y0),
                ):
                    yield x1, y1, x2, y2, math.hypot(x2 - x1, y2 - y1)


def detect_hatched_roof(page: fitz.Page, scale_ratio: float, slope_deg: float = 0.0) -> dict[str, Any]:
    """Find the dominant parallel-hatched roof rectangle and measure its outer band.

    This is intentionally conservative: it only returns a result when a dense run
    of long, near-identical horizontal vector lines exists. Non-rectangular or
    raster roofs are withheld instead of guessed.
    """
    W, H = page.rect.width, page.rect.height
    horizontals: list[tuple[float, float, float, float, float]] = []
    for x1, y1, x2, y2, length in iter_line_segments(page):
        if abs(y2 - y1) > 0.35:
            continue
        xa, xb = sorted((x1, x2))
        y = (y1 + y2) / 2
        if not (0.15 * W < xa < 0.65 * W and 0.25 * H < y < 0.82 * H):
            continue
        if not (0.20 * W < length < 0.45 * W):
            continue
        horizontals.append((xa, y, xb, y, length))
    if len(horizontals) < 15:
        return {"status": "WITHHELD", "reason": "no dense roof hatch band"}

    # Cluster by span rounded to 3 pt. The dense hatch uses the same endpoints;
    # outer outline lines are a few points wider and get folded in afterwards.
    buckets: dict[tuple[int, int], list[tuple[float, float, float, float, float]]] = {}
    for seg in horizontals:
        key = (round(seg[0] / 3), round(seg[2] / 3))
        buckets.setdefault(key, []).append(seg)
    dense = max(buckets.values(), key=len)
    if len(dense) < 12:
        return {"status": "WITHHELD", "reason": "roof hatch span is not dominant"}
    x0 = float(np.median([s[0] for s in dense])); x1 = float(np.median([s[2] for s in dense]))
    ys = [s[1] for s in dense]
    y0, y1 = min(ys), max(ys)

    # Expand to nearby outer outline lines, but never more than 8 pt per side.
    nearby = [s for s in horizontals if abs(s[0] - x0) <= 8 and abs(s[2] - x1) <= 8]
    if nearby:
        x0 = min([x0] + [s[0] for s in nearby]); x1 = max([x1] + [s[2] for s in nearby])
        y0 = min([y0] + [s[1] for s in nearby]); y1 = max([y1] + [s[1] for s in nearby])
    width_pt, height_pt = x1 - x0, y1 - y0
    if width_pt <= 0 or height_pt <= 0:
        return {"status": "WITHHELD", "reason": "invalid roof bounds"}
    mpp = m_per_point(scale_ratio)
    projected = width_pt * height_pt * mpp * mpp
    slope_factor = 1.0 / math.cos(math.radians(slope_deg)) if slope_deg else 1.0
    surface = projected * slope_factor
    perimeter = 2 * (width_pt + height_pt) * mpp
    # Confidence is geometry evidence, not probability. Dense repeated hatches +
    # bounded outer expansion is strong on vector CAD exports.
    conf = min(0.98, 0.80 + min(len(dense), 40) / 250)
    return {
        "status": "DETECTED",
        "bounds_pt": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
        "width_m": width_pt * mpp,
        "height_m": height_pt * mpp,
        "projected_area_m2": projected,
        "surface_area_m2": surface,
        "perimeter_m": perimeter,
        "slope_deg": slope_deg,
        "hatch_lines": len(dense),
        "confidence": conf,
    }


def detect_swing_doors(page: fitz.Page, scale_ratio: float, mapped_widths_m: dict[str, str]) -> list[dict[str, Any]]:
    """Detect door swings from one-curve near-square quarter-circle paths.

    CAD door swings are geometry, not OCR. Mapping a measured nominal width to a
    schedule type comes from the drawing profile (e.g. 0.80 m -> D2), not from
    the benchmark BOQ.
    """
    W, H = page.rect.width, page.rect.height
    mpp = m_per_point(scale_ratio)
    mapped = [(float(k), v) for k, v in mapped_widths_m.items()]
    out: list[dict[str, Any]] = []
    for drawing in page.get_drawings():
        curves = [it for it in drawing.get("items", []) if it[0] == "c"]
        if len(curves) != 1:
            continue
        r = drawing["rect"]
        w, h = r.width, r.height
        # Keep central plan only: excludes title block, seals, section bubbles.
        if not (0.20 * W < r.x0 < 0.62 * W and 0.30 * H < r.y0 < 0.78 * H):
            continue
        if not (14 <= w <= 27 and 14 <= h <= 27 and abs(w - h) <= 2.2):
            continue
        observed = ((w + h) / 2) * mpp
        if not mapped:
            continue
        nominal, type_id = min(mapped, key=lambda kv: abs(kv[0] - observed))
        # Width tolerance 4 cm rejects sanitary symbols and unrelated round glyphs.
        if abs(observed - nominal) > 0.04:
            continue
        out.append({
            "type": type_id,
            "nominal_width_m": nominal,
            "observed_width_m": observed,
            "bbox_pt": [r.x0, r.y0, r.x1, r.y1],
            "confidence": max(0.65, 0.98 - abs(observed - nominal) / 0.08),
        })
    return out


def render_gray(page: fitz.Page, render_scale: float) -> np.ndarray:
    pix = page.get_pixmap(matrix=fitz.Matrix(render_scale, render_scale), colorspace=fitz.csGRAY, alpha=False, annots=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def tight_dark_crop(arr: np.ndarray, threshold: int = 200, pad: int = 2) -> np.ndarray:
    ys, xs = np.where(arr < threshold)
    if not len(xs):
        raise ValueError("template region contains no dark pixels")
    x0=max(0,int(xs.min())-pad); x1=min(arr.shape[1],int(xs.max())+pad+1)
    y0=max(0,int(ys.min())-pad); y1=min(arr.shape[0],int(ys.max())+pad+1)
    return arr[y0:y1, x0:x1]


def nms(matches: list[tuple[float,float,float]], min_dist: float) -> list[tuple[float,float,float]]:
    keep: list[tuple[float,float,float]]=[]
    for score,x,y in sorted(matches, reverse=True):
        if all((x-x2)**2+(y-y2)**2 >= min_dist**2 for _,x2,y2 in keep):
            keep.append((score,x,y))
    return keep


def template_sweep(
    template_page: fitz.Page,
    template_rect_pt: list[float],
    target_pages: list[tuple[int, fitz.Page]],
    target_roi_pt: list[float],
    threshold: float,
    render_scale: float = 1.2,
    rotate_90: bool = False,
) -> list[dict[str, Any]]:
    ref = render_gray(template_page, render_scale)
    x0,y0,x1,y1=[int(round(v*render_scale)) for v in template_rect_pt]
    tpl=tight_dark_crop(ref[y0:y1,x0:x1])
    templates=[(0,tpl)]
    if rotate_90:
        templates.append((90,cv2.rotate(tpl,cv2.ROTATE_90_CLOCKWISE)))
    all_hits=[]
    for page_no,page in target_pages:
        arr=render_gray(page,render_scale)
        rx0,ry0,rx1,ry1=[int(round(v*render_scale)) for v in target_roi_pt]
        crop=255-arr[ry0:ry1,rx0:rx1]
        raw=[]
        for rotation,t in templates:
            ti=255-t
            if crop.shape[0] < ti.shape[0] or crop.shape[1] < ti.shape[1]:
                continue
            res=cv2.matchTemplate(crop,ti,cv2.TM_CCOEFF_NORMED)
            ys,xs=np.where(res>=threshold)
            for yy,xx in zip(ys,xs):
                raw.append((float(res[yy,xx]),xx+rx0+ti.shape[1]/2,yy+ry0+ti.shape[0]/2,rotation,max(ti.shape)))
        merged=[]
        for score,x,y,rotation,size in sorted(raw, reverse=True):
            if all((x-h['x_px'])**2+(y-h['y_px'])**2 >= (max(size,h['size_px'])*0.72)**2 for h in merged):
                merged.append({"score":score,"x_px":x,"y_px":y,"rotation":rotation,"size_px":size})
        for h in merged:
            all_hits.append({
                "page":page_no,
                "x_norm":h["x_px"]/arr.shape[1],
                "y_norm":h["y_px"]/arr.shape[0],
                "match_score":h["score"],
                "rotation":h["rotation"],
            })
    return all_hits



def detect_text_label_counts(page: fitz.Page, specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count exact positioned plan tags, never inferred semantic quantities.

    Profiles name tags that are visibly printed on the drawing (for example BP
    for booster pump). This deliberately does not decode broken legacy Thai CAD
    glyph strings or read benchmark/reference pages.
    """
    words=page.get_text("words") or []
    out=[]
    for spec in specs:
        tokens={str(t).strip().upper() for t in spec.get("tokens",[spec.get("token","")]) if str(t).strip()}
        bounds=spec.get("bounds_pt")
        hits=[]
        for w in words:
            x0,y0,x1,y1,text=w[:5]; key=str(text).strip().upper()
            if key not in tokens: continue
            if bounds:
                bx0,by0,bx1,by1=map(float,bounds); cx=(x0+x1)/2; cy=(y0+y1)/2
                if not (bx0<=cx<=bx1 and by0<=cy<=by1): continue
            hits.append({"text":str(text).strip(),"bbox_pt":[round(float(x0),2),round(float(y0),2),round(float(x1),2),round(float(y1),2)]})
        out.append({"spec":spec,"hits":hits})
    return out


def quantity_row(item_id: str, description: str, category: str, unit: str, quantity: float, confidence: float,
                 method: str, pages: list[int], evidence: dict[str, Any], review: str = "REVIEW_REQUIRED") -> dict[str, Any]:
    return {
        "id": item_id,
        "description": description,
        "category": category,
        "unit": unit,
        "quantity": round(float(quantity), 3),
        "confidence": round(float(confidence), 3),
        "method": method,
        "source_pages": sorted(set(pages)),
        "review": review,
        "evidence": evidence,
    }


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    profile=json.loads(profile_path.read_text(encoding="utf-8"))
    max_page=int(profile["source_page_max"])
    doc=fitz.open(pdf_path)
    if doc.page_count <= max_page:
        raise ValueError("benchmark/source fence is inconsistent with document page count")
    guarded=GuardedPdf(doc,max_page)
    rows=[]; diagnostics=[]

    roof_cfg=profile.get("roof")
    if roof_cfg:
        p=int(roof_cfg["page"]); page=guarded.page(p)
        rr=detect_hatched_roof(page,float(roof_cfg["scale_ratio"]),float(roof_cfg.get("slope_deg",0)))
        diagnostics.append({"detector":"roof_hatch_band","page":p,**rr})
        if rr.get("status")=="DETECTED":
            rows.append(quantity_row("ARCH-ROOF-METAL","หลังคาเหล็กรีดลอน","Architecture","m²",rr["surface_area_m2"],rr["confidence"],"vector:hatch-band + slope",[p],{"bounds_pt":rr["bounds_pt"],"projected_area_m2":round(rr["projected_area_m2"],3),"slope_deg":rr["slope_deg"],"hatch_lines":rr["hatch_lines"]}))
            rows.append(quantity_row("ARCH-FASCIA","เชิงชาย / ขอบหลังคา","Architecture","m",rr["perimeter_m"],min(rr["confidence"],0.96),"vector:roof-outline perimeter",[p],{"bounds_pt":rr["bounds_pt"]}))

    door_cfg=profile.get("doors")
    if door_cfg:
        all_doors=[]
        for p in door_cfg["pages"]:
            pp=guarded.page(int(p))
            ds=detect_swing_doors(pp,float(door_cfg["scale_ratio"]),door_cfg["type_by_nominal_width_m"])
            for d in ds: d["page"]=int(p)
            all_doors.extend(ds)
        by_type={}
        for d in all_doors: by_type.setdefault(d["type"],[]).append(d)
        for type_id,ds in sorted(by_type.items()):
            rows.append(quantity_row(f"ARCH-DOOR-{type_id}",f"ประตู {type_id}","Architecture","ea",len(ds),float(np.median([d["confidence"] for d in ds])),"vector:door-swing radius",[d["page"] for d in ds],{"detections":[{"page":d["page"],"nominal_width_m":d["nominal_width_m"],"observed_width_m":round(d["observed_width_m"],3),"bbox_pt":[round(v,2) for v in d["bbox_pt"]]} for d in ds]}))
        diagnostics.append({"detector":"door_swing","pages":door_cfg["pages"],"detections":len(all_doors),"by_type":{k:len(v) for k,v in by_type.items()}})

    sanitary=profile.get("sanitary")
    if sanitary:
        p=int(sanitary["page"]); results=detect_text_label_counts(guarded.page(p),sanitary.get("label_counts",[]))
        for result in results:
            spec=result["spec"]; hits=result["hits"]
            diagnostics.append({"detector":f"sanitary_label:{spec['id']}","page":p,"detections":len(hits),"status":"DETECTED" if hits else "WITHHELD"})
            if hits:
                rows.append(quantity_row(spec["id"],spec["description"],"Sanitary","ea",len(hits),float(spec.get("confidence",0.92)),"text:exact positioned plan label",[p],{"matched_tokens":hits,"tokens":spec.get("tokens",[spec.get("token")])}))

    fixtures=profile.get("fixture_templates")
    if fixtures:
        render_scale=float(fixtures.get("render_scale",1.5))
        for detector in fixtures.get("templates",[]):
            source_p=int(detector["template_page"])
            target_pages=[(int(p),guarded.page(int(p))) for p in detector["target_pages"]]
            hits=template_sweep(
                guarded.page(source_p), detector["template_rect_pt"], target_pages,
                detector["target_roi_pt"], float(detector["threshold"]), render_scale,
                bool(detector.get("rotate_90",False)),
            )
            median=float(np.median([h["match_score"] for h in hits])) if hits else 0.0
            diagnostics.append({
                "detector":f"fixture_template:{detector['id']}", "template_page":source_p,
                "target_pages":detector["target_pages"], "detections":len(hits),
                "median_score":median, "status":"DETECTED" if hits else "WITHHELD",
            })
            if hits:
                rows.append(quantity_row(
                    detector["id"], detector["description"], detector.get("category","Sanitary"), "ea", len(hits),
                    median, "raster:drawing-label template sweep",
                    sorted(set([source_p]+[h["page"] for h in hits])),
                    {"template_page":source_p,"template_rect_pt":detector["template_rect_pt"],
                     "detections":hits,"threshold":detector["threshold"]},
                ))

    elec=profile.get("electrical")
    if elec:
        legend_p=int(elec["legend_page"]); legend=guarded.page(legend_p)
        targets=[(int(p),guarded.page(int(p))) for p in elec["lighting_pages"]]
        for detector in elec.get("symbol_templates", []):
            hits=template_sweep(
                legend, detector["template_rect_pt"], targets, detector["target_roi_pt"],
                float(detector["threshold"]), float(elec.get("render_scale",1.2)),
                bool(detector.get("rotate_90",False)),
            )
            median=float(np.median([h["match_score"] for h in hits])) if hits else 0.0
            if hits:
                rows.append(quantity_row(
                    detector["id"], detector["description"], "Electrical", "ea", len(hits),
                    median, "raster:legend-template sweep", [legend_p]+[h["page"] for h in hits],
                    {"legend_page":legend_p,"detections":hits,"threshold":detector["threshold"],"template":detector.get("template_name",detector["id"])},
                ))
            diagnostics.append({
                "detector":f"electrical_template:{detector['id']}","legend_page":legend_p,
                "target_pages":elec["lighting_pages"],"detections":len(hits),"median_score":median,
                "status":"DETECTED" if hits else "WITHHELD",
            })

    # Hard guard: every generated quantity/evidence source must stay in drawing pages.
    for row in rows:
        if any(p>max_page for p in row["source_pages"]):
            raise AssertionError(f"reference leakage: {row['id']} cites a source page after {max_page}")
    coverage={
        "supported_detectors":["roof/fascia vector hatch band","0.70/0.80 m swing-door counts","sanitary exact plan-label counts","sanitary fixture drawing-label templates","electrical legend-template sweeps"],
        "withheld_detectors":[
            {"name":"windows","status":"WITHHELD","reason":"type/count mapping not yet reliable on this CAD-font set"},
            {"name":"sanitary fixtures beyond WC.1","status":"WITHHELD","reason":"additional fixture labels/symbols still need validated plan-view fingerprints"},
            {"name":"switch/socket","status":"WITHHELD","reason":"generic dot/line symbols produce unsafe false positives without corroboration"},
            {"name":"floor finishes","status":"WITHHELD","reason":"finish-code text extraction is unreliable on legacy Thai CAD fonts"},
            {"name":"wall area","status":"WITHHELD","reason":"requires opening deductions and wall-height evidence before publication"},
            {"name":"sanitary piping","status":"WITHHELD","reason":"line-role classification and fitting/branch rules are not validated yet"},
            {"name":"structure","status":"WITHHELD","reason":"structural member classification is not validated yet"}
        ],
        "note":"Unsupported items are withheld rather than fabricated.",
    }
    result={
        "schema":SCHEMA,
        "document":{"name":pdf_path.name,"sha256":sha256_file(pdf_path),"pages":doc.page_count},
        "source_policy":{"drawing_pages":[1,max_page],"reference_pages_forbidden":list(range(max_page+1,doc.page_count+1)),"reference_used_for_generation":False},
        "profile":{"id":profile.get("id","unknown"),"version":profile.get("version",1)},
        "status":"AUTOMATIC_PRELIMINARY_REVIEW_REQUIRED",
        "rows":rows,
        "coverage":coverage,
        "diagnostics":diagnostics,
    }
    doc.close()
    return result


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--pdf",type=Path,required=True)
    ap.add_argument("--profile",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    result=extract(args.pdf,args.profile)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("AUTO_BOQ_OK",json.dumps({"rows":len(result["rows"]),"ids":[r["id"] for r in result["rows"]],"output":str(args.output)},ensure_ascii=False))

if __name__=="__main__": main()
