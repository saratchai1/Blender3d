#!/usr/bin/env python3
"""v8.19: cross-sheet-corroborated, fail-closed sanitary pipe publication.

The 1.228 m tank-side CW branch is published as DN15 only when two independent
source-drawing signals agree: the SN-04 BALL VALVE Ø1/2 leader must land on the
exact unresolved run, and SN-05 must explicitly print FLOAT VALVE Ø1/2 in the
tank/equipment plan. The nearby Ø3/4 CW main is audit-only and is never borrowed
to size this branch.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

import auto_boq as base
import auto_boq_v8_15 as v815
import equipment_valve_corroboration_v8 as equipment_corroboration
import pipe_publish_v8 as publish
import pipe_release_reconcile_v8 as release
import probe_cw_valve_leaders_v8 as valve_probe
import vertical_valve_leader_reconcile_v8 as valve_reconcile

SCHEMA = v815.SCHEMA


def _attach_cross_sheet_provenance(vertical: dict, corroboration: dict) -> dict:
    if corroboration.get('status') != 'CORROBORATED_EQUIPMENT_VALVE_CLASS':
        return vertical
    system=str(corroboration.get('system') or '')
    diameter_key=str(corroboration.get('diameter_key') or '')
    pages=[int(p) for p in corroboration.get('source_pages') or []]
    rows=[]
    for raw in vertical.get('candidate_rows') or []:
        row=dict(raw)
        if str(row.get('system') or '')==system and str(row.get('diameter_key') or '')==diameter_key:
            sources=list(row.get('sources') or [])
            role='SN-04_EXPLICIT_VALVE_LEADER_PLUS_SN-05_FLOAT_VALVE'
            if role not in sources:
                sources.append(role)
            source_pages=sorted(set(int(p) for p in (row.get('source_pages') or []) + pages))
            row['sources']=sources
            row['source_pages']=source_pages
            row['cross_sheet_equipment_evidence_id']=corroboration.get('evidence_id')
        rows.append(row)
    promoted=[]
    for raw in vertical.get('valve_leader_promoted_runs') or []:
        row=dict(raw)
        if str(row.get('system') or '')==system and str(row.get('diameter_key') or '')==diameter_key:
            row['cross_sheet_equipment_corroboration']=corroboration
        promoted.append(row)
    return {
        **vertical,
        'candidate_rows':rows,
        'valve_leader_promoted_runs':promoted,
        'equipment_valve_corroboration':corroboration,
    }


def extract(
    pdf_path: Path,
    profile_path: Path,
    roof_evidence_path: Path,
    equipment_evidence_path: Path,
) -> dict:
    result=v815.extract(pdf_path,profile_path,roof_evidence_path)
    roof_evidence=json.loads(roof_evidence_path.read_text(encoding='utf-8'))
    equipment_evidence=json.loads(equipment_evidence_path.read_text(encoding='utf-8'))
    profile=json.loads(profile_path.read_text(encoding='utf-8'))
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_15'),None)
    if not diag:
        return result

    probe=valve_probe.probe(pdf_path,profile_path)
    doc=fitz.open(pdf_path)
    try:
        guarded=base.GuardedPdf(doc,int(profile['source_page_max']))
        primary_text=guarded.page(int(equipment_evidence['source_page'])).get_text('text') or ''
    finally:
        doc.close()
    corroboration=equipment_corroboration.corroborate_equipment_valve(
        primary_text,
        probe,
        equipment_evidence,
    )

    vertical=diag.get('vertical_level_bounded_reconciliation') or {}
    if corroboration.get('status')=='CORROBORATED_EQUIPMENT_VALVE_CLASS':
        vertical=valve_reconcile.apply_valve_leader_evidence(
            vertical,
            probe,
            allowed_system='CW',
            min_span_m=float(equipment_evidence.get('min_vertical_span_m',0.5)),
        )
        vertical=_attach_cross_sheet_provenance(vertical,corroboration)
    else:
        vertical={**vertical,'equipment_valve_corroboration':corroboration}

    # Fail closed if the corroborated run did not become exactly one DN15 branch.
    if corroboration.get('status')=='CORROBORATED_EQUIPMENT_VALVE_CLASS':
        expected_segments=sorted(int(i) for i in equipment_evidence.get('schematic_segment_indexes') or [])
        promoted=[
            r for r in vertical.get('valve_leader_promoted_runs') or []
            if sorted(int(i) for i in r.get('segment_indexes') or [])==expected_segments
        ]
        if not (
            len(promoted)==1
            and promoted[0].get('system')=='CW'
            and promoted[0].get('diameter_key')==equipment_evidence.get('diameter_key')
            and float(equipment_evidence.get('min_vertical_span_m',0.5)) <= float(promoted[0].get('vertical_span_m') or 0.0) <= float(equipment_evidence.get('max_vertical_span_m',2.0))
        ):
            vertical={
                **(diag.get('vertical_level_bounded_reconciliation') or {}),
                'equipment_valve_corroboration':{
                    **corroboration,
                    'status':'WITHHELD_POST_RECONCILIATION_MISMATCH',
                },
            }

    final=release.build_pipe_release_candidate(
        diag.get('reconciliation') or {},
        vertical,
        roof_source_page=int(roof_evidence['source_page']),
        max_excludable_cw_offset_m=0.5,
    )
    diag['vertical_level_bounded_reconciliation']=vertical
    diag['cw_valve_leader_evidence']=probe
    diag['equipment_valve_corroboration']=corroboration
    diag['pipe_release_candidate']=final
    diag['detector']='sanitary_pipe_network_v8_19'
    diag['status']=(
        'VALIDATED_CROSS_SHEET_VALVE_PIPE_RELEASE_READY'
        if final.get('status')=='PASS_VALIDATED_PIPE_RELEASE_CANDIDATE'
        else 'WITHHELD_CROSS_SHEET_VALVE_PIPE_RELEASE_BLOCKERS'
    )
    diag['reconciliation']['full_pipe_boq_publication_status']=final.get('status')
    diag['note_v8_19']=(
        'v8.19 requires SN-04 BALL VALVE Ø1/2 leader evidence and SN-05 FLOAT VALVE Ø1/2 equipment-plan evidence to agree before the 1.228 m tank-side CW run may be classified DN15. '
        'The nearby Ø3/4 CW main is explicitly audit-only and cannot size the vertical valve branch. The branch length remains the SN-04 calibrated span; no plan, leader, gap, schematic-offset or detail length is added. '
        'All previous horizontal, roof, non-additive, residual-run and reference-page-fence guards remain active.'
    )

    published=publish.publish_validated_pipe_rows(result,final)
    pdiag=next((d for d in published.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_19'),None)
    if pdiag:
        pdiag['status']='PUBLISHED_VALIDATED_CROSS_SHEET_SANITARY_PIPE_ROWS'
        pdiag['reconciliation']['full_pipe_boq_publication_status']='PUBLISHED_VALIDATED_PIPE_ROWS'
    return published


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--pdf',type=Path,required=True)
    ap.add_argument('--profile',type=Path,required=True)
    ap.add_argument('--roof-evidence',type=Path,required=True)
    ap.add_argument('--equipment-evidence',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    result=extract(args.pdf,args.profile,args.roof_evidence,args.equipment_evidence)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    pipes=[r for r in result.get('rows',[]) if str(r.get('id','')).startswith('SAN-PIPE-')]
    diag=next((d for d in result.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_19'),None)
    print('AUTO_BOQ_V8_19_OK',json.dumps({
        'rows':len(result.get('rows',[])),
        'corroboration_status':((diag or {}).get('equipment_valve_corroboration') or {}).get('status'),
        'release_status':((diag or {}).get('pipe_release_candidate') or {}).get('status'),
        'release_blockers':((diag or {}).get('pipe_release_candidate') or {}).get('release_blocker_count'),
        'published_pipe_rows':len(pipes),
        'published_pipe_total_m':round(sum(float(r.get('quantity') or 0.0) for r in pipes),3),
        'output':str(args.output),
    },ensure_ascii=False))


if __name__=='__main__':main()
