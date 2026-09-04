# SOLSTICE 14 — modern tropical office / interactive 3D

Design brief: **10,000 m² total floor area, 14 above-ground storeys**, a modern facade, and an energy-conscious concept. This is an actual, metric, procedural mesh model in an interactive WebGL 2 application — not a rendered image or a mock 3D rotation.

## Open the app

From the repository root:

```sh
python -m http.server 8080
# Open http://localhost:8080/web/office_10000sqm/
```

There is no npm install, CDN dependency, API key, remote font, analytics, paid service or AI call at runtime. The browser must support WebGL 2. A clear error panel appears if it cannot create the graphics context.

Build a single-file offline app, the exact GLB, and the semantic scene:

```sh
node web/office_10000sqm/tools/build.mjs
# .generated/office_10000sqm/index.html
# .generated/office_10000sqm/solstice-14.glb
# .generated/office_10000sqm/office.scene.json
```

The generated HTML can also be deployed unchanged to any static web host. No deployed URL is assumed or fabricated by this document. The `office14` workflow publishes a downloadable bundle under GitHub Actions artifacts and refreshes `web/office_10000sqm/standalone.html` and `assets/solstice-14.glb` after its tests pass on main.

## Design and area schedule

| Floors | Proposed use | Floor plate | Area per floor | Subtotal |
|---|---|---|---:|---:|
| 1 | Lobby, cafe, arrival | 40 × 25 m | 1,000 m² | 1,000 m² |
| 2 | Conference, co-working | 40 × 25 m | 1,000 m² | 1,000 m² |
| 3–12 | Flexible offices; gardens at 5 and 10 | 34 × 20 m | 680 m² | 6,800 m² |
| 13–14 | Executive / meeting suites | 30 × 20 m | 600 m² | 1,200 m² |
| **Total** | **14 occupied levels** | | | **10,000 m²** |

The total is the sum of the rectangular conceptual floor plates. It **includes** two 18 × 4 m covered sky terraces (144 m² total). Enclosed floor-plate area on this basis is 9,856 m², not net lettable office area; stairs, lift core and circulation have not been deducted. The ground site, exterior podium-roof landscaping, solar array and screened roof plant are not extra occupied floors. This is **not a certified statutory GFA measurement**.

Floor-to-floor heights: ground 5.0 m; second 4.5 m; remaining 12 floors 3.8 m. Roof datum is +55.1 m; roof slab, parapet and screened plant rise above it. Height to the plant screen is approximately 58.4 m. The ground/site is a **hypothetical 68 × 58 m plot**, not a surveyed or legally buildable site. No basement/parking structure has been designed.

### Architectural language

Warm ivory slab bands, bronze solar fins with staggered angles, blue-green glazing, recessed gardens at L05 and L10, a landscaped podium roof and a set-back two-storey crown. The model includes a sheltered entry, reflecting pool, small landscape objects, indicative people/vehicles, a lift bank, two conceptual stair enclosures and sample furniture. The stairs/core/furniture are schematic spatial placeholders, not detailed circulation, fire or capacity design.

### Energy strategy — targets, not measured performance

* External shading on all elevations; deeper oriented fins on east/west ends and horizontal shades on the long elevations. The long axis is east–west in the reference orientation.
* Low-E glazing is a design intent, with an initial **SHGC target of 0.25–0.30**, not a specified/certified product. The viewer's glazing shader is an opaque reflective visualization, not an optical/thermal material simulation.
* 96 modeled roof modules at an assumed 450 W each = **43.2 kWp DC nameplate capacity**; this is neither annual yield nor an energy-saving percentage. Panel tilt is about 10° toward south. Structure, access clearances, fire setbacks, stringing, wind uplift, electrical design and inverter sizing are not checked.
* Proposed daylight-responsive dimming, occupancy controls, efficient zoned cooling and floor-level metering are narrative design intent, not implemented building services.
* Sky terraces are separated from the office envelope by modeled glazing returns. Natural ventilation is proposed for outdoor amenity areas, **not** assumed as year-round cooling for enclosed Bangkok offices.

