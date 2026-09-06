from __future__ import annotations

import heapq
import math
from typing import Any


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def distance_point_segment(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    vx, vy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
    wx, wy = float(point[0]) - float(a[0]), float(point[1]) - float(a[1])
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        return _distance(point, a)
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    projection = (float(a[0]) + t * vx, float(a[1]) + t * vy)
    return _distance(point, projection)


def _point_rect_distance(point: tuple[float, float], rect: list[float]) -> float:
    x0, y0, x1, y1 = map(float, rect)
    x, y = map(float, point)
    dx = max(x0 - x, 0.0, x - x1)
    dy = max(y0 - y, 0.0, y - y1)
    return math.hypot(dx, dy)


def _segment_rect_distance(segment: dict[str, Any], rect: list[float]) -> float:
    # Leaders normally terminate at a text-box edge. Endpoint distance is both
    # conservative and robust against a long unrelated line merely crossing text.
    return min(
        _point_rect_distance(tuple(segment["a"]), rect),
        _point_rect_distance(tuple(segment["b"]), rect),
    )


def _segment_length(segment: dict[str, Any]) -> float:
    if segment.get("length_pt") is not None:
        return float(segment["length_pt"])
    return _distance(tuple(segment["a"]), tuple(segment["b"]))


def _expanded_rect(rect: list[float], margin: float) -> list[float]:
    x0, y0, x1, y1 = map(float, rect)
    return [x0 - margin, y0 - margin, x1 + margin, y1 + margin]


def _bbox_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax0 = min(float(a["a"][0]), float(a["b"][0])); ax1 = max(float(a["a"][0]), float(a["b"][0]))
    ay0 = min(float(a["a"][1]), float(a["b"][1])); ay1 = max(float(a["a"][1]), float(a["b"][1]))
    bx0 = min(float(b["a"][0]), float(b["b"][0])); bx1 = max(float(b["a"][0]), float(b["b"][0]))
    by0 = min(float(b["a"][1]), float(b["b"][1])); by1 = max(float(b["a"][1]), float(b["b"][1]))
    dx = max(bx0 - ax1, ax0 - bx1, 0.0)
    dy = max(by0 - ay1, ay0 - by1, 0.0)
    return math.hypot(dx, dy)


def _segments_touch(a: dict[str, Any], b: dict[str, Any], snap_pt: float) -> bool:
    if _bbox_distance(a, b) > snap_pt:
        return False
    return (
        distance_point_segment(tuple(a["a"]), tuple(b["a"]), tuple(b["b"])) <= snap_pt
        or distance_point_segment(tuple(a["b"]), tuple(b["a"]), tuple(b["b"])) <= snap_pt
        or distance_point_segment(tuple(b["a"]), tuple(a["a"]), tuple(a["b"])) <= snap_pt
        or distance_point_segment(tuple(b["b"]), tuple(a["a"]), tuple(a["b"])) <= snap_pt
    )


def _leader_to_target_distance(leader: dict[str, Any], target: dict[str, Any]) -> float:
    return min(
        distance_point_segment(tuple(leader["a"]), tuple(target["a"]), tuple(target["b"])),
        distance_point_segment(tuple(leader["b"]), tuple(target["a"]), tuple(target["b"])),
    )


def find_leader_target(
    *,
    tag_bbox_pt: list[float],
    segments: list[dict[str, Any]],
    component_by_segment: dict[int, int],
    expected_layer: str,
    source_snap_pt: float = 3.0,
    leader_snap_pt: float = 1.5,
    target_snap_pt: float = 2.5,
    max_leader_segment_pt: float = 80.0,
    max_path_pt: float = 120.0,
    max_hops: int = 4,
    ambiguity_margin_pt: float = 1.0,
) -> dict[str, Any]:
    """Follow an explicit non-pipe leader from a text box to one semantic pipe.

    The resolver is intentionally asymmetric: the expected CAD layer may only be
    a terminal target, never an intermediate leader. Therefore a connected pipe
    network cannot be traversed to manufacture an association. A result is accepted
    only when the best path resolves to one component with sufficient margin over
    the next component; otherwise it is withheld.
    """
    layer = str(expected_layer or "").strip().upper()
    if not layer:
        return {"status": "WITHHELD_NO_EXPECTED_LAYER"}

    target_indexes = [
        i for i, segment in enumerate(segments)
        if str(segment.get("layer") or "").strip().upper() == layer
    ]
    if not target_indexes:
        return {"status": "WITHHELD_EXPECTED_LAYER_ABSENT"}

    # Keep the leader graph local to the tag. This prevents distant dimension and
    # architectural networks from becoming accidental long leader paths.
    search_rect = _expanded_rect(tag_bbox_pt, max_path_pt + source_snap_pt)
    leader_indexes = []
    for i, segment in enumerate(segments):
        if i in target_indexes:
            continue
        length = _segment_length(segment)
        if length <= 0.25 or length > max_leader_segment_pt:
            continue
        sx0 = min(float(segment["a"][0]), float(segment["b"][0])); sx1 = max(float(segment["a"][0]), float(segment["b"][0]))
        sy0 = min(float(segment["a"][1]), float(segment["b"][1])); sy1 = max(float(segment["a"][1]), float(segment["b"][1]))
        if sx1 < search_rect[0] or sx0 > search_rect[2] or sy1 < search_rect[1] or sy0 > search_rect[3]:
            continue
        leader_indexes.append(i)

    starts = [
        i for i in leader_indexes
        if _segment_rect_distance(segments[i], tag_bbox_pt) <= source_snap_pt
    ]
    if not starts:
        return {"status": "WITHHELD_NO_LEADER_AT_TAG"}

    # Build only the local non-pipe leader graph. O(n²) is acceptable because the
    # max-path window reduces the candidate set to a small neighborhood.
    adjacency: dict[int, list[int]] = {i: [] for i in leader_indexes}
    for pos, i in enumerate(leader_indexes):
        for j in leader_indexes[pos + 1:]:
            if _segments_touch(segments[i], segments[j], leader_snap_pt):
                adjacency[i].append(j)
                adjacency[j].append(i)

    # Dijkstra state: path cost, hop count, current segment, full path.
    queue: list[tuple[float, int, int, tuple[int, ...]]] = []
    best_state: dict[tuple[int, int], float] = {}
    for i in starts:
        source_distance = _segment_rect_distance(segments[i], tag_bbox_pt)
        cost = source_distance + _segment_length(segments[i])
        if cost <= max_path_pt:
            heapq.heappush(queue, (cost, 1, i, (i,)))
            best_state[(i, 1)] = cost

    # Keep the best path per target component. Multiple adjacent target segments
    # from the same connected pipe component are not treated as ambiguity.
    terminal_by_component: dict[int, dict[str, Any]] = {}
    while queue:
        cost, hops, current, path = heapq.heappop(queue)
        if cost > max_path_pt + 1e-9:
            continue
        if cost > best_state.get((current, hops), math.inf) + 1e-9:
            continue

        leader = segments[current]
        for target_index in target_indexes:
            terminal_distance = _leader_to_target_distance(leader, segments[target_index])
            if terminal_distance > target_snap_pt:
                continue
            component_id = component_by_segment.get(target_index)
            if component_id is None:
                continue
            terminal_cost = cost + terminal_distance
            row = {
                "component_id": int(component_id),
                "target_segment_index": int(target_index),
                "terminal_distance_pt": float(terminal_distance),
                "path_cost_pt": float(terminal_cost),
                "leader_segment_indexes": list(path),
                "leader_hops": int(hops),
            }
            previous = terminal_by_component.get(int(component_id))
            if previous is None or (row["path_cost_pt"], row["target_segment_index"]) < (previous["path_cost_pt"], previous["target_segment_index"]):
                terminal_by_component[int(component_id)] = row

        if hops >= max_hops:
            continue
        for neighbor in adjacency.get(current, []):
            if neighbor in path:
                continue
            new_cost = cost + _segment_length(segments[neighbor])
            new_hops = hops + 1
            if new_cost > max_path_pt:
                continue
            state = (neighbor, new_hops)
            if new_cost + 1e-9 < best_state.get(state, math.inf):
                best_state[state] = new_cost
                heapq.heappush(queue, (new_cost, new_hops, neighbor, path + (neighbor,)))

    ranked = sorted(
        terminal_by_component.values(),
        key=lambda row: (row["path_cost_pt"], row["terminal_distance_pt"], row["target_segment_index"]),
    )
    if not ranked:
        return {
            "status": "WITHHELD_LEADER_DOES_NOT_REACH_EXPECTED_LAYER",
            "start_leader_segment_indexes": starts,
        }
    best = ranked[0]
    if len(ranked) > 1 and ranked[1]["path_cost_pt"] <= best["path_cost_pt"] + ambiguity_margin_pt:
        return {
            "status": "WITHHELD_AMBIGUOUS_LEADER_TARGETS",
            "best_candidates": ranked[:3],
            "start_leader_segment_indexes": starts,
        }
    return {
        "status": "ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER",
        **best,
        "start_leader_segment_indexes": starts,
        "runner_up_margin_pt": round(ranked[1]["path_cost_pt"] - best["path_cost_pt"], 3) if len(ranked) > 1 else None,
    }
