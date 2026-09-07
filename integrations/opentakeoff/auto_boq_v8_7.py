#!/usr/bin/env python3
"""v8.7 diagnostic: v8.6 safety baseline + unique short-branch endpoint transfer.

Only transformed source runs <=6 pt may use the orientation-free fallback, and
only onto target stubs <=12 pt on the expected CAD layer with <=12 pt endpoint
gap and >=4 pt uniqueness margin. No detail length is added and no pipe row is
published.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import auto_boq_v8_6 as v86
import detail_short_branch_v8 as short_branch
import detail_view_transfer_v8 as detail_transfer

SCHEMA=v86.SCHEMA


def extract(pdf_path:Path,profile_path:Path)->dict:
    original=detail_transfer.probe_detail_transfer
    detail_transfer.probe_detail_transfer=short_branch.probe_detail_transfer
    try:
        result=v86.extract(pdf_path,profile_path)
    finally:
        detail_transfer.probe_detail_transfer=original
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_6'),None)
    if diag:
        diag['detector']='sanitary_pipe_network_v8_7'
        diag['status']='DIAGNOSTIC_SHORT_BRANCH_RECONCILIATION_NO_PUBLISHED_PIPE_ROWS'
        diag['short_branch_policy']={
            'source_max_pt':6.0,'target_max_pt':12.0,'endpoint_gap_max_pt':12.0,
            'uniqueness_margin_pt':4.0,'expected_layer_required':True,
            'long_run_orientation_free_transfer':'FORBIDDEN',
        }
        diag['note_v8_7']=(
            'v8.7 adds an orientation-free fallback only for short detail branches where primary drafting retains a short perpendicular stub. '
            'Long runs, non-unique targets, wrong layers and larger endpoint gaps remain withheld. All v8.6 strict-parser, leader and non-additive guards remain active.'
        )
    return result


def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--pdf',type=Path,required=True); ap.add_argument('--profile',type=Path,required=True); ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); result=extract(args.pdf,args.profile); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_7'),None); pages=(diag or {}).get('pages') or []; rec=(diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_7_OK',json.dumps({
        'rows':len(result.get('rows',[])),
        'primary_coverage':{p.get('sheet'):(p.get('diameter_coverage') or {}).get('assigned_fraction') for p in pages if p.get('contribution_policy')=='PRIMARY_PLAN_HORIZONTAL'},
        'short_branch_recovered':{p.get('id'):p.get('short_branch_recovered_count',0) for p in (diag or {}).get('detail_view_reconciliation',[])},
        'horizontal_diameter_gate':rec.get('horizontal_diameter_gate'),
        'published_pipe_rows':sum(1 for r in result.get('rows',[]) if str(r.get('id','')).startswith('SAN-PIPE-')),
        'output':str(args.output),
    },ensure_ascii=False))


if __name__=='__main__':main()
