# OpenTakeoff + Automatic BOQ POC

This POC combines the real pinned `Kentucky-ai/opentakeoff` review canvas with a geometry-first Automatic BOQ benchmark for the real 99-page Thai drawing set `family4.pdf`.

## Source isolation

The v8.18 generator is fenced to **drawing pages 1–71 only**. It never imports or opens `benchmark_reference.json` while generating quantities. The official BOQ range (pages 72–95) is read only by `score_auto_boq.py` after generation has finished.

## Validated automatic rows

The scored audit subset contains **20 reference rows**. Nineteen are detected: **95% coverage**. All 19 detected rows are within ±5%; current mean absolute percentage error is below **0.15%**. This score is an audit subset, **not full-project BOQ accuracy**.

Representative non-pipe outputs include:

| ID | Automatic method | Current output |
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

## Validated sanitary pipe output — v8.18

v8.18 publishes eight `SAN-PIPE-*` rows after all horizontal, vertical, roof-terminal, valve-leader and non-additive gates pass:

| ID | Horizontal m | Vertical m | Total m |
|---|---:|---:|---:|
| `SAN-PIPE-CW-DN15` | 7.296 | 1.228 | **8.524** |
| `SAN-PIPE-CW-DN20` | 19.812 | 6.300 | **26.112** |
| `SAN-PIPE-RL-DN65` | 3.570 | 0.000 | **3.570** |
| `SAN-PIPE-S-DN100` | 2.270 | 0.000 | **2.270** |
| `SAN-PIPE-SW-DN100` | 11.355 | 8.100 | **19.455** |
| `SAN-PIPE-V-DN50` | 1.365 | 13.300 | **14.665** |
| `SAN-PIPE-W-DN50` | 10.746 | 0.000 | **10.746** |
| `SAN-PIPE-W-DN65` | 4.708 | 2.450 | **7.158** |

Total validated sanitary pipe length: **92.500 m**.

### Pipe reconciliation contract

- SN-05 and SN-06 primary plans contribute horizontal length.
- SN-04 sanitary schematic contributes only vertical lengths validated by explicit level calibration/direct evidence.
- SN-07 enlarged details contribute sizing/matching evidence only and never add whole-view length.
- A-06 architectural roof evidence corroborates the top elevation of the main vent risers; duplicated terminal drawing pieces add zero metres.
- The tank-side CW service run `segments 182–187` is not treated as a drawing offset. `BALL VALVE Ø1/2"` on SN-04 has a unique leader terminating on segment 183, so the calibrated 1.228 m vertical branch is classified as **CW DN15**. This explicit leader evidence overrides the earlier inferred DN20 network class for that vertical run only.
- Remaining CW schematic offsets shorter than 0.5 m do not encode an explicit physical elevation interval and are retained as audited zero-quantity exclusions.
- Ambiguous/conflicting evidence remains withheld rather than averaged or guessed.

## Floor drain is intentionally withheld

`SAN-FLOOR-DRAIN-2` is not published. SN-07 exposes four physical `Ø2"FD` tags while the official BOQ reference is five. The same sheet also contains an `FD.` row in the fixture connection schedule, but a schedule row is not a physical installed instance. The generator therefore records the four explicit hits as `WITHHELD_DIAGNOSTIC_ONLY` rather than counting the schedule row to force a match.

## Accuracy policy

- Missing is safer than fabricated.
- Every published row carries `source_pages`, `method`, `confidence`, `review` and evidence.
- The source-page guard rejects generation evidence after page 71.
- Reference quantities live in a different file and scorer.
- CI regenerates from the exact PDF before scoring and retains generated JSON as evidence.
- Pipe publication is fail-closed: a release blocker prevents `SAN-PIPE-*` rows from being emitted.
- Automatic output is preliminary and requires estimator review before procurement.

## Web UI

GitHub Pages publishes `/Blender3d/takeoff/` with Automatic BOQ, the real OpenTakeoff/PDF.js review canvas, a separate Manual BOQ workspace, and an Accuracy/limitations page. Automatic and manual quantities remain separate to prevent double counting.

The verified Family4 demo is automatic. Arbitrary PDFs uploaded by users still open only in the Manual/Review workspace because GitHub Pages is static; runtime automatic extraction for new uploads is the next integration phase.

## Reproduce v8.18

Requires Python 3.12+, Node 24, PyMuPDF, NumPy and OpenCV.

```sh
python -m pip install -r integrations/opentakeoff/requirements-auto-boq.txt
python integrations/opentakeoff/fetch_sample.py --output .generated/samples/family4.pdf
python integrations/opentakeoff/auto_boq_v8_18.py \
  --pdf .generated/samples/family4.pdf \
  --profile integrations/opentakeoff/profiles/family4.json \
  --roof-evidence integrations/opentakeoff/profiles/family4_roof_level_evidence.json \
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

`auto_boq.py` is the base extractor. Versions v6–v15 build up conservative label, topology, detail, horizontal and vertical reconciliation evidence. v8.16 is now fail-safe on substantive unresolved CW vertical branches; v8.18 is the current validated Family4 publication entry point. `build.py` uses v8.18.

## Current withheld scope

Floor drain, soap/floor faucet/valve items without stable evidence, windows, switch/socket, floor finishes, wall area and structural quantities remain `WITHHELD`. Family4 sanitary pipe lengths are no longer withheld in v8.18 after their release gates pass.

## Data and attribution

The OpenTakeoff canvas remains client-side and persists PDFs/annotations in browser IndexedDB. No public AI key, cloud sync or public MCP endpoint is configured. Never publish private/customer PDFs as CI fixtures.

OpenTakeoff remains under Apache-2.0 with LICENSE/NOTICE/third-party notices preserved. The downstream Automatic BOQ extractor/profile/scorer are project-specific additions in this repository.
