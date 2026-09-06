# OpenTakeoff + Automatic BOQ POC

This POC combines the real pinned `Kentucky-ai/opentakeoff` review canvas with a geometry-first Automatic BOQ benchmark for the real 99-page Thai drawing set `family4.pdf`.

## What is automatic now

The v6 generator reads **drawing pages 1–71 only**. It has no import, path or quantity dependency on `benchmark_reference.json`. The official BOQ range (pages 72–95) is read only by the separate `score_auto_boq.py` after generation has finished.

Validated automatic detectors in the current Family4 profile:

| ID | Automatic method | Current benchmark output |
|---|---|---:|
| `ARCH-ROOF-METAL` | vector hatch band + 6° roof slope | 128.349 m² |
| `ARCH-FASCIA` | vector roof outline perimeter | 45.199 m |
| `ARCH-DOOR-D2` | door-swing radius, 0.80 m | 7 ea |
| `ARCH-DOOR-D3` | door-swing radius, 0.70 m | 4 ea |
| `SAN-WC-BOWL` | bathroom-detail template sweep | 3 ea |
| `SAN-LAVATORY` | bathroom-detail template sweep | 3 ea |
| `SAN-SHOWER-SET` | bathroom-detail template sweep | 2 ea |
| `SAN-BIDET-SPRAY` | line-stripped CAD label sweep | 3 ea |
| `SAN-PAPER-HOLDER` | line-stripped CAD label sweep | 3 ea |
| `SAN-TOWEL-RAIL` | line-stripped CAD label sweep | 3 ea |
| `SAN-BOOSTER-PUMP` | exact positioned plan label `BP` | 1 ea |
| `SAN-WATER-METER` | exact positioned plan label `M` | 1 ea |
| `SAN-FLOAT-VALVE` | exact positioned plan label `FLOAT` | 1 ea |
| `ELEC-DOWNLIGHT` | electrical legend template sweep | 37 ea |
| `ELEC-T8-LONG` | electrical legend template sweep | 1 ea |

The isolated audit subset contains **16 rows**. Fifteen are detected, giving **93.75% coverage of that audit subset**. All fifteen detected rows are within ±5%; the current mean absolute percentage error is about **0.063%**. These numbers are **not full-project BOQ accuracy**.

The three v6 accessory rows use visible labels on bathroom detail pages 23–25. The detector first suppresses long orthogonal CAD wall/grid lines, then matches the remaining label glyph pattern. This is specifically for drawings where legacy CAD fonts make normal text extraction unreliable. The short T8 row and broader categories remain withheld until their detectors are reliable.

## Accuracy policy

- Missing is safer than fabricated. Unsupported/ambiguous items return no quantity.
- Every published automatic row carries `source_pages`, `method`, `confidence`, `review` and evidence.
- Source-page guard rejects any generation attempt after page 71.
- Reference quantities live in a different file and scorer.
- CI regenerates quantities from the exact PDF before reading the reference and retains generated JSON as evidence.
- CI asserts known benchmark tolerances and that all generated evidence pages are <= 71.
- Automatic output is preliminary and requires estimator review before procurement.

## Web UI

GitHub Pages publishes `/Blender3d/takeoff/` with four surfaces:

1. **Automatic BOQ** — generated rows, quantity/unit, confidence, drawing-page evidence, method and error against the isolated audit reference.
2. **แบบ / ตรวจ** — the actual OpenTakeoff/PDF.js measurement canvas.
3. **Manual BOQ** — only user-created/review takeoff; kept separate to prevent automatic/manual double counting.
4. **วิธี / Accuracy** — source fence, method and limitations.

The demo uses the verified Family4 PDF. User-uploaded PDFs still open in the manual/review workspace. GitHub Pages is static, so the Python Automatic BOQ detector does **not yet run on arbitrary new uploads in-browser**.

## Reproduce

Requires Python 3.12+, Node 24, PyMuPDF, NumPy and OpenCV.

```sh
python -m pip install -r integrations/opentakeoff/requirements-auto-boq.txt
python integrations/opentakeoff/fetch_sample.py --output .generated/samples/family4.pdf
python integrations/opentakeoff/auto_boq_v6.py \
  --pdf .generated/samples/family4.pdf \
  --profile integrations/opentakeoff/profiles/family4.json \
  --output .generated/auto-boq.json
python integrations/opentakeoff/test_auto_boq.py \
  --pdf .generated/samples/family4.pdf \
  --profile integrations/opentakeoff/profiles/family4.json \
  --reference integrations/opentakeoff/benchmark_reference.json
python integrations/opentakeoff/score_auto_boq.py \
  --generated .generated/auto-boq.json \
  --reference integrations/opentakeoff/benchmark_reference.json \
  --output .generated/auto-boq-benchmark.json
```

`auto_boq.py` remains the v5 base extractor; `auto_boq_v6.py` extends it with the line-stripped label detector without giving either generator access to the reference file. `build.py` uses the v6 entry point.

## Current withheld scope

Windows, floor drains/soap accessories/floor faucets/valves that do not yet have stable fingerprints, switch/socket, floor finishes, wall area, sanitary pipe lengths and structural quantities remain `WITHHELD`. Sanitary piping is the next geometry target because the source drawings expose pipe system/diameter labels, but network-line classification must be validated before a length is published.

## Data and security

The OpenTakeoff canvas remains client-side and persists PDFs/annotations in browser IndexedDB. The automatic benchmark is generated in CI from the verified public sample and ships as JSON. No public AI key, cloud sync or public MCP endpoint is configured. Never publish private/customer PDFs as CI fixtures.

## Attribution

OpenTakeoff is retained under Apache-2.0 with its LICENSE, NOTICE and third-party notices. The downstream Automatic BOQ extractor/profile/scorer are project-specific additions in this repository.
