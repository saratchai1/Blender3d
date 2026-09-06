# OpenTakeoff + Automatic BOQ POC

This POC combines the real pinned `Kentucky-ai/opentakeoff` review canvas with a geometry-first Automatic BOQ benchmark for the real 99-page Thai drawing set `family4.pdf`.

## Source isolation

The v7 generator reads **drawing pages 1–71 only**. It never imports or opens `benchmark_reference.json`. The official BOQ range (pages 72–95) is read only by `score_auto_boq.py` after generation has finished.

## Validated automatic rows

| ID | Automatic method | Current benchmark output |
|---|---|---:|
| `ARCH-ROOF-METAL` | vector hatch band + 6° roof slope | 128.349 m² |
| `ARCH-FASCIA` | vector roof outline perimeter | 45.199 m |
| `ARCH-DOOR-D2` | door-swing radius | 7 ea |
| `ARCH-DOOR-D3` | door-swing radius | 4 ea |
| `SAN-WC-BOWL` | bathroom-detail template | 3 ea |
| `SAN-LAVATORY` | bathroom-detail template | 3 ea |
| `SAN-SHOWER-SET` | bathroom-detail template | 2 ea |
| `SAN-BIDET-SPRAY` | line-stripped CAD label | 3 ea |
| `SAN-PAPER-HOLDER` | line-stripped CAD label | 3 ea |
| `SAN-TOWEL-RAIL` | line-stripped CAD label | 3 ea |
| `SAN-BOOSTER-PUMP` | exact positioned `BP` tag | 1 ea |
| `SAN-WATER-METER` | exact positioned `M` tag | 1 ea |
| `SAN-FLOAT-VALVE` | exact positioned `FLOAT` tag | 1 ea |
| `SAN-FCO-4` | positioned sanitary drawing tag | 2 ea |
| `SAN-CO-2.5` | positioned sanitary drawing tag | 1 ea |
| `SAN-RFD-2.5` | positioned sanitary drawing tag | 2 ea |
| `SAN-AVC-2` | positioned sanitary drawing tag | 2 ea |
| `ELEC-DOWNLIGHT` | electrical legend template | 37 ea |
| `ELEC-T8-LONG` | electrical legend template | 1 ea |

The scored audit subset contains **20 rows**. Nineteen are detected: **95% coverage**. All 19 detected rows are within ±5%; current mean absolute percentage error is **0.05%**. This is an audit subset, **not full-project BOQ accuracy**.

## Floor drain is intentionally withheld

`SAN-FLOOR-DRAIN-2` is not published in v7. The SN-07 bathroom drawing exposes four physical `Ø2"FD` tags while the official BOQ reference is five. The same sheet also contains an `FD.` row in the fixture connection schedule, but a schedule row is not a physical installed instance. v7 therefore records the four explicit hits as `WITHHELD_DIAGNOSTIC_ONLY` rather than counting the schedule row to force a match.

## Pipe-length preparation

v7 inventories diameter/system tags on drawing pages 57–60, including tags such as `Ø2"W`, `Ø4"SW`, `Ø2"V`, `Ø2½"RFD`, `Ø2"AVC`, and CW tags. This inventory is diagnostic only. Pipe lengths remain withheld until vector-line tracing, system classification and plan/riser/detail de-duplication are validated.

## Accuracy policy

- Missing is safer than fabricated.
- Every published row carries `source_pages`, `method`, `confidence`, `review` and evidence.
- The source-page guard rejects any generation evidence after page 71.
- Reference quantities live in a different file and scorer.
- CI regenerates from the exact PDF before scoring and retains generated JSON as evidence.
- Automatic output is preliminary and requires estimator review before procurement.

## Web UI

GitHub Pages publishes `/Blender3d/takeoff/` with Automatic BOQ, the real OpenTakeoff/PDF.js review canvas, a separate Manual BOQ workspace, and an Accuracy/limitations page. Automatic and manual quantities remain separate to prevent double counting.

The verified Family4 demo is automatic. Arbitrary PDFs uploaded by users still open only in the Manual/Review workspace because GitHub Pages is static; runtime automatic extraction for new uploads is not implemented yet.

## Reproduce

Requires Python 3.12+, Node 24, PyMuPDF, NumPy and OpenCV.

```sh
python -m pip install -r integrations/opentakeoff/requirements-auto-boq.txt
python integrations/opentakeoff/fetch_sample.py --output .generated/samples/family4.pdf
python integrations/opentakeoff/auto_boq_v7.py \
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

`auto_boq.py` is the base extractor, `auto_boq_v6.py` adds line-stripped CAD label matching, and `auto_boq_v7.py` adds conservative positioned sanitary tag counts plus diagnostic pipe-tag inventory. `build.py` uses the v7 entry point.

## Current withheld scope

Floor drain, soap/floor faucet/valve items without stable evidence, windows, switch/socket, floor finishes, wall area, sanitary pipe lengths and structural quantities remain `WITHHELD`.

## Data and attribution

The OpenTakeoff canvas remains client-side and persists PDFs/annotations in browser IndexedDB. No public AI key, cloud sync or public MCP endpoint is configured. Never publish private/customer PDFs as CI fixtures.

OpenTakeoff remains under Apache-2.0 with LICENSE/NOTICE/third-party notices preserved. The downstream Automatic BOQ extractor/profile/scorer are project-specific additions in this repository.
