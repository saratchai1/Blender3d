from __future__ import annotations

import heapq
import math
import re
from collections import defaultdict
from typing import Any

PIPE_SYSTEMS = ("CW", "W", "SW", "S", "V", "RL")
SYSTEM_RX = r"(?:CW|SW|RL|W|V|S)"
STANDARD_DN_BY_INCH = {
    0.5: 15,
    0.75: 20,
    1.0: 25,
    1.25: 32,
    1.5: 40,
    2.0: 50,
    2.5: 65,
    3.0: 80,
    4.0: 100,
    5.0: 125,
    6.0: 150,
    8.0: 200,
    10.0: 250,
    12.0: 300,
}
STANDARD_DN = set(STANDARD_DN_BY_INCH.values())
NUMBER_RX = r"\d+(?:\s*[- ]\s*\d+\s*/\s*\d+|\s*/\s*\d+|\.\d+)?"
DIAMETER_RX = rf"(?:DIA\.?\s*)?(?:Ø|∅)?\s*(?:DN\s*)?{NUMBER_RX}\s*(?:MM|IN(?:CH(?:ES)?)?|[\"”″])?"
TAG_PATTERNS = (
    re.compile(rf"(?P<dia>{DIAMETER_RX})\s*(?P<system>{SYSTEM_RX})(?![A-Z])", re.IGNORECASE),
    re.compile(rf"(?P<system>{SYSTEM_RX})(?![A-Z])\s*(?P<dia>{DIAMETER_RX})", re.IGNORECASE),
)


def parse_fractional_number(token: str) -> float:
    value = re.sub(r"\s+", "", str(token or "").strip())
    if not value:
        raise ValueError("empty diameter")
    if "-" in value:
        whole, fraction = value.split("-", 1)
        return float(whole) + parse_fractional_number(fraction)
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        if not denominator or float(denominator) == 0:
            raise ValueError("invalid fraction")
        # Family4 CAD text can collapse 2 1/2 -> 21/2 and 1 1/2 -> 11/2.
        if len(numerator) > 1 and denominator in {"2", "4", "8", "16"}:
            return float(numerator[:-1]) + float(numerator[-1]) / float(denominator)
        return float(numerator) / float(denominator)
    return float(value)


def _nearest_standard_dn(inches: float, tol: float = 1e-6) -> int | None:
    for nominal_in, dn in STANDARD_DN_BY_INCH.items():
        if abs(float(inches) - nominal_in) <= tol:
            return dn
    return None


def normalize_diameter(raw: str) -> dict[str, Any]:
    text = str(raw or "").upper().strip()
    text = re.sub(r"\bDIA\.?\s*", "", text)
    text = text.replace("∅", "Ø")
    is_dn = bool(re.search(r"\bDN\s*\d", text))
    is_mm = bool(re.search(r"\bMM\b", text))
    is_inch = bool(re.search(r"(?:INCH(?:ES)?|\bIN\b|[\"”″])", text))
    number_match = re.search(NUMBER_RX, text)
    if not number_match:
        raise ValueError(f"no diameter number in {raw!r}")
    number = parse_fractional_number(number_match.group(0))
    if number <= 0:
        raise ValueError("diameter must be positive")

    if is_dn:
        dn = int(round(number))
        return {
            "diameter_key": f"DN{dn}",
            "dn": dn,
            "diameter_mm": float(dn),
            "diameter_in": None,
            "diameter_raw": raw,
            "diameter_basis": "EXPLICIT_DN",
            "diameter_confidence": 1.0,
        }
    if is_mm:
        mm = float(number)
        dn = int(round(mm)) if abs(mm - round(mm)) <= 1e-6 and int(round(mm)) in STANDARD_DN else None
        return {
            "diameter_key": f"DN{dn}" if dn else f"{mm:g}mm",
            "dn": dn,
            "diameter_mm": mm,
            "diameter_in": None,
            "diameter_raw": raw,
            "diameter_basis": "EXPLICIT_MM",
            "diameter_confidence": 1.0,
        }

    # Explicit quote/inch is authoritative. For Family4's compact tags (e.g. Ø2V)
    # a small bare value is conventionally inches; values >=10 are treated as mm
    # but kept at lower confidence because the unit is absent.
    if is_inch or number < 10:
        inches = float(number)
        dn = _nearest_standard_dn(inches)
        return {
            "diameter_key": f"DN{dn}" if dn else f"{inches:g}in",
            "dn": dn,
            "diameter_mm": float(dn) if dn else round(inches * 25.4, 3),
            "diameter_in": inches,
            "diameter_raw": raw,
            "diameter_basis": "EXPLICIT_INCH" if is_inch else "FAMILY4_BARE_SMALL_VALUE_INCH",
            "diameter_confidence": 1.0 if is_inch else 0.92,
        }

    mm = float(number)
    dn = int(round(mm)) if abs(mm - round(mm)) <= 1e-6 and int(round(mm)) in STANDARD_DN else None
    return {
        "diameter_key": f"DN{dn}" if dn else f"{mm:g}mm",
        "dn": dn,
        "diameter_mm": mm,
        "diameter_in": None,
        "diameter_raw": raw,
        "diameter_basis": "BARE_LARGE_VALUE_MM_HEURISTIC",
        "diameter_confidence": 0.85,
    }


