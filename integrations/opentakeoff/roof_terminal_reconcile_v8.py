from __future__ import annotations

from collections import defaultdict
from typing import Any


def apply_roof_terminal_evidence(
    bounded: dict[str, Any],
    evidence: dict[str, Any],
    *,
    base_elevation_m: float = 0.0,
) -> dict[str, Any]:
    """Extend already-accepted full-band vent risers to a corroborated roof level.

    The source evidence is non-reference and system-scoped. A run must already be
    accepted as a full explicit-level-band candidate and its independently
    calibrated raw top must agree with the architectural roof level within the
    evidence tolerance. Short terminal/AVC geometry is never added separately.
    """
    result = dict(bounded)
    if evidence.get('reference_used') is not False or not evidence.get('generation_allowed'):
        result['roof_terminal_status'] = 'WITHHELD_ROOF_EVIDENCE_POLICY'
        return result
    try:
        source_page = int(evidence['source_page'])
        source_page_max = int(evidence['source_page_max'])
        roof = float(evidence['roof_elevation_m'])
        tol = float(evidence.get('max_calibrated_top_error_m', 0.15))
    except (KeyError, TypeError, ValueError):
        result['roof_terminal_status'] = 'WITHHELD_INVALID_ROOF_EVIDENCE'
        return result
    if source_page > source_page_max:
        result['roof_terminal_status'] = 'WITHHELD_ROOF_SOURCE_OUTSIDE_GENERATION_FENCE'
        return result
    allowed = {str(x) for x in evidence.get('allowed_systems') or []}
    if not allowed:
        result['roof_terminal_status'] = 'WITHHELD_ROOF_EVIDENCE_NO_ALLOWED_SYSTEMS'
        return result

    extended = []
    candidate_runs = []
    for run in bounded.get('candidate_runs') or []:
        row = dict(run)
        if (
            row.get('classification_status') == 'CANDIDATE_COVERS_FULL_EXPLICIT_LEVEL_BAND'
            and str(row.get('system') or '') in allowed
        ):
            span = row.get('elevation_span_m') or []
            if len(span) == 2:
                calibrated_top = max(float(span[0]), float(span[1]))
                error = abs(calibrated_top - roof)
                if error <= tol and roof > base_elevation_m:
                    row['classification_status'] = 'CANDIDATE_CORROBORATED_TO_ARCHITECTURAL_ROOF'
                    row['vertical_length_m_candidate'] = round(roof - base_elevation_m, 3)
                    row['architectural_roof_elevation_m'] = roof
                    row['calibrated_raw_top_m'] = round(calibrated_top, 3)
                    row['roof_top_error_m'] = round(error, 3)
                    row['roof_evidence_source_page'] = source_page
                    row['roof_evidence_id'] = evidence.get('evidence_id')
                    row['roof_extension_basis'] = 'CALIBRATED_SCHEMATIC_TOP_MATCHES_SOURCE_ARCH_ROOF_LEVEL'
                    extended.append(row)
        candidate_runs.append(row)

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
        if run.get('classification_status') == 'CANDIDATE_CORROBORATED_TO_ARCHITECTURAL_ROOF':
            source = 'SN-04_CALIBRATED_PLUS_A-06_ROOF_LEVEL'
        elif run.get('classification_status') == 'CANDIDATE_EXPLICIT_SINGLE_SEGMENT_VERTICAL_BRANCH':
            source = 'SN-04_EXPLICIT_DIRECT_SINGLE_SEGMENT'
        else:
            source = 'SN-04_EXPLICIT_LEVEL_INTERVALS'
        if source not in entry['sources']:
            entry['sources'].append(source)
    rows = []
    for entry in grouped.values():
        entry['vertical_length_m_candidate'] = round(entry['vertical_length_m_candidate'], 3)
        rows.append(entry)
    rows.sort(key=lambda r: (r['system'], r['diameter_key']))

    result.update({
        'status': 'ROOF_CORROBORATED_VERTICAL_CANDIDATES',
        'candidate_runs': candidate_runs,
        'candidate_rows': rows,
        'roof_terminal_status': 'APPLIED' if extended else 'NO_MATCHING_MAIN_RISER',
        'roof_extended_run_count': len(extended),
        'roof_extended_runs': extended,
        'roof_evidence': evidence,
        'publication_policy': 'DIAGNOSTIC_ONLY_NO_VERTICAL_PUBLICATION',
        'note_roof_terminal': 'Only full-band main risers whose calibrated top independently matches the source architectural roof level are extended. Short AVC/terminal geometry remains withheld and is never added separately.',
    })
    return result
