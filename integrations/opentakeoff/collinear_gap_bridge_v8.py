from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _angle_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0


def _angle_diff_deg(a: float, b: float) -> float:
    d = abs(float(a) - float(b)) % 180.0
    return min(d, 180.0 - d)


def _endpoint_gap(
    component_a: dict[str, Any],
    component_b: dict[str, Any],
    segments: list[dict[str, Any]],
) -> dict[str, Any] | None:
    best: tuple[float, float, int, int, tuple[float, float], tuple[float, float]] | None = None
    for i in component_a["segment_indexes"]:
        si = segments[i]
        ai = _angle_deg(si["a"], si["b"])
        for p in (si["a"], si["b"]):
            for j in component_b["segment_indexes"]:
                sj = segments[j]
                aj = _angle_deg(sj["a"], sj["b"])
                angle_diff = _angle_diff_deg(ai, aj)
                for q in (sj["a"], sj["b"]):
                    gap = math.hypot(float(p[0]) - float(q[0]), float(p[1]) - float(q[1]))
                    key = (gap, angle_diff, int(i), int(j), p, q)
                    if best is None or key[:4] < best[:4]:
                        best = key
    if best is None:
        return None
    gap, angle_diff, i, j, p, q = best
    return {
        "gap_pt": float(gap),
        "angle_diff_deg": float(angle_diff),
        "segment_a": int(i),
        "segment_b": int(j),
        "endpoint_a_pt": [float(p[0]), float(p[1])],
        "endpoint_b_pt": [float(q[0]), float(q[1])],
    }


def _seed_class_map(tags: list[dict[str, Any]], component_by_segment: dict[int, int]) -> tuple[dict[int, set[tuple[str, str]]], dict[tuple[str, str], dict[str, Any]]]:
    by_component: dict[int, set[tuple[str, str]]] = defaultdict(set)
    meta: dict[tuple[str, str], dict[str, Any]] = {}
    for tag in tags:
        index = tag.get("nearest_segment")
        if index is None or tag.get("system") is None or tag.get("diameter_key") is None:
            continue
        try:
            cid = int(tag.get("component_id")) if tag.get("component_id") is not None else int(component_by_segment[int(index)])
        except (KeyError, TypeError, ValueError):
            continue
        cls = (str(tag["system"]), str(tag["diameter_key"]))
        by_component[cid].add(cls)
        meta.setdefault(cls, {
            "system": tag["system"],
            "diameter_key": tag["diameter_key"],
            "dn": tag.get("dn"),
            "diameter_mm": tag.get("diameter_mm"),
            "diameter_in": tag.get("diameter_in"),
        })
    return by_component, meta


def bridge_diameter_tags(
    segments: list[dict[str, Any]],
    components: list[dict[str, Any]],
    tags: list[dict[str, Any]],
    *,
    max_gap_pt: float = 9.0,
    max_angle_diff_deg: float = 5.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create diameter-only seeds across tiny collinear same-layer CAD gaps.

    Safety rules:
    - same semantic layer only;
    - endpoint-to-endpoint gap only (never endpoint-to-interior T-junction bridge);
    - local segments must be collinear within max_angle_diff_deg;
    - all explicit/transferred seed classes inside one bridge-connected group must
      agree exactly on system + diameter; any disagreement withholds the group;
    - only existing segment lengths are classified; the geometric gap is never
      added as pipe length.
    """
    component_by_id = {int(c["id"]): c for c in components}
    component_by_segment: dict[int, int] = {}
    for c in components:
        for i in c["segment_indexes"]:
            component_by_segment[int(i)] = int(c["id"])
    seeds_by_component, class_meta = _seed_class_map(tags, component_by_segment)

    parent = {int(c["id"]): int(c["id"]) for c in components}
    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    edges: list[dict[str, Any]] = []
    for pos, ca in enumerate(components):
        layer_a = str(ca.get("layer") or "")
        if not layer_a:
            continue
        for cb in components[pos + 1:]:
            if str(cb.get("layer") or "") != layer_a:
                continue
            evidence = _endpoint_gap(ca, cb, segments)
            if not evidence:
                continue
            if evidence["gap_pt"] > float(max_gap_pt):
                continue
            if evidence["angle_diff_deg"] > float(max_angle_diff_deg):
                continue
            a = int(ca["id"]); b = int(cb["id"])
            union(a, b)
            edges.append({
                "component_a": a,
                "component_b": b,
                "layer": layer_a,
                **evidence,
            })

    groups: dict[int, list[int]] = defaultdict(list)
    for cid in parent:
        groups[find(cid)].append(cid)

    augmented = list(tags)
    events: list[dict[str, Any]] = []
    edges_by_group: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        edges_by_group[find(int(edge["component_a"]))].append(edge)

    for root, members in groups.items():
        if len(members) < 2:
            continue
        classes: set[tuple[str, str]] = set()
        seeded_members: list[int] = []
        for cid in members:
            member_classes = seeds_by_component.get(cid, set())
            if member_classes:
                seeded_members.append(cid)
                classes.update(member_classes)
        if not classes:
            continue
        if len(classes) != 1:
            events.append({
                "status": "WITHHELD_BRIDGE_GROUP_CONFLICTING_DIAMETERS",
                "component_ids": sorted(members),
                "classes": [{"system": s, "diameter_key": d} for s, d in sorted(classes)],
                "bridge_edges": edges_by_group.get(root, []),
            })
            continue
        cls = next(iter(classes))
        meta = class_meta[cls]
        for cid in sorted(members):
            if seeds_by_component.get(cid):
                continue
            component = component_by_id[cid]
            # Pick the segment participating in the shortest accepted bridge edge
            # touching this component so evidence is auditable and deterministic.
            touching = [e for e in edges_by_group.get(root, []) if cid in (int(e["component_a"]), int(e["component_b"]))]
            touching.sort(key=lambda e: (float(e["gap_pt"]), float(e["angle_diff_deg"]), int(e["segment_a"]), int(e["segment_b"])))
            if not touching:
                continue
            edge = touching[0]
            if cid == int(edge["component_a"]):
                seed_segment = int(edge["segment_a"])
            else:
                seed_segment = int(edge["segment_b"])
            synthetic = {
                "text": "COLLINEAR_GAP_BRIDGE",
                **meta,
                "nearest_segment": seed_segment,
                "component_id": cid,
                "expected_layer": component.get("layer"),
                "associated_layer": component.get("layer"),
                "association_basis": "COLLINEAR_ENDPOINT_GAP_BRIDGE",
                "association_status": "ASSOCIATED_BY_COLLINEAR_ENDPOINT_GAP_BRIDGE",
                "evidence_role": "DIAMETER_SEED_ONLY_NO_GAP_LENGTH",
                "bridge_gap_pt": round(float(edge["gap_pt"]), 3),
                "bridge_angle_diff_deg": round(float(edge["angle_diff_deg"]), 3),
                "bridge_source_components": sorted(seeded_members),
                "bridge_group_components": sorted(members),
            }
            augmented.append(synthetic)
            events.append({
                **synthetic,
                "status": "ACCEPTED_COLLINEAR_GAP_DIAMETER_SEED",
                "component_length_pt": round(float(component.get("length_pt", 0.0)), 3),
            })
    return augmented, events
