from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_pipe_release_candidate(
    reconciliation: dict[str, Any],
    vertical: dict[str, Any],
) -> dict[str, Any]:
    """Combine validated horizontal + vertical pipe evidence without publishing.

    Remaining SN-04 geometry is not silently dropped. It is classified as either:
    - vent terminal drawing pieces already represented by the roof-corroborated main
      riser length, or
    - local schematic service-branch geometry whose drawn vertical offset does not
      correspond to an explicit physical level interval and therefore must not be
      converted to metres from the riser diagram.

    Any other withheld class is a release blocker.
    """
    horizontal_gate = reconciliation.get('horizontal_diameter_gate')
    roof_status = vertical.get('roof_terminal_status')
    roof_extended = list(vertical.get('roof_extended_runs') or [])
    roof_v_classes = {
        (str(r.get('system') or ''), str(r.get('diameter_key') or ''))
        for r in roof_extended
    }

    excluded: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for run in vertical.get('withheld_runs') or []:
        system = str(run.get('system') or '')
        diameter_key = str(run.get('diameter_key') or '')
        terminal_above = float(run.get('terminal_extension_above_m') or 0.0)
        terminal_below = float(run.get('terminal_extension_below_m') or 0.0)
        if system == 'V' and terminal_above > 0 and (system, diameter_key) in roof_v_classes:
            excluded.append({
                **run,
                'release_exclusion_status': 'EXCLUDED_TERMINAL_PIECE_ALREADY_REPRESENTED_BY_ROOF_MAIN_RISER',
                'quantity_added_m': 0.0,
            })
            continue
        if system == 'CW' and terminal_above <= 0 and terminal_below <= 0:
            excluded.append({
                **run,
                'release_exclusion_status': 'EXCLUDED_SCHEMATIC_SERVICE_OFFSET_NO_EXPLICIT_PHYSICAL_HEIGHT',
                'quantity_added_m': 0.0,
            })
            continue
        blockers.append({
            **run,
            'release_blocker_status': 'WITHHELD_UNRESOLVED_VERTICAL_PHYSICAL_QUANTITY',
        })

    combined: dict[tuple[str, str], dict[str, Any]] = {}
    for row in reconciliation.get('horizontal_primary_rows') or []:
        key = (str(row.get('system') or ''), str(row.get('diameter_key') or ''))
        entry = combined.setdefault(key, {
            'system': key[0],
            'diameter_key': key[1],
            'dn': row.get('dn'),
            'diameter_mm': row.get('diameter_mm'),
            'diameter_in': row.get('diameter_in'),
            'horizontal_length_m': 0.0,
            'vertical_length_m': 0.0,
            'total_length_m': 0.0,
            'source_pages': [],
            'evidence_roles': [],
        })
        entry['horizontal_length_m'] += float(row.get('length_m_candidate') or 0.0)
        for p in row.get('source_pages') or []:
            if int(p) not in entry['source_pages']:
                entry['source_pages'].append(int(p))
        if 'PRIMARY_PLAN_HORIZONTAL' not in entry['evidence_roles']:
            entry['evidence_roles'].append('PRIMARY_PLAN_HORIZONTAL')

    for row in vertical.get('candidate_rows') or []:
        key = (str(row.get('system') or ''), str(row.get('diameter_key') or ''))
        entry = combined.setdefault(key, {
            'system': key[0],
            'diameter_key': key[1],
            'dn': row.get('dn'),
            'diameter_mm': None,
            'diameter_in': None,
            'horizontal_length_m': 0.0,
            'vertical_length_m': 0.0,
            'total_length_m': 0.0,
            'source_pages': [],
            'evidence_roles': [],
        })
        entry['vertical_length_m'] += float(row.get('vertical_length_m_candidate') or 0.0)
        if 57 not in entry['source_pages']:
            entry['source_pages'].append(57)
        for source in row.get('sources') or []:
            if source not in entry['evidence_roles']:
                entry['evidence_roles'].append(source)

    rows = []
    for entry in combined.values():
        entry['horizontal_length_m'] = round(entry['horizontal_length_m'], 3)
        entry['vertical_length_m'] = round(entry['vertical_length_m'], 3)
        entry['total_length_m'] = round(entry['horizontal_length_m'] + entry['vertical_length_m'], 3)
        entry['source_pages'].sort()
        rows.append(entry)
    rows.sort(key=lambda r: (r['system'], r['diameter_key']))

    ready = (
        horizontal_gate == 'PASS'
        and roof_status == 'APPLIED'
        and bool(rows)
        and not blockers
    )
    return {
        'status': 'PASS_VALIDATED_PIPE_RELEASE_CANDIDATE' if ready else 'WITHHELD_PIPE_RELEASE_BLOCKERS',
        'horizontal_gate': horizontal_gate,
        'vertical_roof_terminal_status': roof_status,
        'candidate_rows': rows,
        'candidate_row_count': len(rows),
        'excluded_non_quantity_runs': excluded,
        'excluded_non_quantity_run_count': len(excluded),
        'release_blockers': blockers,
        'release_blocker_count': len(blockers),
        'publication_policy': 'READY_FOR_PIPE_ROW_PUBLICATION' if ready else 'WITHHELD_NO_PIPE_PUBLICATION',
        'non_additive_contract': 'SN-05/SN-06 contribute horizontal length; SN-04 contributes only validated physical vertical length; SN-07 contributes sizing/matching evidence only; no view lengths are summed wholesale.',
    }
