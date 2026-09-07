#!/usr/bin/env python3
"""Synthetic v8 tests: topology, duplicate suppression, tag parsing and scale guards."""
from __future__ import annotations

import math

import fitz

import auto_boq_v8 as v8


def make_page(*, multi_scale: bool = False) -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)

    def line(a: tuple[float, float], b: tuple[float, float]) -> None:
        shape = page.new_shape()
        shape.draw_line(a, b)
        shape.finish(color=(1, 0, 0), width=0.5, closePath=False)
        shape.commit()

    line((100, 100), (300, 100))
    line((300, 100), (400, 100))
    line((200, 100), (200, 200))  # T: endpoint lands on trunk interior
    line((150, 50), (150, 150))   # X: interior/interior crossing must stay separate
    line((100, 100), (300, 100))  # exact duplicate must not double count

    symbol = page.new_shape()
    symbol.draw_rect(fitz.Rect(450, 50, 500, 100))
    symbol.finish(color=(1, 0, 0), width=0.5, closePath=True)
    symbol.commit()

    page.insert_text((115, 88), 'Ø2" W', fontsize=10)
    page.insert_text((430, 350), "SCALE 1:100", fontsize=10)
    if multi_scale:
        page.insert_text((430, 330), "DETAIL SCALE 1:20", fontsize=10)
    return doc, page


def main() -> None:
    doc, page = make_page()
    analysis = v8.analyze_pipe_page(page, 1)
    assert analysis["segment_count"] == 4, analysis
    assert analysis["component_count"] == 2, analysis
    assert analysis["tag_count"] >= 1, analysis
    # Synthetic PyMuPDF drawings have no preserved CAD layer, so v8 must expose
    # the explicit unlayered fallback status rather than pretending layer proof.
    candidates = [row for row in analysis["candidate_components"] if row["status"] == "UNLAYERED_SINGLE_TAG_CLASS_CANDIDATE"]
    assert candidates, analysis
    candidate = candidates[0]
    assert candidate["classes"] == [{"system": "W", "diameter_in": 2.0}], candidate
    assert candidate["segment_count"] == 3, candidate
    assert candidate["publication_status"] == "WITHHELD_DIAGNOSTIC_ONLY"
    expected_m = 400 / 72 * 0.0254 * 100
    assert math.isclose(candidate["length_m_candidate"], round(expected_m, 3), abs_tol=1e-9), candidate

    # Thai CAD source uses both explicit and run-together mixed fractions.
    assert v8.parse_inches("2-1/2") == 2.5
    assert v8.parse_inches("21/2") == 2.5
    assert v8.parse_inches("11/2") == 1.5
    assert v8.parse_inches("3/4") == 0.75
    assert "S" in v8.PIPE_SYSTEMS
    doc.close()

    doc, page = make_page(multi_scale=True)
    analysis = v8.analyze_pipe_page(page, 2)
    assert analysis["scale_candidates_from_extractable_english_text"] == [100, 20], analysis
    candidate = analysis["candidate_components"][0]
    assert candidate["length_status"] == "WITHHELD_SCALE_AMBIGUOUS", candidate
    assert "length_m_candidate" not in candidate
    doc.close()
    print("AUTO_BOQ_V8_TEST_PASS", {"topology": "T connected / X separate", "scale_guard": "ambiguous withheld", "mixed_fraction": "Thai CAD forms parsed", "publication": "diagnostic-only"})


if __name__ == "__main__":
    main()
