#!/usr/bin/env python3
"""v8.8 diagnostic: v8.7 + conflict-safe collinear endpoint gap bridging.

The bridge only classifies existing pipe segments across tiny drafting/fitting gaps.
It never adds gap length, never bridges endpoint-to-interior T junctions, and never
propagates through a bridge-connected group containing conflicting diameter/system
classes. Pipe publication remains withheld behind the existing release gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import auto_boq_v8_7 as v87
import collinear_gap_bridge_v8 as gap_bridge
import pipe_reconcile_v8 as reconcile

SCHEMA=v87.SCHEMA
_BASE_ASSIGN=reconcile.assign_segment_diameters
_LAST_EVENTS: list[dict[str,Any]]=[]


def _assign_with_collinear_bridges(
    segments:list[dict[str,Any]],
    components:list[dict[str,Any]],
    tags:list[dict[str,Any]],
    *,
    endpoint_snap_pt:float=1.5,
    tie_tolerance_pt:float=0.5,
)->list[dict[str,Any]]:
    global _LAST_EVENTS
    augmented,events=gap_bridge.bridge_diameter_tags(
        segments,components,tags,
        max_gap_pt=9.0,
        max_angle_diff_deg=5.0,
    )
    _LAST_EVENTS.extend(events)
    assignments=_BASE_ASSIGN(
        segments,components,augmented,
        endpoint_snap_pt=endpoint_snap_pt,
        tie_tolerance_pt=tie_tolerance_pt,
    )
    bridged_components={int(e['component_id']) for e in events if e.get('status')=='ACCEPTED_COLLINEAR_GAP_DIAMETER_SEED'}
    for row in assignments:
        if int(row.get('component_id',-1)) in bridged_components:
            row['diameter_evidence_role']='COLLINEAR_ENDPOINT_GAP_BRIDGE'
    return assignments


def extract(pdf_path:Path,profile_path:Path)->dict:
    global _LAST_EVENTS
    _LAST_EVENTS=[]
    original=reconcile.assign_segment_diameters
    reconcile.assign_segment_diameters=_assign_with_collinear_bridges
    try:
        result=v87.extract(pdf_path,profile_path)
    finally:
        reconcile.assign_segment_diameters=original
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_7'),None)
    if diag:
        diag['detector']='sanitary_pipe_network_v8_8'
        diag['status']='DIAGNOSTIC_COLLINEAR_GAP_RECONCILIATION_NO_PUBLISHED_PIPE_ROWS'
        accepted=[e for e in _LAST_EVENTS if e.get('status')=='ACCEPTED_COLLINEAR_GAP_DIAMETER_SEED']
        withheld=[e for e in _LAST_EVENTS if e.get('status')=='WITHHELD_BRIDGE_GROUP_CONFLICTING_DIAMETERS']
        diag['collinear_gap_bridge']={
            'max_gap_pt':9.0,
            'max_angle_diff_deg':5.0,
            'endpoint_to_endpoint_only':True,
            'gap_length_added':False,
            'accepted_seed_count':len(accepted),
            'accepted_component_length_pt':round(sum(float(e.get('component_length_pt',0.0)) for e in accepted),3),
            'conflicting_group_count':len(withheld),
            'accepted_events':accepted,
            'withheld_conflicting_groups':withheld,
        }
        diag['note_v8_8']=(
            'v8.8 may transfer a diameter across <=9 pt same-layer collinear endpoint gaps only when every seed in the entire bridge-connected group agrees on system and diameter. '
            'Any DN/system conflict withholds the group. No synthetic gap length is added and all v8.7 parser, leader, detail-transfer and cross-view non-additive guards remain active.'
        )
    return result


def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--pdf',type=Path,required=True); ap.add_argument('--profile',type=Path,required=True); ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); result=extract(args.pdf,args.profile); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_8'),None); pages=(diag or {}).get('pages') or []; rec=(diag or {}).get('reconciliation') or {}; bridge=(diag or {}).get('collinear_gap_bridge') or {}
    print('AUTO_BOQ_V8_8_OK',json.dumps({
        'rows':len(result.get('rows',[])),
        'primary_coverage':{p.get('sheet'):(p.get('diameter_coverage') or {}).get('assigned_fraction') for p in pages if p.get('contribution_policy')=='PRIMARY_PLAN_HORIZONTAL'},
        'accepted_bridge_seeds':bridge.get('accepted_seed_count',0),
        'accepted_bridge_length_pt':bridge.get('accepted_component_length_pt',0),
        'conflicting_bridge_groups':bridge.get('conflicting_group_count',0),
        'horizontal_diameter_gate':rec.get('horizontal_diameter_gate'),
        'published_pipe_rows':sum(1 for r in result.get('rows',[]) if str(r.get('id','')).startswith('SAN-PIPE-')),
        'output':str(args.output),
    },ensure_ascii=False))


if __name__=='__main__':main()
