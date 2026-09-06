from __future__ import annotations

import math
from typing import Any

import auto_boq_v8 as v8
import detail_view_transfer_v8 as base

_BASE_PROBE = base.probe_detail_transfer


def _distance(a: tuple[float,float], b: tuple[float,float]) -> float:
    return math.hypot(b[0]-a[0], b[1]-a[1])


def _point_segment(p: tuple[float,float], a: tuple[float,float], b: tuple[float,float]) -> float:
    return v8.distance_point_segment(p,a,b)


def _segment_gap(a0,a1,b0,b1) -> float:
    return min(
        _point_segment(a0,b0,b1), _point_segment(a1,b0,b1),
        _point_segment(b0,a0,a1), _point_segment(b1,a0,a1),
    )


def probe_detail_transfer(
    detail_page: Any,
    target_page: Any,
    spec: dict[str,Any],
    *,
    min_segment_pt: float,
    max_stroke_width_pt: float,
    endpoint_snap_pt: float,
    tag_snap_max_pt: float,
    render_scale: float = 1.5,
) -> dict[str,Any]:
    """Base affine transfer plus endpoint fallback for short drafting stubs only."""
    result = _BASE_PROBE(
        detail_page,target_page,spec,
        min_segment_pt=min_segment_pt,
        max_stroke_width_pt=max_stroke_width_pt,
        endpoint_snap_pt=endpoint_snap_pt,
        tag_snap_max_pt=tag_snap_max_pt,
        render_scale=render_scale,
    )
    if result.get('status') != 'DIAGNOSTIC_TRANSFER_PROBED':
        return result

    target_segments = v8.line_segments(target_page,None,min_segment_pt,max_stroke_width_pt)
    _, component_by_segment = v8.style_components(target_segments,endpoint_snap_pt)
    max_source_len = float(spec.get('short_branch_source_max_pt',6.0))
    max_target_len = float(spec.get('short_branch_target_max_pt',12.0))
    max_gap = float(spec.get('short_branch_endpoint_gap_pt',12.0))
    uniqueness = float(spec.get('short_branch_uniqueness_margin_pt',4.0))
    recovered = 0

    for row in result.get('transfer_candidates',[]):
        if row.get('status') != 'WITHHELD_NO_TARGET_SEGMENT_MATCH':
            continue
        predicted = row.get('predicted_target_segment_pt') or []
        if len(predicted) != 4:
            continue
        a=(float(predicted[0]),float(predicted[1])); b=(float(predicted[2]),float(predicted[3]))
        source_len=_distance(a,b)
        if source_len > max_source_len:
            row['short_branch_fallback_status']='WITHHELD_SOURCE_RUN_TOO_LONG'
            continue
        expected_layer=str(row.get('expected_layer') or '')
        ranked=[]
        for index,target in enumerate(target_segments):
            if expected_layer and str(target.get('layer') or '') != expected_layer:
                continue
            target_len=float(target.get('length_pt') or 0.0)
            if target_len > max_target_len:
                continue
            gap=_segment_gap(a,b,target['a'],target['b'])
            if gap <= max_gap:
                ranked.append((gap,index,target_len))
        ranked.sort(key=lambda x:(x[0],x[2],x[1]))
        row['short_branch_candidate_count']=len(ranked)
        if not ranked:
            row['short_branch_fallback_status']='WITHHELD_NO_SHORT_TARGET_NEAR_ENDPOINT'
            continue
        best_gap,best_index,best_len=ranked[0]
        if len(ranked)>1 and ranked[1][0] <= best_gap + uniqueness:
            row['short_branch_fallback_status']='WITHHELD_AMBIGUOUS_SHORT_TARGETS'
            row['short_branch_best_gap_pt']=round(best_gap,3)
            row['short_branch_second_gap_pt']=round(ranked[1][0],3)
            continue
        row.update({
            'target_segment_index':int(best_index),
            'target_component_id':component_by_segment.get(best_index),
            'distance_pt':round(best_gap,3),
            'angle_diff_deg':None,
            'target_layer':target_segments[best_index].get('layer',''),
            'status':'DETAIL_TRANSFER_CANDIDATE',
            'transfer_basis':'SHORT_BRANCH_UNIQUE_ENDPOINT_GAP',
            'short_branch_source_length_pt':round(source_len,3),
            'short_branch_target_length_pt':round(best_len,3),
            'short_branch_best_gap_pt':round(best_gap,3),
            'short_branch_fallback_status':'RECOVERED_UNIQUE_SHORT_BRANCH',
        })
        recovered += 1

    result['short_branch_recovered_count']=recovered
    result['candidate_count']=sum(1 for row in result.get('transfer_candidates',[]) if row.get('status')=='DETAIL_TRANSFER_CANDIDATE')
    result['ambiguous_count']=sum(1 for row in result.get('transfer_candidates',[]) if 'AMBIGUOUS' in str(row.get('status','')) or 'AMBIGUOUS' in str(row.get('short_branch_fallback_status','')))
    result['unmatched_count']=sum(1 for row in result.get('transfer_candidates',[]) if row.get('status')=='WITHHELD_NO_TARGET_SEGMENT_MATCH')
    return result
