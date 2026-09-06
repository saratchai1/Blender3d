from __future__ import annotations

from collections import defaultdict
from typing import Any


def _tag_evidence(tag: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    system = str(tag.get('system') or '').strip().upper()
    diameter_key = str(tag.get('diameter_key') or '').strip().upper()
    layer = str(tag.get('expected_layer') or tag.get('layer') or '').strip().upper()
    if not system or not diameter_key or not layer:
        return None
    return {
        'system': system,
        'diameter_key': diameter_key,
        'layer': layer,
        'dn': tag.get('dn'),
        'diameter_mm': tag.get('diameter_mm'),
        'diameter_in': tag.get('diameter_in'),
        'source_id': source_id,
    }


def collect_local_evidence(
    page: dict[str, Any],
    detail_probes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collect explicit class evidence tied to one primary sheet.

    Primary text tags are evidence even when their leader cannot be associated to a
    specific segment. Detail tags are used only from a detail view already accepted
    by the geometric detail matcher for this target page. Detail length is never used.
    """
    out: list[dict[str, Any]] = []
    for tag in page.get('tags_direct') or []:
        item = _tag_evidence(tag, 'PRIMARY_DIRECT')
        if item:
            out.append(item)

    page_no = int(page.get('page', 0))
    for probe in detail_probes:
        if int(probe.get('target_page', -1)) != page_no:
            continue
        if probe.get('status') != 'DIAGNOSTIC_TRANSFER_PROBED':
            continue
        detail_id = str(probe.get('id') or probe.get('detail_page') or 'DETAIL')
        for row in probe.get('transfer_candidates') or []:
            # Every transfer row originated from an explicit diameter/system tag in
            # the matched enlarged detail. Target-segment match status is irrelevant
            # for class consensus because no target geometry is copied here.
            item = _tag_evidence(row, f'DETAIL:{detail_id}')
            if item:
                out.append(item)
    return out


def collect_schematic_classes(schematic_page: dict[str, Any] | None) -> dict[str, set[str]]:
    by_system: dict[str, set[str]] = defaultdict(set)
    if not schematic_page:
        return by_system
    for tag in schematic_page.get('tags_direct') or []:
        system = str(tag.get('system') or '').strip().upper()
        diameter_key = str(tag.get('diameter_key') or '').strip().upper()
        if system and diameter_key:
            by_system[system].add(diameter_key)
    return by_system


def derive_consensus(
    page: dict[str, Any],
    detail_probes: list[dict[str, Any]],
    schematic_page: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Derive one safe system+diameter class per semantic layer, or withhold it.

    Acceptance paths:
      1) At least two independent local sources (primary and/or different matched
         detail views) all agree on exactly one (system, diameter) class on a layer.
      2) Exactly one local source is present and the vertical schematic contains
         that exact system at exactly one diameter, matching the local class.

    Any local class conflict is terminal. Schematic evidence never overrides a local
    conflict and never contributes pipe length.
    """
    local = collect_local_evidence(page, detail_probes)
    schematic = collect_schematic_classes(schematic_page)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in local:
        grouped[item['layer']].append(item)

    result: dict[str, dict[str, Any]] = {}
    for layer, evidence in grouped.items():
        classes = {(e['system'], e['diameter_key']) for e in evidence}
        sources = {e['source_id'] for e in evidence}
        base = {
            'layer': layer,
            'local_classes': [
                {'system': system, 'diameter_key': diameter}
                for system, diameter in sorted(classes)
            ],
            'local_sources': sorted(sources),
            'local_evidence_count': len(evidence),
        }
        if len(classes) != 1:
            result[layer] = {
                **base,
                'status': 'WITHHELD_CONFLICTING_LOCAL_CLASSES',
                'publication_role': 'EVIDENCE_ONLY',
            }
            continue

        system, diameter_key = next(iter(classes))
        representative = next(
            e for e in evidence
            if e['system'] == system and e['diameter_key'] == diameter_key
        )
        if len(sources) >= 2:
            result[layer] = {
                **base,
                'status': 'CORROBORATED_PAGE_LOCAL_MULTI_VIEW_CLASS',
                'basis': 'PAGE_LOCAL_MULTI_VIEW_CONSENSUS',
                'system': system,
                'diameter_key': diameter_key,
                'dn': representative.get('dn'),
                'diameter_mm': representative.get('diameter_mm'),
                'diameter_in': representative.get('diameter_in'),
                'publication_role': 'DIAMETER_CLASS_EVIDENCE_ONLY',
            }
            continue

        schematic_diameters = set(schematic.get(system, set()))
        if schematic_diameters == {diameter_key}:
            result[layer] = {
                **base,
                'status': 'CORROBORATED_PAGE_LOCAL_PLUS_SCHEMATIC_CLASS',
                'basis': 'PAGE_LOCAL_PLUS_SCHEMATIC_CORROBORATION',
                'system': system,
                'diameter_key': diameter_key,
                'dn': representative.get('dn'),
                'diameter_mm': representative.get('diameter_mm'),
                'diameter_in': representative.get('diameter_in'),
                'schematic_diameters_for_system': sorted(schematic_diameters),
                'publication_role': 'DIAMETER_CLASS_EVIDENCE_ONLY',
            }
        else:
            result[layer] = {
                **base,
                'status': 'WITHHELD_INSUFFICIENT_INDEPENDENT_CORROBORATION',
                'system': system,
                'diameter_key': diameter_key,
                'schematic_diameters_for_system': sorted(schematic_diameters),
                'publication_role': 'EVIDENCE_ONLY',
            }
    return result


def apply_consensus_to_assignments(
    assignments: list[dict[str, Any]],
    consensus: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Seed only previously evidence-free segments; never override ties/conflicts."""
    accepted_statuses = {
        'CORROBORATED_PAGE_LOCAL_MULTI_VIEW_CLASS',
        'CORROBORATED_PAGE_LOCAL_PLUS_SCHEMATIC_CLASS',
    }
    out: list[dict[str, Any]] = []
    summary: dict[str, dict[str, Any]] = {}
    for row in assignments:
        new = dict(row)
        layer = str(row.get('layer') or '').upper()
        evidence = consensus.get(layer)
        if (
            row.get('status') == 'WITHHELD_NO_DIAMETER_EVIDENCE'
            and not row.get('classes')
            and evidence
            and evidence.get('status') in accepted_statuses
        ):
            new['status'] = 'CROSS_VIEW_CORROBORATED_SYSTEM_CLASS'
            new['classes'] = [{
                'system': evidence['system'],
                'diameter_key': evidence['diameter_key'],
                'dn': evidence.get('dn'),
                'diameter_mm': evidence.get('diameter_mm'),
                'diameter_in': evidence.get('diameter_in'),
            }]
            new['diameter_evidence_role'] = evidence['basis']
            entry = summary.setdefault(layer, {
                'layer': layer,
                'system': evidence['system'],
                'diameter_key': evidence['diameter_key'],
                'basis': evidence['basis'],
                'seeded_segment_count': 0,
                'seeded_length_pt': 0.0,
            })
            entry['seeded_segment_count'] += 1
            entry['seeded_length_pt'] += float(row.get('length_pt') or 0.0)
        out.append(new)

    rows = []
    for layer in sorted(summary):
        item = summary[layer]
        item['seeded_length_pt'] = round(float(item['seeded_length_pt']), 3)
        rows.append(item)
    return out, rows
