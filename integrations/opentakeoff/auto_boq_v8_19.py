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
import auto_boq_v8 as v8
import auto_boq_v8_15 as v815
import equipment_valve_corroboration_v8 as equipment_corroboration
import layer_topology_v8 as layer_topology
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


def _attach_pipe_segment_geometry(pdf_path: Path, profile: dict, diag: dict) -> None:
    """Attach exact source-PDF endpoints for only the segments that can support rows.

    This is audit evidence, not a second takeoff calculation. Segment indexes are
    reconstructed with the same v8.6 semantic-layer topology used by the validated
    detector and are accepted only when segment/component counts match the stored
    diagnostic exactly. Synthetic connector gaps are never emitted as geometry.
    """
    cfg=profile.get('sanitary_pipe_network') or {}
    specs={int(s['page']):s for s in cfg.get('page_specs') or []}
    min_segment_pt=float(cfg.get('min_segment_pt',3.0))
    max_stroke_width_pt=float(cfg.get('max_stroke_width_pt',3.0))
    endpoint_snap_pt=float(cfg.get('endpoint_snap_pt',1.5))
    vertical=diag.get('vertical_level_bounded_reconciliation') or {}
    vertical_indexes:set[int]=set()
    for key in ('candidate_runs','direct_branch_promoted_runs','valve_leader_promoted_runs','roof_extended_runs'):
        for run in vertical.get(key) or []:
            vertical_indexes.update(int(i) for i in run.get('segment_indexes') or [])

    doc=fitz.open(pdf_path)
    try:
        guarded=base.GuardedPdf(doc,int(profile['source_page_max']))
        total_emitted=0
        for page_diag in diag.get('pages') or []:
            page_no=int(page_diag['page'])
            spec=specs.get(page_no,{})
            segments=v8.line_segments(
                guarded.page(page_no),
                bounds=spec.get('bounds_pt'),
                min_len_pt=min_segment_pt,
                max_width_pt=max_stroke_width_pt,
            )
            components,component_by_segment=layer_topology.layer_components(
                segments,
                snap_pt=endpoint_snap_pt,
            )
            expected_segments=int(page_diag.get('segment_count',len(segments)))
            expected_components=int(page_diag.get('component_count',len(components)))
            if len(segments)!=expected_segments or len(components)!=expected_components:
                raise ValueError(
                    f'pipe segment audit reconstruction mismatch p.{page_no}: '
                    f'segments {len(segments)} != {expected_segments} or '
                    f'components {len(components)} != {expected_components}'
                )

            needed:set[int]=set()
            for assignment in page_diag.get('diameter_assignments') or []:
                classes=assignment.get('classes') or []
                if len(classes)==1 and not str(assignment.get('status') or '').startswith('WITHHELD'):
                    needed.add(int(assignment['segment_index']))
            if page_no==57:
                needed.update(vertical_indexes)

            geometry=[]
            for index in sorted(needed):
                if index<0 or index>=len(segments):
                    raise ValueError(f'pipe segment audit index out of range p.{page_no}: {index}')
                segment=segments[index]
                geometry.append({
                    'segment_index':index,
                    'component_id':component_by_segment.get(index),
                    'a_pt':[round(float(segment['a'][0]),3),round(float(segment['a'][1]),3)],
                    'b_pt':[round(float(segment['b'][0]),3),round(float(segment['b'][1]),3)],
                    'length_pt':round(float(segment['length_pt']),3),
                    'layer':str(segment.get('layer') or ''),
                    'path_index':int(segment.get('path_index') or 0),
                    'source':'PDF_VECTOR_OPEN_STRAIGHT_SEGMENT',
                })
            page_diag['segment_geometry_status']='EXACT_RECONSTRUCTION_MATCH'
            page_diag['segment_geometry']=geometry
            page_diag['segment_geometry_count']=len(geometry)
            total_emitted+=len(geometry)
        diag['segment_geometry_evidence']={
            'status':'EXACT_RECONSTRUCTION_MATCH',
            'source':'SOURCE_PDF_VECTOR_GEOMETRY_ONLY',
            'topology':'SEMANTIC_LAYER_ENDPOINT_T_JUNCTION',
            'synthetic_gap_geometry_emitted':False,
            'emitted_segment_count':total_emitted,
            'purpose':'AUDIT_OVERLAY_ONLY_QUANTITY_UNCHANGED',
        }
    finally:
        doc.close()


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
    _attach_pipe_segment_geometry(pdf_path,profile,diag)

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
        'segment_geometry_status':((diag or {}).get('segment_geometry_evidence') or {}).get('status'),
        'segment_geometry_count':((diag or {}).get('segment_geometry_evidence') or {}).get('emitted_segment_count'),
        'output':str(args.output),
    },ensure_ascii=False))


if __name__=='__main__':main()