The sun widget uses a simplified declination/equation-of-time geometric approximation at assumed Bangkok coordinates (13.7563° N, 100.5018° E; UTC+7), with four seasonal dates. It changes actual rendered shadows. It is **not** EnergyPlus, weather-file analysis, solar irradiance, daylight autonomy, glare analysis, annual PV yield or validated solar ephemeris. Night lighting is illustrative. No savings percentage, EUI, OTTV compliance, LEED/TREES rating or net-zero claim is made.

Background references (design context, not project validation):
- US DOE, windows: https://www.energy.gov/cmei/buildings/windows
- US DOE, shading/window attachments: https://www.energy.gov/sites/prod/files/2013/11/f5/energy_savings_from_windows_attachments.pdf
- Khronos glTF 2.0: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html

## Interaction

Drag to orbit; wheel/pinch to zoom; Shift/right drag to pan; two-finger touch can zoom/pan. Keyboard arrows orbit; `+`/`-` zoom; `Home` returns to the hero view. Select any of the 14 floor entries or click the massing to inspect a floor. Picking uses conceptual floor bounding boxes rather than a detailed BIM element picker.

Facade and landscape toggles hide actual geometry. Opening the envelope removes glazing and shows indicative furniture. The fin-depth slider rebuilds the fins between 0.4 and 1.5 m. Explode separates storeys **for inspection only**, without modifying design/export elevations. Section removes floors above a chosen level; roof/PV elements disappear with the top floors. Reset restores all defaults. South/east/top presets, day/night, seasonal shadow control, model snapshot and full-design GLB export are provided.

**Export always includes the complete 14-storey design**, regardless of clipped/exploded/hidden display states. The chosen fin depth is retained. One world unit equals one metre. Axes: X east, Y up, Z south. The GLB has shared meshes/materials and per-object floor/layer metadata. Site and building geometry are included; there are no baked textures.

## Blender

In Blender: `File → Import → glTF 2.0` and select the exported `.glb`. For a saved, organized native file in a new Blender process:

```sh
blender --background --python models/office_10000sqm/import_office.py -- \
  --input .generated/office_10000sqm/solstice-14.glb \
  --output .generated/office_10000sqm/solstice-14.blend
```

The script clears only the scene in that Blender process, imports the exact exported geometry, sets metric units, organizes objects into floor collections and saves the `.blend`. It does **not** use Pascal, 3D Gaussian Splatting, or the MCP bridge. Existing house/MCP/Pascal work is unchanged. No live connection to the user's local Blender is assumed. Native `.blend` generation must be run where Blender is installed.

## Source and tests

- `web/office_10000sqm/model.mjs`: shared metric specification, deterministic scene, meshes and sun approximation.
- `renderer.mjs`: instanced WebGL 2 rendering, PCF shadows, camera and floor picking (three shape batches).
- `export.mjs`: dependency-free glTF 2.0 binary exporter.
- `app.mjs`, `index.html`, `style.css`: Thai-first responsive interface.
- `tools/build.mjs`: offline app / GLB / semantic JSON builder.
- `tools/model.test.mjs`: numerical and structural tests.
- `tools/smoke.py`: actual desktop/mobile WebGL browser checks, interactions, screenshots and GLB download.

```sh
node --test web/office_10000sqm/tools/model.test.mjs
node web/office_10000sqm/tools/build.mjs
python -m pip install playwright==1.57.0
python -m playwright install chromium
python web/office_10000sqm/tools/smoke.py \
  --html .generated/office_10000sqm/index.html
```

Set `CHROMIUM_EXECUTABLE` when testing with an existing Chromium. Some Linux software-rendering setups require `xvfb-run -a`. Browser tests at mobile viewport/touch settings are not a physical iPhone/Safari certification. Local review checked desktop and mobile-layout screenshots as well as interactions; workflow artifacts retain test evidence.

## Before this becomes a building

Required next work: actual site/survey/brief; statutory GFA and planning checks; full floor layouts and occupancy; accessible arrival and facilities; fire/egress strategy; structural grid/lateral system; facade maintenance; plant loads and drainage; MEP; parking and transport; cost; detailed landscape and PV design; EnergyPlus/daylight/OTTV studies. The concept is **not for construction, permitting, procurement or energy guarantees**.
