# SOLSTICE 14 — real-time architectural film

## Scope

A separate Three.js / WebGL 2 cinematic experience, built from the existing metric `web/office_10000sqm/model.mjs` scene. It does not replace the original data viewer, IFC files, quantity takeoff, house work or OpenTakeoff POC.

Public route after the Pages workflow succeeds: `/Blender3d/cinematic/`. A committed route is not proof of a live deployment; check the workflow's `deploy` and `verify-live` jobs.

## Actual animation

The 72-second loop has six 12-second sequences: overview, entrance, facade, L10 garden, rooftop and blue hour. Each sequence computes a moving camera position along a 3D Bezier rail and looks at an architectural target. Perspective, occlusion and reflections change with that position. Leaves and pool ripples advance with time. This is not a still-image slideshow, CSS photo pan, image-generation output or a video painted onto a plane.

The film autoplays except when the browser reports reduced-motion preference. Play/pause freezes both the film and its environmental animation; the renderer idles when paused until a control changes. Hidden browser tabs do not advance the film. The timeline uses elapsed time rather than assuming a particular frame rate. Free exploration uses OrbitControls on the same scene.

## Presentation

- Physically based glass, bronze, stone, timber, asphalt and photovoltaic materials.
- Procedural texture maps generated locally in the browser.
- Procedural sky, directional sunlight, hemisphere fill and static shadow maps refreshed when the lighting changes.
- A filtered cubemap captured from the actual illustrative environment supplies material reflections. There is no downloaded HDRI photograph.
- Planar reflected geometry and animated distortion on the pool in the high-quality mode.
- Screen-space ambient occlusion on desktop, subtle bloom, ACES tone mapping and anti-aliasing.
- Three lighting looks: daylight, golden light and blue hour. These are presentation settings, not photometric or energy-simulation results.
- Real instanced leaf/branch/grass geometry replaces the original low-poly vegetation representation. Distant context blocks, garden infill glass and decorative lighting are presentation-only details.

This is **not native Twinmotion, 3ds Max, V-Ray, Unreal Lumen or an offline path-traced render**. It does not certify parity with those render engines. Frame rate depends on the actual browser, GPU, resolution and quality setting. The responsive/touch browser check is not certification on a physical iPhone.

## Controls

Film / Explore; play/pause and restart; scrubbable timeline; six scene selectors; three light selectors; High/Balanced mode; fullscreen where supported; hide/restore UI. Information dialog links back to the source and original IFC/data viewer.

Keyboard: Space play/pause; left/right arrows change scenes; H hides controls; F requests fullscreen. Reduced-motion users can explicitly press Play. Browsers without WebGL 2 show an error rather than an invented picture.

## Model relationship

The shared architectural source remains 4,504 primitives, 14 storeys and 10,000 m² of conceptual floor plates, including 144 m² of covered sky gardens. One source unit is one metre, X east / Y up / Z south. Scene rendering uses those placements; the film does not regenerate the IFC or revise the BOQ. Visual materials, foliage and illustrative context must not be treated as additional measured BIM scope.

No claim is made that the existing conceptual IFC is construction-ready, that room interiors are fully designed, or that the earlier conceptual BOQ is suitable for procurement.

## Build

```sh
node web/office_10000sqm/tools/build-pages.mjs
node web/office_10000sqm/cinematic/build.mjs
python -m http.server 8080 --directory .generated/pages
# Open http://localhost:8080/cinematic/
```

The film build packs **three@0.180.0** with npm scripts disabled, verifies the package version, and copies only the runtime and required addon module graph. The MIT license is retained. All runtime module/texture requests are same-origin or locally generated; no runtime CDN, remote font, AI API or paid service is required. Build-time npm availability is required. `THREE_ROOT` may point to an already unpacked 0.180.0 package for an offline build.

## Validation

```sh
python -m pip install playwright==1.57.0
python -m playwright install --with-deps chromium
python web/office_10000sqm/cinematic/smoke.py --root .generated/pages
# Or verify an already deployed route:
python web/office_10000sqm/cinematic/smoke.py --url https://saratchai1.github.io/Blender3d/cinematic/
```

Acceptance covers HTML MIME/status, successful WebGL initialization, actual camera and wind advancement, source geometry counts, distinct six-shot frames, pause idling, scrub, orbit, light/quality controls, information dialog, clean cinema mode, mobile viewport overflow, graphics errors and unexpected external runtime requests. The script writes a partial report on failure. Screenshots are inspection evidence for the animated app, not the requested deliverable.

`.github/workflows/cinematic-qa.yml` retains the portable film and review evidence. `.github/workflows/pages.yml` builds the film together with the existing site and takeoff POC, gates publication on tests, and runs the cinematic tests again against the public HTTPS route after deployment.
