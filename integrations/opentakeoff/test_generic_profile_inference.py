#!/usr/bin/env python3
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import fitz

import generic_profile_inference as generic
import runtime_backend


def make_vector_pdf(path: Path, *, title: str = 'SANITARY PLAN SCALE 1:100 DN20 CW', include_reference: bool = False, second_plan: bool = False) -> None:
    doc = fitz.open()
    ocg = doc.add_ocg('CW')
    page = doc.new_page(width=595, height=842)
    page.insert_text((110, 190), title, fontsize=10)
    page.draw_line((100, 200), (300, 200), width=1, color=(0, 0, 0), oc=ocg)
    if include_reference:
        ref = doc.new_page(width=595, height=842)
        ref.insert_text((72, 72), 'BILL OF QUANTITIES - reference only', fontsize=12)
    if second_plan:
        page2 = doc.new_page(width=595, height=842)
        page2.insert_text((110, 190), 'SANITARY PLAN SCALE 1:100 DN20 CW', fontsize=10)
        page2.draw_line((100, 200), (300, 200), width=1, color=(0, 0, 0), oc=ocg)
    doc.save(path)
    doc.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = root / 'generic.pdf'
        make_vector_pdf(good, include_reference=True)
        out = generic.infer_generic_pdf(good)
        assert out['runtime_status'] == 'PUBLISHED_GENERIC_INFERRED_BOQ', out
        assert out['source_policy']['reference_used_for_generation'] is False, out
        assert out['source_policy']['excluded_reference_pages'] == [2], out['source_policy']
        assert len(out['rows']) == 1, out['rows']
        row = out['rows'][0]
        assert row['id'] == 'GEN-SAN-PIPE-CW-DN20', row
        assert row['unit'] == 'm' and row['source_pages'] == [1], row
        expected = 200.0 / 72.0 * 0.0254 * 100.0
        assert math.isclose(row['quantity'], round(expected, 3), abs_tol=1e-9), (row, expected)
        assert row['evidence']['release_gate_status'] == 'PASS_GENERIC_VECTOR_PIPE_V0', row
        assert row['evidence']['assigned_fraction'] >= 0.95, row

        via_runtime = runtime_backend.run_registered_pdf(good)
        assert via_runtime['runtime_status'] == 'PUBLISHED_GENERIC_INFERRED_BOQ', via_runtime
        assert via_runtime['runtime_profile'] == 'generic-inferred-vector-sanitary-v0', via_runtime
        assert via_runtime['runtime_profile_sha256_gate'] is None, via_runtime
        assert via_runtime['runtime_pipe_summary']['published_rows'] == 1, via_runtime

        ambiguous = root / 'two-plans.pdf'
        make_vector_pdf(ambiguous, second_plan=True)
        held = generic.infer_generic_pdf(ambiguous)
        assert held['runtime_status'] == 'WITHHELD_GENERIC_INFERENCE', held
        assert held['rows'] == [], held
        assert any('exactly one' in x['reason'] for x in held['coverage']['withheld_detectors']), held

        no_scale = root / 'no-scale.pdf'
        make_vector_pdf(no_scale, title='SANITARY PLAN DN20 CW')
        held = generic.infer_generic_pdf(no_scale)
        assert held['runtime_status'] == 'WITHHELD_GENERIC_INFERENCE', held
        assert held['rows'] == [], held
        assert any('SCALE 1:N' in x['reason'] for x in held['coverage']['withheld_detectors']), held

        reference_only = root / 'boq.pdf'
        make_vector_pdf(reference_only, title='BILL OF QUANTITIES SCALE 1:100 DN20 CW')
        held = generic.infer_generic_pdf(reference_only)
        assert held['runtime_status'] == 'WITHHELD_GENERIC_INFERENCE', held
        assert held['rows'] == [], held
        assert held['source_policy']['excluded_reference_pages'] == [1], held

    print('GENERIC_PROFILE_INFERENCE_TEST_PASS')


if __name__ == '__main__':
    main()
