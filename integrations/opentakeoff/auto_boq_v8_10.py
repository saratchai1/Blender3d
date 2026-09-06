#!/usr/bin/env python3
"""v8.10 diagnostic: v8.9 + same-page corroborated rainwater sizing.

An unlabelled RL segment may receive a diameter only when its own primary drawing
contains both a standalone <diameter>RL label and an <same diameter>RFD+RL label,
with no conflicting RL class on that page. No new geometry/gap length is counted
and no pipe BOQ row is published.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

import auto_boq as base
import auto_boq_v8_9 as v89
import pipe_reconcile_v8 as reconcile
import rainwater_page_evidence_v8 as rainwater

SCHEMA=v89.SCHEMA


def extract(pdf_path:Path,profile_path:Path)->dict:
    result=v89.extract(pdf_path,profile_path)
    profile=json.loads(profile_path.read_text(encoding='utf-8'))
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_9'),None)
    if not diag:
        return result

    doc=fitz.open(pdf_path); guarded=base.GuardedPdf(doc,int(profile['source_page_max']))
    page_evidence=[]
    for page in diag.get('pages',[]):
        if page.get('contribution_policy')!='PRIMARY_PLAN_HORIZONTAL':
            continue
        page_no=int(page['page'])
        evidence=rainwater.corroborated_rl_class(guarded.page(page_no).get_text('text') or '')
        before=dict(page.get('diameter_coverage') or {})
        assignments,applied=rainwater.apply_to_assignments(page.get('diameter_assignments') or [],evidence)
        scales=page.get('effective_scale_candidates') or []
        scale_ratio=int(scales[0]) if len(scales)==1 else None
        rows,coverage=reconcile.aggregate_diameter_rows(assignments,scale_ratio)
        page['diameter_assignments_pre_rainwater']=page.get('diameter_assignments')
        page['diameter_rows_pre_rainwater']=page.get('diameter_rows')
        page['diameter_coverage_pre_rainwater']=before
        page['diameter_assignments']=assignments
        page['diameter_rows']=rows
        page['diameter_coverage']=coverage
        page['rainwater_page_evidence']={**evidence,'application':applied}
        page['diameter_publication_status']=(
            'PRIMARY_DIAMETER_GATE_CANDIDATE'
            if coverage.get('assigned_fraction',0.0)>=0.95 and scale_ratio
            else 'WITHHELD_DIAMETER_COVERAGE_OR_SCALE'
        )
        page_evidence.append({
            'page':page_no,'sheet':page.get('sheet'),
            'evidence_status':evidence.get('status'),
            'diameter_key':evidence.get('diameter_key'),
            **applied,
            'coverage_before':before.get('assigned_fraction'),
            'coverage_after':coverage.get('assigned_fraction'),
        })
    doc.close()

    cfg=profile.get('sanitary_pipe_network',{})
    diag['reconciliation']=reconcile.reconcile_pages(
        diag.get('pages',[]),
        min_primary_diameter_coverage=float(cfg.get('min_primary_diameter_coverage',0.95)),
    )
    diag['detector']='sanitary_pipe_network_v8_10'
    diag['status']='DIAGNOSTIC_CORROBORATED_RAINWATER_NO_PUBLISHED_PIPE_ROWS'
    diag['rainwater_corroboration_summary']=page_evidence
    diag['note_v8_10']=(
        'v8.10 may size otherwise-unlabelled RL geometry only when the same primary sheet independently prints both a standalone RL diameter and an RFD+RL diameter, '
        'both normalize to the same DN, and no conflicting rainwater diameter is present. This is diameter evidence only; no schematic/detail/gap length is added.'
    )
    return result


def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--pdf',type=Path,required=True); ap.add_argument('--profile',type=Path,required=True); ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); result=extract(args.pdf,args.profile); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_10'),None); pages=(diag or {}).get('pages') or []; rec=(diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_10_OK',json.dumps({
        'rows':len(result.get('rows',[])),
        'primary_coverage':{p.get('sheet'):(p.get('diameter_coverage') or {}).get('assigned_fraction') for p in pages if p.get('contribution_policy')=='PRIMARY_PLAN_HORIZONTAL'},
        'rainwater':(diag or {}).get('rainwater_corroboration_summary',[]),
        'horizontal_diameter_gate':rec.get('horizontal_diameter_gate'),
        'published_pipe_rows':sum(1 for r in result.get('rows',[]) if str(r.get('id','')).startswith('SAN-PIPE-')),
        'output':str(args.output),
    },ensure_ascii=False))


if __name__=='__main__':main()
