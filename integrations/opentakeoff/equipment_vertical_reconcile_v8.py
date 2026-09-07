from __future__ import annotations

from typing import Any


def apply_equipment_vertical_evidence(
    bounded: dict[str, Any],
    schematic_analysis: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    if not evidence.get('generation_allowed') or evidence.get('reference_used'):
        return {**bounded, 'equipment_vertical_status':'WITHHELD_INVALID_SOURCE_EVIDENCE'}
    source_page=int(evidence.get('source_page',0) or 0)
    source_page_max=int(evidence.get('source_page_max',0) or 0)
    schematic_page=int(evidence.get('corroborates_schematic_page',0) or 0)
    if not (1 <= source_page <= source_page_max and 1 <= schematic_page <= source_page_max):
        return {**bounded, 'equipment_vertical_status':'WITHHELD_SOURCE_PAGE_FENCE'}

    expected_segments=sorted(int(i) for i in evidence.get('schematic_segment_indexes') or [])
    system=str(evidence.get('system') or '')
    diameter_key=str(evidence.get('diameter_key') or '')
    assignments={int(r['segment_index']):r for r in schematic_analysis.get('diameter_assignments') or []}

    matched=None
    kept=[]
    for run in bounded.get('withheld_runs') or []:
        if (
            sorted(int(i) for i in run.get('segment_indexes') or []) == expected_segments
            and str(run.get('system') or '') == system
            and str(run.get('diameter_key') or '') == diameter_key
        ):
            if matched is not None:
                return {**bounded, 'equipment_vertical_status':'WITHHELD_AMBIGUOUS_MATCH'}
            matched=run
        else:
            kept.append(run)
    if matched is None:
        return {**bounded, 'equipment_vertical_status':'WITHHELD_TARGET_RUN_NOT_FOUND'}

    span=float(matched.get('vertical_span_m') or 0.0)
    min_span=float(evidence.get('min_vertical_span_m',0.5))
    max_span=float(evidence.get('max_vertical_span_m',2.0))
    tol=float(evidence.get('terminal_extension_allowed_m',0.05))
    if not (min_span <= span <= max_span):
        return {**bounded, 'equipment_vertical_status':'WITHHELD_SPAN_OUTSIDE_EVIDENCE_RANGE'}
    if float(matched.get('terminal_extension_above_m') or 0.0) > tol or float(matched.get('terminal_extension_below_m') or 0.0) > tol:
        return {**bounded, 'equipment_vertical_status':'WITHHELD_TERMINAL_EXTENSION'}

    explicit=0
    validated=0
    assignment_audit=[]
    for idx in expected_segments:
        row=assignments.get(idx)
        if not row or str(row.get('status') or '').startswith('WITHHELD'):
            return {**bounded, 'equipment_vertical_status':'WITHHELD_SEGMENT_ASSIGNMENT_MISSING'}
        classes=row.get('classes') or []
        if len(classes)!=1:
            return {**bounded, 'equipment_vertical_status':'WITHHELD_SEGMENT_CLASS_AMBIGUITY'}
        cls=classes[0]
        if str(cls.get('system') or '')!=system or str(cls.get('diameter_key') or '')!=diameter_key:
            return {**bounded, 'equipment_vertical_status':'WITHHELD_SEGMENT_CLASS_CONFLICT'}
        validated += 1
        if row.get('status')=='EXPLICIT_TAG_SEED':
            explicit += 1
        assignment_audit.append({'segment_index':idx,'status':row.get('status'),'classes':classes})
    fraction=explicit/validated if validated else 0.0
    required=float(evidence.get('min_explicit_seed_fraction',0.8))
    if fraction < required:
        return {**bounded, 'equipment_vertical_status':'WITHHELD_EXPLICIT_SEED_FRACTION','explicit_seed_fraction':round(fraction,4)}

    promoted=dict(matched)
    promoted.update({
        'classification_status':'CANDIDATE_PRIMARY_PLAN_CORROBORATED_EQUIPMENT_VERTICAL_BRANCH',
        'vertical_length_m_candidate':round(span,3),
        'equipment_evidence_id':evidence.get('evidence_id'),
        'equipment_source_page':source_page,
        'equipment_plan_label':evidence.get('plan_label'),
        'explicit_seed_fraction':round(fraction,4),
        'segment_assignment_audit':assignment_audit,
    })
    candidate_runs=list(bounded.get('candidate_runs') or [])+[promoted]

    grouped:dict[tuple[str,str],dict[str,Any]]={}
    for row in bounded.get('candidate_rows') or []:
        key=(str(row.get('system') or ''),str(row.get('diameter_key') or ''))
        grouped[key]={**row,'sources':list(row.get('sources') or []),'source_pages':list(row.get('source_pages') or [])}
    key=(system,diameter_key)
    entry=grouped.setdefault(key,{
        'system':system,'diameter_key':diameter_key,'dn':evidence.get('dn'),
        'vertical_length_m_candidate':0.0,'run_count':0,'sources':[],'source_pages':[],
    })
    entry['vertical_length_m_candidate']=round(float(entry.get('vertical_length_m_candidate') or 0.0)+span,3)
    entry['run_count']=int(entry.get('run_count') or 0)+1
    source_role='SN-04_CALIBRATED_PLUS_SN-05_EQUIPMENT_PLAN'
    if source_role not in entry['sources']:
        entry['sources'].append(source_role)
    for p in (schematic_page,source_page):
        if p not in entry['source_pages']:
            entry['source_pages'].append(p)
    entry['source_pages'].sort()
    rows=sorted(grouped.values(),key=lambda r:(r['system'],r['diameter_key']))

    return {
        **bounded,
        'status':'LEVEL_BOUNDED_PLUS_EQUIPMENT_VERTICAL_CANDIDATES',
        'candidate_runs':candidate_runs,
        'withheld_runs':kept,
        'candidate_rows':rows,
        'candidate_run_count':len(candidate_runs),
        'withheld_run_count':len(kept),
        'equipment_vertical_status':'APPLIED',
        'equipment_promoted_run_count':1,
        'equipment_promoted_runs':[promoted],
        'equipment_evidence':evidence,
        'publication_policy':'DIAGNOSTIC_ONLY_NO_VERTICAL_PUBLICATION',
    }
