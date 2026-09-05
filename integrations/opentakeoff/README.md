# OpenTakeoff POC — Takeoff Lab

A real, pinned build of [Kentucky-ai/opentakeoff](https://github.com/Kentucky-ai/opentakeoff) alongside the existing Blender3d presentation. The native engine is built into `takeoff/engine/`; the iframe does not point at an external demo.

## Open

GitHub Pages publishes `/Blender3d/takeoff/` after the `pages.yml` build and browser QA pass. The original root presentation and IFC assets are preserved. See the actual Actions result for deployment status.

## Implemented by this POC

- Full upstream React/PDF.js takeoff canvas; Thai drawing/BOQ/guide shell.
- Synthetic vector PDF, 20 x 12 m, with 12 scripted proposals under 7 conditions.
- Independent IndexedDB namespaces for demo and user workspaces; no resetting of user documents when loading the demo.
- Read-only adapter invokes upstream `conditionTotals`, separates floor/wall/linear/count roles, converts ft/SF to SI without changing native storage math.
- Native area/line/surface/count, scale, review and report/project export tools are retained upstream capabilities.
- Local autosave to BOQ updates; CSV formula-injection protection; native takeoff JSON download; source sheet/shape IDs and pending-review counts.
- Exact upstream commit, npm lockfile, license notices, adapter tests, actual Chromium QA.

## Demo checks

| Kind | Baseline without waste |
|---|---:|
| Floor | 96 + 40 + 24 + 80 = 240 m² |
| Wall finish | 20 x 3 = 60 m² |
| Skirting | 20 m |
| Light fittings | 6 each |

This fixture is **not a floor plan extracted from SOLSTICE 14** and not AI room detection. Areas exclude no wall thickness/openings; waste is illustrative. Initial shape provenance is `actor: agent`, `method: poc_fixture_v1`, `reviewed: false`. The native human review gate stays in place. Nothing is added to the existing building's IFC quantities.

## Reproduce

Python 3.12+ and Node 24 are required for this pinned web build. MCP runtime requirements are separate; this POC does not deploy MCP.

```sh
git clone https://github.com/saratchai1/Blender3d.git
cd Blender3d
git clone https://github.com/Kentucky-ai/opentakeoff.git .external/opentakeoff-poc
git -C .external/opentakeoff-poc checkout 7a3c8eb44252d0d9083157ad9677866f92f711bb
node web/office_10000sqm/tools/build-pages.mjs
python integrations/opentakeoff/build.py --upstream .external/opentakeoff-poc --output .generated/pages/takeoff
python -m http.server 8080 --directory .generated/pages
# Open http://localhost:8080/takeoff/
```

The builder patches only the disposable upstream checkout: mounting shell, storage names, relative demo fetches and local connection policy. It does not rewrite shapeMetrics, geometry, totals, or the measurement canvas.

## Tests

```sh
node --test web/opentakeoff-poc/report.test.mjs
python -m pip install playwright==1.57.0
python -m playwright install chromium
python web/opentakeoff-poc/smoke.py --root .generated/pages
```

The builder runs upstream typechecking and the full upstream test suite. Workflow artifacts: `blender3d-pages-qa` includes screenshots, synthetic PDF, downloaded CSV/JSON and `qa.json`; `opentakeoff-poc-static` contains the portable static build. A configured test is not proof of a pass: inspect the run result.

## Data, security and limits

Files persist in browser IndexedDB, not cloud backup. Workspaces share an origin and are separate databases, not multi-user authorization boundaries. Clearing browser data loses work. Use native Project export for a complete archive; the added JSON export contains geometry/scale, **not PDF bytes**.

The read-only bridge validates exact origin and iframe identity. CSP restricts network connections to same-origin/blob. No AI credentials, cloud sync, external AI call or public MCP endpoint is configured. Optional upstream AI/cloud controls are not connected integrations; do not enter credentials into them. CI fixtures are synthetic; never publish customer drawings as QA artifacts.

One-Click/detect_rooms and command/voice remain off. No IFC import, BIM GUID mapping, 2D/3D reconciliation, prices, cost calculation or certified BOQ. Do not sum unlike units or add 2D quantities to IFC blindly. Count waste is zero per upstream. Native two-decimal SF/ft rounding can produce metric differences below 0.01 m² in this fixture. The canvas is best used on desktop; mobile shell QA does not certify all native drawing gestures on iOS/Safari. Export uses the latest saved state, not an unfinished polygon.

No changes to Blender, Pascal, 3DGS, building geometry or IFC generation.

## Attribution

Pin `7a3c8eb44252d0d9083157ad9677866f92f711bb` verified 2026-09-05. Apache-2.0. Distribution retains LICENSE, NOTICE and third-party notices, plus POC-NOTICE describing downstream changes. See `upstream.json` and deployed `build-info.json` for source provenance.
