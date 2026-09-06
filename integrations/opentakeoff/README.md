# OpenTakeoff + Automatic BOQ POC

This POC combines the real pinned `Kentucky-ai/opentakeoff` review canvas with a geometry-first Automatic BOQ benchmark for the real 99-page Thai drawing set `family4.pdf`.

## What is automatic now

`auto_boq.py` reads **drawing pages 1–71 only**. It has no import, path or quantity dependency on `benchmark_reference.json`. The official BOQ range (pages 72–95) is read only by the separate `score_auto_boq.py` after generation has finished.

Validated automatic detectors in the current Family4 profile:

| ID | Automatic method | Current benchmark output |
|---|---|---:|
| `ARCH-ROOF-METAL` | vector hatch band + 6° roof slope | 128.349 m² |
| `ARCH-FASCIA` | vector roof outline perimeter | 45.199 m |
| `ARCH-DOOR-D2` | door-swing radius, 0.80 m | 7 ea |
| `ARCH-DOOR-D3` | door-swing radius, 0.70 m | 4 ea |
| `SAN-WC-BOWL` | drawing-label template sweep on bathroom details pages 23–25 | 3 ea |
| `SAN-LAVATORY` | bathroom-detail template sweep | 3 ea |
| `SAN-SHOWER-SET` | bathroom-detail template sweep | 2 ea |
| `SAN-BOOSTER-PUMP` | exact positioned plan label `BP` | 1 ea |
| `SAN-WATER-METER` | exact positioned plan label `M` | 1 ea |
| `SAN-FLOAT-VALVE` | exact positioned plan label `FLOAT` | 1 ea |
| `ELEC-DOWNLIGHT` | electrical legend template sweep | 37 ea |
| `ELEC-T8-LONG` | electrical legend template sweep | 1 ea |

The separate official audit subset now contains **13 rows** across architecture, sanitary equipment/fixtures and electrical. Twelve are detected, giving **92.31% coverage of that audit subset**. All twelve detected rows are within ±5%; the current mean absolute percentage error is about **0.079%**. These numbers are **not full-project BOQ accuracy**.

The short T8 row and broader categories are withheld until their detectors are reliable. Current withheld registry: windows, sanitary fixtures beyond the validated bathroom/equipment tags, switch/socket, floor finishes, wall area, sanitary piping and structure.

## Accuracy policy

- Missing is safer than fabricated. Unsupported/ambiguous items return no quantity.
- Every published automatic row carries `source_pages`, `method`, `confidence`, `review` and evidence.
- Source-page guard rejects any generation attempt after page 71.
- Reference quantities live in a different file and scorer.
- `Automatic BOQ benchmark` CI regenerates quantities from the exact PDF before reading the reference and retains the generated JSON as evidence.
- CI asserts known benchmark tolerances and that all generated evidence pages are <= 71.
- Automatic output is preliminary and requires estimator review before procurement.

## Web UI

GitHub Pages publishes `/Blender3d/takeoff/` with four surfaces:

1. **Automatic BOQ** — generated rows, quantity/unit, confidence, drawing-page evidence, method and error against the isolated audit reference.
2. **แบบ / ตรวจ** — the actual OpenTakeoff/PDF.js measurement canvas.
3. **Manual BOQ** — only user-created/review takeoff; kept separate to prevent automatic/manual double counting.
4. **วิธี / Accuracy** — source fence, method and limitations.

The demo uses the verified Family4 PDF. User-uploaded PDFs still open in the manual/review workspace. GitHub Pages is static, so the Python Automatic BOQ detector does **not yet run on arbitrary new uploads in-browser**. Do not describe that capability as implemented yet.

## Reproduce

Requires Python 3.12+, Node 24, PyMuPDF, NumPy and OpenCV. Install the exact detector environment from the committed requirements file:

```sh
python -m pip install -r integrations/opentakeoff/requirements-auto-boq.txt
python integrations/opentakeoff/fetch_sample.py --output .generated/samples/family4.pdf
python integrations/opentakeoff/auto_boq.py \
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

To build the full site, checkout the pinned OpenTakeoff commit listed in `upstream.json` and run `build.py`; CI does this automatically. The Pages workflow also browser-tests the generated Automatic BOQ before deployment and runs a second acceptance test against the public HTTPS site after deployment.

## Data and security

The OpenTakeoff canvas remains client-side and persists PDFs/annotations in browser IndexedDB. The automatic benchmark is generated in CI from the verified public sample and ships as JSON. No public AI key, cloud sync or public MCP endpoint is configured. Never publish private/customer PDFs as CI fixtures.

## Attribution

OpenTakeoff is retained under Apache-2.0 with its LICENSE, NOTICE and third-party notices. The downstream Automatic BOQ extractor/profile/scorer are project-specific additions in this repository.
