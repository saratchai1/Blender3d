from __future__ import annotations

from collections import defaultdict
from typing import Any


def promote_direct_single_segment_branches(
    bounded: dict[str, Any],
    page_analysis: dict[str, Any],
    *,
    min_branch_span_m: float = 0.5,
    boundary_tolerance_m: float = 0.05,
) -> dict[str, Any]:
    """Promote only directly tagged, single-segment vertical branches.

    This is intentionally narrower than generic vertical inference. A branch must:
    - still be withheld after explicit-level interval matching,
    - consist of exactly one vertical segment,
    - have that segment classified as EXPLICIT_TAG_SEED,
    - remain inside the explicit level band (no terminal extension), and
    - be at least `min_branch_span_m` long.
    The measured calibrated span is used; no level snapping or gap length is added.
    """
    assignments = {
        int(r['segment_index']): r
        for r in page_analysis.get('diameter_assignments') or []
    }
    promoted: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for run in bounded.get('withheld_runs') or []:
        indexes = list(run.get('segment_indexes') or [])
        span = float(run.get('vertical_span_m') or 0.0)
        if len(indexes) != 1 or span < min_branch_span_m:
            kept.append(run)
            continue
        assignment = assignments.get(int(indexes[0]))
        if not assignment or assignment.get('status') != 'EXPLICIT_TAG_SEED':
            kept.append(run)
            continue
        if float(run.get('terminal_extension_above_m', 0.0)) > boundary_tolerance_m:
            kept.append(run)
            continue
        if float(run.get('terminal_extension_below_m', 0.0)) > boundary_tolerance_m:
            kept.append(run)
            continue
        classes = assignment.get('classes') or []
        if len(classes) != 1:
            kept.append(run)
            continue
        cls = classes[0]
        if str(cls.get('system')) != str(run.get('system')) or str(cls.get('diameter_key')) != str(run.get('diameter_key')):
            kept.append(run)
            continue
        row = dict(run)
        row['classification_status'] = 'CANDIDATE_EXPLICIT_SINGLE_SEGMENT_VERTICAL_BRANCH'
        row['vertical_length_m_candidate'] = round(span, 3)
        row['direct_assignment_status'] = assignment.get('status')
        row['direct_segment_index'] = int(indexes[0])
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
        source = (
            'SN-04_EXPLICIT_DIRECT_SINGLE_SEGMENT'
            if run.get('classification_status') == 'CANDIDATE_EXPLICIT_SINGLE_SEGMENT_VERTICAL_BRANCH'
            else 'SN-04_EXPLICIT_LEVEL_INTERVALS'
        )
        if source not in entry['sources']:
            entry['sources'].append(source)
    rows = []
    for entry in grouped.values():
        entry['vertical_length_m_candidate'] = round(entry['vertical_length_m_candidate'], 3)
        rows.append(entry)
    rows.sort(key=lambda r: (r['system'], r['diameter_key']))
    return {
        **bounded,
        'status': 'LEVEL_BOUNDED_PLUS_DIRECT_BRANCH_VERTICAL_CANDIDATES',
        'candidate_runs': candidate_runs,
        'withheld_runs': kept,
        'candidate_rows': rows,
        'candidate_run_count': len(candidate_runs),
        'withheld_run_count': len(kept),
        'direct_branch_promoted_count': len(promoted),
        'direct_branch_promoted_runs': promoted,
        'publication_policy': 'DIAGNOSTIC_ONLY_NO_VERTICAL_PUBLICATION',
        'note_direct_branch': 'Only explicit single-segment branches inside the explicit level band are added to vertical candidates. Multi-segment service stubs and terminal extensions remain withheld.',
    }
