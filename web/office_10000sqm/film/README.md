# SOLSTICE 14 — completed native Cycles animation

`SOLSTICE-14-Architectural-Film.mp4` is a completed 24-second architectural animation, not a still-image slideshow. It contains **576 real Cycles-rendered frames** at **1280 × 720 / 24 fps**, covering six animated cameras: overview, arrival, facade, Level 10 garden, roof and evening.

- Engine: Blender 4.5.3 LTS / Cycles CPU, guided denoising.
- Encoding: H.264, yuv420p, MP4 faststart.
- Audio: none.
- Presentation MP4 SHA-256: `38cbc1d7162c8ed9250cd0094baa1d56c272b04082a06ee84ecc50f04c8c0a9d`.
- Full frame coverage and native camera transforms: `render-report.json`.
- Completion/assembly run: `33968144059`; original chunk render run: `33965799767`.

The original render completed 17 of 18 chunks. The last garden chunk hit its 40-minute job timeout during its final frame. The recovery workflow rendered that exact segment in eight four-frame slices at the same settings, reusing all other 544 completed frames. Final assembly verified 18 complete chunks, 96 distinct native camera positions per shot, 576 distinct native rendered-frame hashes, exact duration/frame count, and a full video decode. No optical-flow frames, repeated stills, zoom-pan simulation, or resolution upscaling were used.

The six native `.blend` scene files and clean master without title overlays are available in the corresponding Actions artifacts (finite retention). Rebuild scripts are retained under `models/office_10000sqm/film/`.

This is Blender/Cycles output, not a Twinmotion or 3ds Max project. The building is still conceptual BIM; presentation landscape, lighting, context and visual materials do not change IFC/BOQ quantities or demonstrate construction/energy compliance.

## Player

`index.html` plays the actual MP4, with six chapter buttons and native mobile/fullscreen controls. The Pages build copies this directory only when the movie hash agrees with its passed audit. A source commit does not itself prove deployment; use the Pages workflow status and public-site playback test for publication evidence.
