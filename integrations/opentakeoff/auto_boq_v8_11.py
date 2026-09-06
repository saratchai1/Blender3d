#!/usr/bin/env python3
"""v8.11 diagnostic: v8.10 + conflict-safe cross-view system consensus.

Previously evidence-free primary-plan segments may receive a system+diameter class
only when explicit source-page evidence independently corroborates one class and
no local class conflict exists. Schematic/detail geometry remains evidence-only;
no length from those views is added and no SAN-PIPE row is published.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import auto_boq_v8_10 as v810
import cross_view_system_consensus_v8 as consensus
import pipe_reconcile_v8 as reconcile

SCHEMA = v810.SCHEMA


def extract(pdf_path: Path, profile_path: Path) -> dict:
    result = v810.extract(pdf_path, profile_path)
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_10'),
        None,
    )
    if not diag:
        return result

    schematic = next(
        (p for p in diag.get('pages', []) if p.get('view_role') == 'vertical_schematic'),
        None,
    )
    page_summaries = []
    for page in diag.get('pages', []):
        if page.get('contribution_policy') != 'PRIMARY_PLAN_HORIZONTAL':
            continue
        evidence = consensus.derive_consensus(
            page,
            diag.get('detail_view_reconciliation') or [],
            schematic,
        )
        before_assignments = page.get('diameter_assignments') or []
        before_coverage = dict(page.get('diameter_coverage') or {})
        assignments, applied = consensus.apply_consensus_to_assignments(
            before_assignments,
            evidence,
        )
        scales = page.get('effective_scale_candidates') or []
        scale_ratio = int(scales[0]) if len(scales) == 1 else None
        rows, coverage = reconcile.aggregate_diameter_rows(assignments, scale_ratio)
        page['diameter_assignments_pre_cross_view_consensus'] = before_assignments
        page['diameter_rows_pre_cross_view_consensus'] = page.get('diameter_rows')
        page['diameter_coverage_pre_cross_view_consensus'] = before_coverage
        page['cross_view_system_consensus'] = evidence
        page['cross_view_system_consensus_application'] = applied
        page['diameter_assignments'] = assignments
        page['diameter_rows'] = rows
        page['diameter_coverage'] = coverage
        page['diameter_publication_status'] = (
            'PRIMARY_DIAMETER_GATE_CANDIDATE'
            if coverage.get('assigned_fraction', 0.0) >= 0.95 and scale_ratio
            else 'WITHHELD_DIAMETER_COVERAGE_OR_SCALE'
        )
        page_summaries.append({
            'page': int(page['page']),
            'sheet': page.get('sheet'),
            'coverage_before': before_coverage.get('assigned_fraction'),
            'coverage_after': coverage.get('assigned_fraction'),
            'accepted_layers': [
                {
                    'layer': layer,
                    'system': item.get('system'),
                    'diameter_key': item.get('diameter_key'),
                    'basis': item.get('basis'),
                }
                for layer, item in sorted(evidence.items())
                if str(item.get('status', '')).startswith('CORROBORATED_')
            ],
            'withheld_layers': [
                {
                    'layer': layer,
                    'status': item.get('status'),
                    'local_classes': item.get('local_classes'),
                }
                for layer, item in sorted(evidence.items())
                if not str(item.get('status', '')).startswith('CORROBORATED_')
            ],
            'applications': applied,
        })

    cfg = profile.get('sanitary_pipe_network', {})
    diag['reconciliation'] = reconcile.reconcile_pages(
        diag.get('pages', []),
        min_primary_diameter_coverage=float(cfg.get('min_primary_diameter_coverage', 0.95)),
    )
    diag['detector'] = 'sanitary_pipe_network_v8_11'
    diag['status'] = 'DIAGNOSTIC_CROSS_VIEW_CORROBORATED_CLASSES_NO_PUBLISHED_PIPE_ROWS'
    diag['cross_view_system_consensus_summary'] = page_summaries
    diag['cross_view_system_consensus_policy'] = {
        'local_independent_sources_required': 2,
        'single_local_source_requires_unique_schematic_exact_class': True,
        'local_class_conflict': 'WITHHOLD',
        'schematic_or_detail_length_added': False,
        'overrides_existing_class_or_tie': False,
    }
    diag['note_v8_11'] = (
        'v8.11 classifies only previously evidence-free primary-plan segments when explicit tags from at least two independent local sources agree on one exact system+diameter class, '
        'or when one local source is corroborated by the same system having exactly one matching diameter in the vertical schematic. Any local system/diameter conflict remains withheld. '
        'Detail and schematic lengths are never added; they provide class evidence only.'
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', type=Path, required=True)
    ap.add_argument('--profile', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = extract(args.pdf, args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_11'),
        None,
    )
    pages = (diag or {}).get('pages') or []
    rec = (diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_11_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'primary_coverage': {
            p.get('sheet'): (p.get('diameter_coverage') or {}).get('assigned_fraction')
            for p in pages if p.get('contribution_policy') == 'PRIMARY_PLAN_HORIZONTAL'
        },
        'cross_view_consensus': (diag or {}).get('cross_view_system_consensus_summary', []),
        'horizontal_diameter_gate': rec.get('horizontal_diameter_gate'),
        'full_pipe_boq_publication_status': rec.get('full_pipe_boq_publication_status'),
        'published_pipe_rows': sum(
            1 for r in result.get('rows', [])
            if str(r.get('id', '')).startswith('SAN-PIPE-')
        ),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