def extract_pipe_tag_classes(text: str) -> list[dict[str, Any]]:
    raw = str(text or "").upper()
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for pattern in TAG_PATTERNS:
        for match in pattern.finditer(raw):
            system = match.group("system").upper()
            try:
                dia = normalize_diameter(match.group("dia"))
            except ValueError:
                continue
            key = (system, dia["diameter_key"])
            if key in seen:
                continue
            seen.add(key)
            out.append({"system": system, **dia})
    return out


def _distance_point_segment(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    wx, wy = point[0] - a[0], point[1] - a[1]
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    px, py = a[0] + t * vx, a[1] + t * vy
    return math.hypot(point[0] - px, point[1] - py)


def _segment_adjacency(segments: list[dict[str, Any]], members: list[int], snap_pt: float) -> dict[int, set[int]]:
    graph: dict[int, set[int]] = {i: set() for i in members}
    for pos, i in enumerate(members):
        si = segments[i]
        for j in members[pos + 1:]:
            sj = segments[j]
            linked = any(
                _distance_point_segment(endpoint, sj["a"], sj["b"]) <= snap_pt
                for endpoint in (si["a"], si["b"])
            ) or any(
                _distance_point_segment(endpoint, si["a"], si["b"]) <= snap_pt
                for endpoint in (sj["a"], sj["b"])
            )
            if linked:
                graph[i].add(j)
                graph[j].add(i)
    return graph


def assign_segment_diameters(
    segments: list[dict[str, Any]],
    components: list[dict[str, Any]],
    tags: list[dict[str, Any]],
    *,
    endpoint_snap_pt: float = 1.5,
    tie_tolerance_pt: float = 0.5,
) -> list[dict[str, Any]]:
    tags_by_component: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for tag in tags:
        cid = tag.get("component_id")
        seed = tag.get("nearest_segment")
        if cid is None or seed is None or not tag.get("diameter_key"):
            continue
        tags_by_component[int(cid)].append(tag)

    assignments: list[dict[str, Any]] = []
    for component in components:
        cid = int(component["id"])
        members = list(component["segment_indexes"])
        seeds = tags_by_component.get(cid, [])
        if not seeds:
            assignments.extend({
                "component_id": cid,
                "segment_index": i,
                "layer": segments[i].get("layer", ""),
                "length_pt": float(segments[i]["length_pt"]),
                "status": "WITHHELD_NO_DIAMETER_EVIDENCE",
                "classes": [],
            } for i in members)
            continue

        seed_classes: dict[int, set[tuple[str, str]]] = defaultdict(set)
        class_meta: dict[tuple[str, str], dict[str, Any]] = {}
        for tag in seeds:
            cls = (str(tag["system"]), str(tag["diameter_key"]))
            seed_classes[int(tag["nearest_segment"])].add(cls)
            class_meta.setdefault(cls, {
                "system": tag["system"],
                "diameter_key": tag["diameter_key"],
                "dn": tag.get("dn"),
                "diameter_mm": tag.get("diameter_mm"),
                "diameter_in": tag.get("diameter_in"),
            })

        unique_classes = {cls for classes in seed_classes.values() for cls in classes}
        if len(unique_classes) == 1:
            cls = next(iter(unique_classes))
            meta = class_meta[cls]
            seed_indexes = set(seed_classes)
            assignments.extend({
                "component_id": cid,
                "segment_index": i,
                "layer": segments[i].get("layer", ""),
                "length_pt": float(segments[i]["length_pt"]),
                "status": "EXPLICIT_TAG_SEED" if i in seed_indexes else "COMPONENT_SINGLE_CLASS_PROPAGATION",
                "classes": [meta],
            } for i in members)
            continue

        graph = _segment_adjacency(segments, members, endpoint_snap_pt)
        best_distance: dict[int, float] = {i: math.inf for i in members}
        labels: dict[int, set[tuple[str, str]]] = {i: set() for i in members}
        queue: list[tuple[float, int, str, str]] = []
        for seed_index, classes in seed_classes.items():
            for system, diameter_key in classes:
                heapq.heappush(queue, (0.0, seed_index, system, diameter_key))

        while queue:
            distance, index, system, diameter_key = heapq.heappop(queue)
            cls = (system, diameter_key)
            if distance > best_distance[index] + tie_tolerance_pt:
                continue
            if distance + tie_tolerance_pt < best_distance[index]:
                best_distance[index] = distance
                labels[index] = {cls}
            elif abs(distance - best_distance[index]) <= tie_tolerance_pt:
                labels[index].add(cls)
            for neighbor in graph[index]:
                weight = (float(segments[index]["length_pt"]) + float(segments[neighbor]["length_pt"])) / 2.0
                new_distance = distance + weight
                if new_distance <= best_distance[neighbor] + tie_tolerance_pt:
                    heapq.heappush(queue, (new_distance, neighbor, system, diameter_key))

        for i in members:
            segment_labels = labels[i]
            classes = [class_meta[cls] for cls in sorted(segment_labels)]
            if len(segment_labels) == 1:
                status = "EXPLICIT_TAG_SEED" if i in seed_classes and len(seed_classes[i]) == 1 else "NETWORK_NEAREST_TAG_PROPAGATION"
            elif len(segment_labels) > 1:
                status = "WITHHELD_DIAMETER_TIE"
            else:
                status = "WITHHELD_UNREACHABLE_FROM_DIAMETER_SEED"
            assignments.append({
                "component_id": cid,
                "segment_index": i,
                "layer": segments[i].get("layer", ""),
                "length_pt": float(segments[i]["length_pt"]),
                "status": status,
                "classes": classes,
            })
    assignments.sort(key=lambda row: (row["component_id"], row["segment_index"]))
    return assignments


def aggregate_diameter_rows(assignments: list[dict[str, Any]], scale_ratio: int | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    total_pt = 0.0
    assigned_pt = 0.0
    ambiguous_pt = 0.0
    for row in assignments:
        length_pt = float(row["length_pt"])
        total_pt += length_pt
        if len(row.get("classes", [])) != 1 or row["status"].startswith("WITHHELD"):
            ambiguous_pt += length_pt
            continue
        assigned_pt += length_pt
        cls = row["classes"][0]
        key = (str(cls["system"]), str(cls["diameter_key"]))
        entry = grouped.setdefault(key, {
            "system": cls["system"],
            "diameter_key": cls["diameter_key"],
            "dn": cls.get("dn"),
            "diameter_mm": cls.get("diameter_mm"),
            "diameter_in": cls.get("diameter_in"),
            "length_pt": 0.0,
            "segment_count": 0,
        })
        entry["length_pt"] += length_pt
        entry["segment_count"] += 1
    rows = []
    for entry in grouped.values():
        entry["length_pt"] = round(float(entry["length_pt"]), 3)
        if scale_ratio:
            entry["scale_ratio"] = int(scale_ratio)
            entry["length_m_candidate"] = round(float(entry["length_pt"]) / 72.0 * 0.0254 * int(scale_ratio), 3)
        rows.append(entry)
    rows.sort(key=lambda r: (r["system"], r["diameter_key"]))
    coverage = {
        "total_length_pt": round(total_pt, 3),
        "assigned_length_pt": round(assigned_pt, 3),
        "withheld_length_pt": round(ambiguous_pt, 3),
        "assigned_fraction": round(assigned_pt / total_pt, 4) if total_pt else 0.0,
    }
    return rows, coverage


def reconcile_pages(pages: list[dict[str, Any]], *, min_primary_diameter_coverage: float = 0.95) -> dict[str, Any]:
    additive: dict[tuple[str, str], dict[str, Any]] = {}
    excluded: list[dict[str, Any]] = []
    primary_pages: list[int] = []
    primary_ready = True
    for page in pages:
        policy = str(page.get("contribution_policy") or "")
        page_no = int(page.get("page", 0))
        if policy == "PRIMARY_PLAN_HORIZONTAL":
            primary_pages.append(page_no)
            coverage = float((page.get("diameter_coverage") or {}).get("assigned_fraction", 0.0))
            scale_candidates = page.get("effective_scale_candidates") or []
            if coverage < min_primary_diameter_coverage or len(scale_candidates) != 1:
                primary_ready = False
            for row in page.get("diameter_rows", []):
                if "length_m_candidate" not in row:
                    primary_ready = False
                    continue
                key = (str(row["system"]), str(row["diameter_key"]))
                entry = additive.setdefault(key, {
                    "system": row["system"],
                    "diameter_key": row["diameter_key"],
                    "dn": row.get("dn"),
                    "diameter_mm": row.get("diameter_mm"),
                    "diameter_in": row.get("diameter_in"),
                    "length_m_candidate": 0.0,
                    "source_pages": [],
                    "segment_count": 0,
                })
                entry["length_m_candidate"] += float(row["length_m_candidate"])
                entry["segment_count"] += int(row.get("segment_count", 0))
                if page_no not in entry["source_pages"]:
                    entry["source_pages"].append(page_no)
        else:
            reason = (
                "VERTICAL_SCHEMATIC_EVIDENCE_ONLY"
                if policy.startswith("DIAGNOSTIC_VERTICAL")
                else "DETAIL_OVERLAY_EVIDENCE_ONLY"
                if policy.startswith("DETAIL_OVERLAY")
                else "NON_PRIMARY_VIEW_WITHHELD"
            )
            excluded.append({"page": page_no, "sheet": page.get("sheet"), "view_role": page.get("view_role"), "reason": reason})

    rows = []
    for entry in additive.values():
        entry["length_m_candidate"] = round(float(entry["length_m_candidate"]), 3)
        entry["source_pages"].sort()
        rows.append(entry)
    rows.sort(key=lambda r: (r["system"], r["diameter_key"]))
    return {
        "horizontal_primary_rows": rows,
        "primary_pages": sorted(primary_pages),
        "excluded_non_additive_views": excluded,
        "cross_view_policy_status": "PASS_NON_ADDITIVE_BY_VIEW_ROLE",
        "horizontal_diameter_gate": "PASS" if primary_ready and primary_pages else "WITHHELD",
        "full_pipe_boq_publication_status": "WITHHELD_VERTICAL_AND_DETAIL_RECONCILIATION",
        "note": "Only PRIMARY_PLAN_HORIZONTAL contributes to horizontal candidates. Vertical schematic and enlarged details are evidence-only, so repeated physical pipework cannot be summed across overlapping views.",
    }
