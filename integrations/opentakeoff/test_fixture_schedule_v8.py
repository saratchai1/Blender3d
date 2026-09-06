#!/usr/bin/env python3
from __future__ import annotations

import fixture_schedule_v8 as schedule


FIXTURE_X = {
    "WC.": 556.0,
    "WC1.": 571.7,
    "LAV.": 587.9,
    "UR.": 602.8,
    "SH.": 619.0,
    "C.": 634.7,
    "SINK.": 650.4,
    "FD.": 665.8,
}
SYSTEM_Y = {"W.": 312.2, "V.": 363.0, "S.": 413.9, "CW.": 460.5}
VALUES = {
    "WC.": {"CW.": "1/2", "S.": "4", "V.": "2", "W.": "-"},
    "WC1.": {"CW.": "1", "S.": "4", "V.": "2", "W.": "-"},
    "LAV.": {"CW.": "1/2", "S.": "-", "V.": "1 1/2", "W.": "2"},
    "UR.": {"CW.": "3/4", "S.": "2", "V.": "1 1/2", "W.": "-"},
    "SH.": {"CW.": "1/2", "S.": "-", "V.": "-", "W.": "-"},
    "C.": {"CW.": "1/2", "S.": "-", "V.": "-", "W.": "-"},
    "SINK.": {"CW.": "1/2", "S.": "-", "V.": "1 1/2", "W.": "2"},
    "FD.": {"CW.": "-", "S.": "-", "V.": "-", "W.": "2"},
}


def word(text: str, cx: float, cy: float, w: float = 8.0, h: float = 5.0) -> dict:
    return {"text": text, "bbox_pt": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]}


def synthetic_words() -> list[dict]:
    words = []
    for code, x in FIXTURE_X.items():
        words.append(word(code, x, 522.0, 10.0, 16.0))
    for code, y in SYSTEM_Y.items():
        words.append(word(code, 541.0, y, 10.0, 8.0))
    for fixture, systems in VALUES.items():
        x = FIXTURE_X[fixture]
        for system, raw in systems.items():
            y = SYSTEM_Y[system]
            if raw == "1 1/2":
                # Match SN-07's rotated PDF encoding: fractional part above, whole below.
                words.append(word("1/2", x, y - 3.0))
                words.append(word("1", x, y + 8.0))
            else:
                words.append(word(raw, x, y))
    return words


def main() -> None:
    result = schedule.parse_fixture_schedule_words(synthetic_words())
    assert result["status"] == "PARSED", result
    assert result["connection_count"] == 18, result
    assert not result["ambiguous_cells"], result

    expected = {
        ("WC", "CW"): "DN15",
        ("WC", "S"): "DN100",
        ("WC", "V"): "DN50",
        ("WC1", "CW"): "DN25",
        ("WC1", "S"): "DN100",
        ("WC1", "V"): "DN50",
        ("LAV", "CW"): "DN15",
        ("LAV", "V"): "DN40",
        ("LAV", "W"): "DN50",
        ("UR", "CW"): "DN20",
        ("UR", "S"): "DN50",
        ("UR", "V"): "DN40",
        ("SH", "CW"): "DN15",
        ("C", "CW"): "DN15",
        ("SINK", "CW"): "DN15",
        ("SINK", "V"): "DN40",
        ("SINK", "W"): "DN50",
        ("FD", "W"): "DN50",
    }
    got = {(row["fixture"], row["system"]): row["diameter_key"] for row in result["rows"]}
    assert got == expected, got
    assert result["matrix"]["FD"]["CW"]["status"] == "NO_CONNECTION"
    assert result["matrix"]["LAV"]["S"]["status"] == "NO_CONNECTION"
    print("FIXTURE_SCHEDULE_V8_TEST_PASS", {"connections": len(got), "source": "vector grid, no OCR"})


if __name__ == "__main__":
    main()
