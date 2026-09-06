from __future__ import annotations

from collections import defaultdict
from typing import Any


def explicit_level_intervals(markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    levels = sorted({round(float(m['elevation_m']), 4) for m in markers})
    out: list[dict[str, Any]] = []
    for i, lo in enumerate(levels):
        for hi in levels[i + 1:]:
            out.append({
                'low_elevation_m': float(lo),
                'high_elevation_m': float(hi),
                'span_m': round(float(hi - lo), 4),
            })
    return out


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def classify_vertical_runs(
    runs: list[dict[str, Any]],
    markers: list[dict[str, Any]],
    *,
    interval_span_tolerance_m: float = 0.18,
    min_interval_overlap_fraction: float = 0.75,
    full_band_coverage_tolerance_m: float = 0.20,
    major_run_min_m: float = 2.0,
) -> dict[str, Any]:
    intervals = explicit_level_intervals(markers)
    levels = sorted({round(float(m['elevation_m']), 4) for m in markers})
    if len(levels) < 2:
        return {
            'status': 'WITHHELD_INSUFFICIENT_EXPLICIT_LEVELS',
            'intervals': intervals,
            'candidate_runs': [],
            'withheld_runs': list(runs),
            'candidate_rows': [],
        }
    band_lo = float(levels[0]); band_hi = float(levels[-1]); band_span = band_hi - band_lo
    candidate_runs: list[dict[str, Any]] = []
    withheld_runs: list[dict[str, Any]] = []

    for run in runs:
        e0, e1 = map(float, run.get('elevation_span_m') or (0.0, 0.0))
        lo, hi = min(e0, e1), max(e0, e1)
        measured_span = float(run.get('vertical_span_m') or abs(hi - lo))
        band_overlap = _overlap(lo, hi, band_lo, band_hi)
        row = dict(run)
        row['explicit_level_band_m'] = [band_lo, band_hi]
        row['supported_band_overlap_m'] = round(band_overlap, 3)
        row['terminal_extension_above_m'] = round(max(0.0, hi - band_hi), 3)
        row['terminal_extension_below_m'] = round(max(0.0, band_lo - lo), 3)

        # Long continuous risers that cover essentially the full explicit level band
        # have a safe inter-level quantity equal to that band. Any extension beyond
        # the highest/lowest explicit level is kept separate and remains withheld.
        covers_full_band = (
            measured_span >= major_run_min_m
            and lo <= band_lo + full_band_coverage_tolerance_m
            and hi >= band_hi - full_band_coverage_tolerance_m
            and band_overlap >= band_span - full_band_coverage_tolerance_m
        )
        if covers_full_band:
            row['classification_status'] = 'CANDIDATE_COVERS_FULL_EXPLICIT_LEVEL_BAND'
            row['matched_level_interval_m'] = [band_lo, band_hi]
            row['vertical_length_m_candidate'] = round(band_span, 3)
            candidate_runs.append(row)
            continue

        best = None
        for interval in intervals:
            ilo = float(interval['low_elevation_m']); ihi = float(interval['high_elevation_m'])
            ispan = float(interval['span_m'])
            overlap = _overlap(lo, hi, ilo, ihi)
            overlap_fraction = overlap / ispan if ispan > 1e-9 else 0.0
            span_error = abs(measured_span - ispan)
            if span_error > interval_span_tolerance_m:
                continue
            if overlap_fraction < min_interval_overlap_fraction:
                continue
            score = (span_error, -overlap_fraction, ispan)
            if best is None or score < best[0]:
                best = (score, interval, overlap_fraction)
        if best is not None:
            _, interval, overlap_fraction = best
            row['classification_status'] = 'CANDIDATE_MATCHES_EXPLICIT_LEVEL_INTERVAL'
            row['matched_level_interval_m'] = [
                float(interval['low_elevation_m']), float(interval['high_elevation_m'])
            ]
            row['interval_overlap_fraction'] = round(float(overlap_fraction), 4)
            row['vertical_length_m_candidate'] = round(float(interval['span_m']), 3)
            candidate_runs.append(row)
        else:
            row['classification_status'] = 'WITHHELD_NO_EXPLICIT_LEVEL_INTERVAL_MATCH'
            withheld_runs.append(row)

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidate_runs:
        key = (str(row.get('system') or ''), str(row.get('diameter_key') or ''))
        entry = grouped.setdefault(key, {
            'system': key[0],
            'diameter_key': key[1],
            'dn': row.get('dn'),
            'vertical_length_m_candidate': 0.0,
            'run_count': 0,
            'source': 'SN-04_EXPLICIT_LEVEL_INTERVALS',
        })
        entry['vertical_length_m_candidate'] += float(row['vertical_length_m_candidate'])
        entry['run_count'] += 1
    candidate_rows = []
    for entry in grouped.values():
        entry['vertical_length_m_candidate'] = round(entry['vertical_length_m_candidate'], 3)
        candidate_rows.append(entry)
    candidate_rows.sort(key=lambda r: (r['system'], r['diameter_key']))

    return {
        'status': 'LEVEL_BOUNDED_VERTICAL_CANDIDATES',
        'explicit_levels_m': levels,
        'intervals': intervals,
        'candidate_runs': candidate_runs,
        'withheld_runs': withheld_runs,
        'candidate_rows': candidate_rows,
        'candidate_run_count': len(candidate_runs),
        'withheld_run_count': len(withheld_runs),
        'publication_policy': 'DIAGNOSTIC_ONLY_NO_VERTICAL_PUBLICATION',
        'note': 'Only spans corroborated by explicit SN-04 level intervals are candidates. Vent/terminal extensions outside the explicit level band and unmatched minor branches remain withheld.',
    }
