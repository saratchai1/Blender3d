from __future__ import annotations

from copy import deepcopy
from typing import Any

SYSTEM_LABELS = {
    'CW': 'Cold Water',
    'RL': 'Rainwater',
    'S': 'Soil',
    'SW': 'Soil/Waste',
    'V': 'Vent',
    'W': 'Waste',
}


def publish_validated_pipe_rows(result: dict[str, Any], release: dict[str, Any]) -> dict[str, Any]:
    if release.get('status') != 'PASS_VALIDATED_PIPE_RELEASE_CANDIDATE':
        raise ValueError('pipe release gate is not PASS')
    if release.get('publication_policy') != 'READY_FOR_PIPE_ROW_PUBLICATION':
        raise ValueError('pipe publication policy is not ready')
    if int(release.get('release_blocker_count') or 0) != 0:
        raise ValueError('pipe release still has blockers')

    out = deepcopy(result)
    existing_ids = {str(row.get('id') or '') for row in out.get('rows', [])}
    pipe_rows = []
    for candidate in release.get('candidate_rows') or []:
        system = str(candidate.get('system') or '').upper()
        diameter_key = str(candidate.get('diameter_key') or '')
        quantity = round(float(candidate.get('total_length_m') or 0.0), 3)
        if not system or not diameter_key or quantity <= 0:
            raise ValueError(f'invalid pipe candidate: {candidate!r}')
        row_id = f'SAN-PIPE-{system}-{diameter_key}'
        if row_id in existing_ids:
            raise ValueError(f'duplicate pipe row id: {row_id}')
        label = SYSTEM_LABELS.get(system, system)
        pipe_rows.append({
            'id': row_id,
            'description': f'ท่อ {label} {diameter_key}',
            'category': 'Sanitary',
            'unit': 'm',
            'quantity': quantity,
            'confidence': 0.93,
            'method': 'vector:validated primary-plan horizontal + evidence-bounded vertical reconciliation',
            'source_pages': sorted({int(p) for p in candidate.get('source_pages') or []}),
            'review': 'REVIEW_REQUIRED',
            'evidence': {
                'system': system,
                'diameter_key': diameter_key,
                'dn': candidate.get('dn'),
                'horizontal_length_m': round(float(candidate.get('horizontal_length_m') or 0.0), 3),
                'vertical_length_m': round(float(candidate.get('vertical_length_m') or 0.0), 3),
                'evidence_roles': list(candidate.get('evidence_roles') or []),
                'release_gate_status': release.get('status'),
                'non_additive_contract': release.get('non_additive_contract'),
            },
        })
        existing_ids.add(row_id)

    pipe_rows.sort(key=lambda r: r['id'])
    out.setdefault('rows', []).extend(pipe_rows)
    coverage = out.setdefault('coverage', {})
    supported = coverage.setdefault('supported_detectors', [])
    if 'validated sanitary pipe takeoff' not in supported:
        supported.append('validated sanitary pipe takeoff')
    coverage['withheld_detectors'] = [
        item for item in coverage.get('withheld_detectors', [])
        if item.get('name') != 'sanitary piping'
    ]
    out.setdefault('diagnostics', []).append({
        'detector': 'sanitary_pipe_publication_v8',
        'status': 'PUBLISHED_VALIDATED_PIPE_ROWS',
        'published_pipe_row_count': len(pipe_rows),
        'published_pipe_ids': [row['id'] for row in pipe_rows],
        'release_gate_status': release.get('status'),
        'excluded_non_quantity_run_count': release.get('excluded_non_quantity_run_count', 0),
        'release_blocker_count': release.get('release_blocker_count', 0),
    })
    return out
