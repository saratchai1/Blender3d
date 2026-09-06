from __future__ import annotations

from typing import Any


def apply_valve_leader_evidence(
    bounded: dict[str, Any],
    valve_probe: dict[str, Any],
    *,
    allowed_system: str = 'CW',
    min_span_m: float = 0.5,
) -> dict[str, Any]:
    """Promote an unresolved vertical run only when an explicit valve leader lands on it.

    The valve callout diameter is treated as stronger evidence than an inferred
    dashed-network class for this vertical run only. The rule never alters the
    horizontal plan assignments or adds leader/gap geometry. A run qualifies when:
      * it is still withheld,
      * its system is the allowed system,
      * its calibrated vertical span is >= min_span_m,
      * a valve callout has an explicit normalized diameter,
      * the conservative leader resolver uniquely associates that callout to the
        expected CAD layer, and
      * the leader target segment is one of the run's actual source segments.
    Conflicting explicit valve diameters on one run are withheld.
    """
    evidence_by_segment: dict[int, list[dict[str, Any]]] = {}
    for callout in valve_probe.get('callouts') or []:
        dia = callout.get('diameter') or {}
        leader = callout.get('leader') or {}
        target = callout.get('target_segment') or {}
        if not dia.get('diameter_key'):
            continue
        if leader.get('status') != 'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER':
            continue
        if str(target.get('layer') or '') != allowed_system:
            continue
        try:
            index = int(target['segment_index'])
        except (KeyError, TypeError, ValueError):
            continue
        evidence_by_segment.setdefault(index, []).append(callout)

    promoted: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for run in bounded.get('withheld_runs') or []:
        if str(run.get('system') or '') != allowed_system:
            kept.append(run)
            continue
        span = float(run.get('vertical_span_m') or 0.0)
        if span < min_span_m:
            kept.append(run)
            continue
        run_segments = {int(x) for x in (run.get('segment_indexes') or [])}
        callouts: list[dict[str, Any]] = []
        for index in sorted(run_segments):
            callouts.extend(evidence_by_segment.get(index, []))
        if not callouts:
            kept.append(run)
            continue
        explicit_classes = {
            str((c.get('diameter') or {}).get('diameter_key'))
            for c in callouts
            if (c.get('diameter') or {}).get('diameter_key')
        }
        if len(explicit_classes) != 1:
            row = dict(run)
            row['classification_status'] = 'WITHHELD_CONFLICTING_EXPLICIT_VALVE_DIAMETERS'
            row['explicit_valve_classes'] = sorted(explicit_classes)
            row['valve_callouts'] = [c.get('name') for c in callouts]
            kept.append(row)
            conflicts.append(row)
            continue
        diameter_key = next(iter(explicit_classes))
        representative = callouts[0].get('diameter') or {}
        row = dict(run)
        row.update({
            'system': allowed_system,
            'diameter_key': diameter_key,
            'dn': representative.get('dn'),
            'classification_status': 'CANDIDATE_EXPLICIT_VALVE_LEADER_VERTICAL_BRANCH',
            'vertical_length_m_candidate': round(span, 3),
            'superseded_inferred_diameter_key': run.get('diameter_key'),
            'valve_evidence': [
                {
                    'name': c.get('name'),
                    'text': c.get('text'),
                    'diameter_key': (c.get('diameter') or {}).get('diameter_key'),
                    'target_segment_index': (c.get('target_segment') or {}).get('segment_index'),
                    'leader_hops': (c.get('leader') or {}).get('leader_hops'),
                    'terminal_distance_pt': (c.get('leader') or {}).get('terminal_distance_pt'),
                }
                for c in callouts
            ],
            'evidence_priority': 'EXPLICIT_VALVE_LEADER_OVERRIDES_INFERRED_NETWORK_CLASS_FOR_THIS_VERTICAL_RUN_ONLY',
        })
        promoted.append(row)

    candidate_runs = list(bounded.get('candidate_runs') or []) + promoted
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for run in candidate_runs:
        key = (str(run.get('system') or ''), str(run.get('diameter_key') or ''))
        entry = grouped.setdefault(key, {
            'system': key[0],
            'diameter_key': key[1],
            'dn': run.get('dn'),
            'vertical_length_m_candidate': 0.0,
            'run_count': 0,
            'sources': [],
        })
        entry['vertical_length_m_candidate'] += float(run.get('vertical_length_m_candidate') or 0.0)
        entry['run_count'] += 1
        status = str(run.get('classification_status') or '')
        if status == 'CANDIDATE_EXPLICIT_VALVE_LEADER_VERTICAL_BRANCH':
            source = 'SN-04_EXPLICIT_VALVE_LEADER'
        elif status == 'CANDIDATE_CORROBORATED_TO_ARCHITECTURAL_ROOF':
            source = 'SN-04_CALIBRATED_PLUS_A-06_ROOF_LEVEL'
        elif status == 'CANDIDATE_EXPLICIT_SINGLE_SEGMENT_VERTICAL_BRANCH':
            source = 'SN-04_EXPLICIT_DIRECT_SINGLE_SEGMENT'
        else:
            source = 'SN-04_EXPLICIT_LEVEL_INTERVALS'
        if source not in entry['sources']:
            entry['sources'].append(source)
    rows = []
    for entry in grouped.values():
        entry['vertical_length_m_candidate'] = round(float(entry['vertical_length_m_candidate']), 3)
        rows.append(entry)
    rows.sort(key=lambda r: (r['system'], r['diameter_key']))

    return {
        **bounded,
        'status': 'ROOF_PLUS_EXPLICIT_VALVE_VERTICAL_CANDIDATES',
        'candidate_runs': candidate_runs,
        'withheld_runs': kept,
        'candidate_rows': rows,
        'candidate_run_count': len(candidate_runs),
        'withheld_run_count': len(kept),
        'valve_leader_promoted_count': len(promoted),
        'valve_leader_promoted_runs': promoted,
        'valve_leader_conflict_count': len(conflicts),
        'publication_policy': 'DIAGNOSTIC_ONLY_NO_VERTICAL_PUBLICATION',
        'note_valve_leader': 'Only explicit valve leaders that terminate on a segment inside one unresolved vertical CW run may override that run inferred diameter. No horizontal assignment, leader length, or gap length is changed.',
    }
