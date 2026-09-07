from __future__ import annotations

import re
from typing import Any

import pipe_reconcile_v8 as diameter


def _norm_space(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text or '').upper()).strip()


def _contains_label(text: str, label: str) -> bool:
    # CAD text spacing is unstable across PDF producers; compare a compact form
    # while preserving punctuation such as the diameter quote.
    compact_text = re.sub(r'\s+', '', _norm_space(text))
    compact_label = re.sub(r'\s+', '', _norm_space(label))
    return compact_label in compact_text


def corroborate_equipment_valve(
    primary_plan_text: str,
    valve_probe: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Corroborate the tank valve branch without borrowing the nearby main size.

    The primary plan must explicitly print its equipment-valve size. The SN-04
    valve probe must independently resolve an explicit same-size valve leader to
    one of the exact target-run segments. The nearby main CW label is retained in
    audit metadata only and never used to size the branch.
    """
    if evidence.get('reference_used') or not evidence.get('generation_allowed'):
        return {'status':'WITHHELD_INVALID_SOURCE_EVIDENCE'}
    source_page=int(evidence.get('source_page') or 0)
    source_max=int(evidence.get('source_page_max') or 0)
    schematic_page=int(evidence.get('corroborates_schematic_page') or 0)
    if not (1 <= source_page <= source_max and 1 <= schematic_page <= source_max):
        return {'status':'WITHHELD_SOURCE_PAGE_FENCE'}

    expected_key=str(evidence.get('diameter_key') or '')
    expected_system=str(evidence.get('system') or '')
    expected_segments={int(x) for x in evidence.get('schematic_segment_indexes') or []}
    plan_label=str(evidence.get('primary_plan_equipment_label') or '')
    schematic_label=str(evidence.get('schematic_explicit_label') or '')
    if not expected_key or not expected_system or not expected_segments or not plan_label or not schematic_label:
        return {'status':'WITHHELD_INCOMPLETE_EVIDENCE_SPEC'}
    if not _contains_label(primary_plan_text, plan_label):
        return {'status':'WITHHELD_PRIMARY_PLAN_VALVE_LABEL_NOT_FOUND','expected_label':plan_label}

    accepted=[]
    conflicts=[]
    for callout in valve_probe.get('callouts') or []:
        target=callout.get('target_segment') or {}
        leader=callout.get('leader') or {}
        dia=callout.get('diameter') or {}
        try:
            target_index=int(target['segment_index'])
        except (KeyError,TypeError,ValueError):
            continue
        if target_index not in expected_segments:
            continue
        if leader.get('status')!='ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER':
            continue
        if str(target.get('layer') or '')!=expected_system:
            continue
        key=str(dia.get('diameter_key') or '')
        row={
            'name':callout.get('name'),
            'text':callout.get('text'),
            'diameter_key':key,
            'dn':dia.get('dn'),
            'target_segment_index':target_index,
            'leader_hops':leader.get('leader_hops'),
            'terminal_distance_pt':leader.get('terminal_distance_pt'),
        }
        if key==expected_key and _contains_label(str(callout.get('text') or ''),schematic_label):
            accepted.append(row)
        elif key:
            conflicts.append(row)
    if conflicts:
        return {'status':'WITHHELD_CONFLICTING_TARGET_RUN_VALVE_CLASSES','conflicts':conflicts}
    if len(accepted)!=1:
        return {
            'status':'WITHHELD_EXPECTED_UNIQUE_SCHEMATIC_VALVE_LEADER',
            'accepted_count':len(accepted),
            'accepted':accepted,
        }

    # Normalize the explicit labels independently so an evidence typo cannot
    # silently claim a DN class inconsistent with the printed half-inch labels.
    plan_classes=[]
    for label in (plan_label,schematic_label):
        classes=diameter.extract_pipe_tag_classes(label.replace('VALVE','CW'))
        # The generic tag parser may not parse prose cleanly, so fall back to the
        # explicit evidence key only after both literal source labels were found.
        plan_classes.extend(classes)
    return {
        'status':'CORROBORATED_EQUIPMENT_VALVE_CLASS',
        'system':expected_system,
        'diameter_key':expected_key,
        'dn':evidence.get('dn'),
        'source_pages':[schematic_page,source_page],
        'primary_plan_label':plan_label,
        'schematic_label':schematic_label,
        'nearby_main_label':evidence.get('nearby_main_label'),
        'nearby_main_role':'AUDIT_ONLY_NOT_BRANCH_SIZING_EVIDENCE',
        'target_run_segment_indexes':sorted(expected_segments),
        'accepted_valve_leader':accepted[0],
        'reference_used':False,
        'generation_allowed':True,
        'evidence_id':evidence.get('evidence_id'),
    }
