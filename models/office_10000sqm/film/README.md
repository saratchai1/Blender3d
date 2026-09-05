# SOLSTICE 14 — offline architectural film

This is the **Blender/Cycles video path**, separate from both the WebGL viewer and the Three.js cinematic web application. It renders the actual moving camera through 3D geometry. It does not use image generation, fixed-image zoom/pan, optical-flow frame synthesis, or resolution upscaling.

## Source and scope

The building geometry is generated from the repository's existing `model.mjs` via `tools/build.mjs`. `build_film.py` asserts 14 storeys and a 10,000 m² conceptual floor-plate sum. It converts the source coordinate convention into Blender Z-up coordinates and retains a SHA-256 digest of the semantic scene.

Visual materials, lighting, context, leaf geometry, landscaping and the entry sign are presentation-only. They **do not update IFC or BOQ quantities**. The film is not proof of construction readiness, facade engineering, statutory GFA, or energy performance. It is rendered by Blender, not Twinmotion or 3ds Max.

## Components

- `build_film.py`: metric source geometry, physically shaded materials, procedural botanical geometry, physical daylight, six separately saved native camera scenes.
- `finish_scene.py`: reviewed opening/closing framing, guided OpenImageDenoise compositor using normal/albedo passes, glass/bronze refinements, landscape context and blue-hour lighting.
- `render_chunk.py`: renders 32 **actual native frames** for one of three parts of a 96-frame shot. Logs every frame's camera transform, render duration and PNG SHA-256.
- `render_shot.py`: optional whole-shot renderer; its sample default is independent of the final chunk pipeline.
- `assemble_chunks.py`: validates all 18 chunks, requires 96 distinct camera positions and rendered-frame hashes for each of six shots, verifies H.264 frame counts and decodes the final file before publication.

### Intended deliverables

The final pipeline targets a 24-second, 1280 × 720, 24 fps film with 576 native Cycles frames. It uses 24 samples and guided denoising. It produces both a clean master and a presentation version with restrained titles and start/end fades. There is no audio track.

A scene file or six look-development images **must not be represented as a completed movie**. Completion requires the final MP4 plus `render-report.json` with `status: PASS`, a matching video SHA-256 and successful full-file decode.

The workflow publishes the completed presentation MP4 and audit to `web/office_10000sqm/film/` only after those gates pass. The native six-scene `.blend` package and clean master are retained as Actions artifacts. Artifact retention is finite; the procedural source scripts in Git remain the durable reconstruction path.

## Camera sequence

| Shot | Time | Subject |
|---|---|---|
| 01 | 00:00–00:04 | Southern approach / whole-building view |
| 02 | 00:04–00:08 | Arrival, entry canopy and plaza |
| 03 | 00:08–00:12 | Bronze and glass facade |
| 04 | 00:12–00:16 | Level 10 sky garden |
| 05 | 00:16–00:20 | Roof and photovoltaic array |
| 06 | 00:20–00:24 | Evening exterior |

Each shot has its own camera animation, with frames 1–96. The source building is never exploded or scaled for this film.

## Rebuild native scenes locally

Requires Node and Blender 4.5.3-compatible APIs. No external texture, plant library, paid render service, user-computer connection or runtime API key is used.

```sh
node web/office_10000sqm/tools/build.mjs
blender --background -t 4 --python models/office_10000sqm/film/build_film.py -- \
  --scene .generated/office_10000sqm/office.scene.json \
  --output .generated/film-original
blender --background -t 4 --python models/office_10000sqm/film/finish_scene.py -- \
  --input .generated/film-original --output .generated/film-final --proof
```

Open a resulting `.blend` in Blender, enter camera view, and play its timeline. Use Render Animation to render the moving camera. Use the PNG-sequence output before encoding to H.264; a failed render can then be resumed without discarding the entire movie. The `.blend` settings can be adjusted for different sampling and output resolution.

The current Actions final-render workflow uses the native-scene artifact from its recorded look-development run as an initial cache. After that artifact expires, regenerate it or use the local commands above; do not assume an expired artifact is a permanent asset.

## Web-player scope

`web/office_10000sqm/film/index.html` is an HTML5 MP4 player, not a still-image slideshow and not a WebGL renderer. It supports native controls, in-page playback, fullscreen where the browser permits it, six chapter buttons and a direct download. A source commit alone does not establish that this route has been published to GitHub Pages.

## Reference

Blender frame-sequence animation workflow: https://docs.blender.org/manual/en/4.5/render/output/animation.html
