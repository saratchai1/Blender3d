#!/usr/bin/env python3
"""v8.9 diagnostic: v8.7 + reconstructed dashed-network diameter partition.

Tiny same-layer collinear endpoint gaps are treated as drafting gaps for evidence
routing only. Single-class groups inherit that class; multi-diameter groups are
partitioned by nearest seed only when all classes belong to the same system.
Distance ties and multi-system groups remain withheld. No gap length is added and
no SAN-PIPE rows are published.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import auto_boq_v8_7 as v87
import dashed_network_partition_v8 as dashed
import pipe_reconcile_v8 as reconcile

SCHEMA=v87.SCHEMA
_BASE_ASSIGN=reconcile.assign_segment_diameters
_LAST_EVENTS:list[dict[str,Any]]=[]


def _assign_with_dashed_partition(
    segments:list[dict[str,Any]],components:list[dict[str,Any]],tags:list[dict[str,Any]],*,
    endpoint_snap_pt:float=1.5,tie_tolerance_pt:float=0.5,
)->list[dict[str,Any]]:
    global _LAST_EVENTS
    augmented,events=dashed.partition_diameter_tags(
        segments,components,tags,max_gap_pt=9.0,max_angle_diff_deg=5.0,tie_tolerance_pt=tie_tolerance_pt,
    )
    _LAST_EVENTS.extend(events)
    assignments=_BASE_ASSIGN(
        segments,components,augmented,endpoint_snap_pt=endpoint_snap_pt,tie_tolerance_pt=tie_tolerance_pt,
    )
    partitioned={int(e['component_id']) for e in events if e.get('status')=='ACCEPTED_DASHED_NETWORK_PARTITION_SEED'}
    bridged={int(e['component_id']) for e in events if e.get('status')=='ACCEPTED_COLLINEAR_GAP_DIAMETER_SEED'}
    for row in assignments:
        cid=int(row.get('component_id',-1))
        if cid in partitioned:
            row['diameter_evidence_role']='DASHED_NETWORK_NEAREST_DIAMETER_SEED'
        elif cid in bridged:
            row['diameter_evidence_role']='COLLINEAR_ENDPOINT_GAP_BRIDGE'
    return assignments


def _dedupe_events(events:list[dict[str,Any]])->list[dict[str,Any]]:
    seen=set(); out=[]
    for e in events:
        key=json.dumps(e,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        if key in seen: continue
        seen.add(key); out.append(e)
    return out


def extract(pdf_path:Path,profile_path:Path)->dict:
    global _LAST_EVENTS
    _LAST_EVENTS=[]
    original=reconcile.assign_segment_diameters
    reconcile.assign_segment_diameters=_assign_with_dashed_partition
    try:
        result=v87.extract(pdf_path,profile_path)
    finally:
        reconcile.assign_segment_diameters=original
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_7'),None)
    if diag:
        diag['detector']='sanitary_pipe_network_v8_9'
        diag['status']='DIAGNOSTIC_DASHED_NETWORK_PARTITION_NO_PUBLISHED_PIPE_ROWS'
        events=_dedupe_events(_LAST_EVENTS)
        accepted_partition=[e for e in events if e.get('status')=='ACCEPTED_DASHED_NETWORK_PARTITION_SEED']
        accepted_single=[e for e in events if e.get('status')=='ACCEPTED_COLLINEAR_GAP_DIAMETER_SEED']
        ties=[e for e in events if e.get('status')=='WITHHELD_DASH_PARTITION_DISTANCE_TIE']
        multisystem=[e for e in events if e.get('status')=='WITHHELD_DASH_PARTITION_MULTIPLE_SYSTEMS']
        summaries=[e for e in events if e.get('status')=='DASHED_NETWORK_PARTITION_SUMMARY']
        diag['dashed_network_partition']={
            'max_gap_pt':9.0,'max_angle_diff_deg':5.0,'endpoint_to_endpoint_only':True,
            'gap_length_added':False,'same_system_required_for_multi_size_partition':True,
            'accepted_partition_seed_count':len(accepted_partition),
            'accepted_single_class_bridge_seed_count':len(accepted_single),
            'partitioned_component_length_pt':round(sum(float(e.get('component_length_pt',0.0)) for e in accepted_partition),3),
            'single_class_bridge_component_length_pt':round(sum(float(e.get('component_length_pt',0.0)) for e in accepted_single),3),
            'distance_tie_count':len(ties),'multiple_system_group_count':len(multisystem),
            'partition_summaries':summaries,'distance_ties':ties,'multiple_system_groups':multisystem,
        }
        diag['note_v8_9']=(
            'v8.9 reconstructs dashed CAD pipe topology across <=9 pt collinear endpoint gaps. When one reconstructed network contains multiple diameters of the same system, '
            'unseeded components are assigned only to the nearest explicit/detail-derived diameter source using network distance; exact distance ties remain withheld. '
            'Different systems are never partitioned together and no synthetic gap length contributes to quantity.'
        )
    return result


def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--pdf',type=Path,required=True); ap.add_argument('--profile',type=Path,required=True); ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); result=extract(args.pdf,args.profile); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_9'),None); pages=(diag or {}).get('pages') or []; rec=(diag or {}).get('reconciliation') or {}; part=(diag or {}).get('dashed_network_partition') or {}
    print('AUTO_BOQ_V8_9_OK',json.dumps({
        'rows':len(result.get('rows',[])),
        'primary_coverage':{p.get('sheet'):(p.get('diameter_coverage') or {}).get('assigned_fraction') for p in pages if p.get('contribution_policy')=='PRIMARY_PLAN_HORIZONTAL'},
        'partition_seeds':part.get('accepted_partition_seed_count',0),'single_class_bridge_seeds':part.get('accepted_single_class_bridge_seed_count',0),
        'distance_ties':part.get('distance_tie_count',0),'multi_system_groups':part.get('multiple_system_group_count',0),
        'horizontal_diameter_gate':rec.get('horizontal_diameter_gate'),
        'published_pipe_rows':sum(1 for r in result.get('rows',[]) if str(r.get('id','')).startswith('SAN-PIPE-')),
        'output':str(args.output),
    },ensure_ascii=False))


if __name__=='__main__':main()
