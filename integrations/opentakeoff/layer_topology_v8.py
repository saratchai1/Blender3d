from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _distance_point_segment(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    wx, wy = point[0] - a[0], point[1] - a[1]
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    px, py = a[0] + t * vx, a[1] + t * vy
    return math.hypot(point[0] - px, point[1] - py)


def layer_components(
    segments: list[dict[str, Any]],
    snap_pt: float = 1.5,
) -> tuple[list[dict[str, Any]], dict[int, int]]:
    """Group open vector segments by semantic CAD layer and geometric topology.

    Unlike v8's style_components, width/color/dash changes do not break a physical
    network. Connectivity remains conservative: an endpoint landing on another
    same-layer segment forms a junction, but an interior/interior X crossing does
    not connect. Different CAD layers can never merge.
    """
    by_layer: dict[str, list[int]] = defaultdict(list)
    for index, segment in enumerate(segments):
        by_layer[str(segment.get('layer') or '')].append(index)

    components: list[dict[str, Any]] = []
    component_by_segment: dict[int, int] = {}
    for layer, ids in by_layer.items():
        parent = {i: i for i in ids}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        cell = max(12.0, snap_pt * 6.0)
        segment_grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        for i in ids:
            segment = segments[i]
            x0 = min(segment['a'][0], segment['b'][0]) - snap_pt
            y0 = min(segment['a'][1], segment['b'][1]) - snap_pt
            x1 = max(segment['a'][0], segment['b'][0]) + snap_pt
            y1 = max(segment['a'][1], segment['b'][1]) + snap_pt
            for gx in range(math.floor(x0 / cell), math.floor(x1 / cell) + 1):
                for gy in range(math.floor(y0 / cell), math.floor(y1 / cell) + 1):
                    segment_grid[(gx, gy)].append(i)

        for i in ids:
            for endpoint in (segments[i]['a'], segments[i]['b']):
                key = (math.floor(endpoint[0] / cell), math.floor(endpoint[1] / cell))
                candidates: set[int] = set()
                for gx in range(key[0] - 1, key[0] + 2):
                    for gy in range(key[1] - 1, key[1] + 2):
                        candidates.update(segment_grid.get((gx, gy), []))
                for j in candidates:
                    if j == i:
                        continue
                    if _distance_point_segment(endpoint, segments[j]['a'], segments[j]['b']) <= snap_pt:
                        union(i, j)

        groups: dict[int, list[int]] = defaultdict(list)
        for i in ids:
            groups[find(i)].append(i)
        for members in groups.values():
            component_id = len(components)
            for i in members:
                component_by_segment[i] = component_id
            xs: list[float] = []
            ys: list[float] = []
            style_hist: dict[str, int] = defaultdict(int)
            for i in members:
                segment = segments[i]
                for point in (segment['a'], segment['b']):
                    xs.append(float(point[0])); ys.append(float(point[1]))
                style_key = repr((
                    round(float(segment.get('width_pt') or 0.0), 3),
                    segment.get('color'),
                    str(segment.get('dash') or 'solid'),
                ))
                style_hist[style_key] += 1
            components.append({
                'id': component_id,
                'layer': layer,
                'style': {
                    'layer': layer,
                    'topology_basis': 'SEMANTIC_LAYER_GEOMETRY_ONLY',
                    'style_variant_count': len(style_hist),
                },
                'segment_indexes': sorted(members),
                'segment_count': len(members),
                'length_pt': sum(float(segments[i]['length_pt']) for i in members),
                'bbox_pt': [min(xs), min(ys), max(xs), max(ys)],
            })
    return components, component_by_segment
