# SOLSTICE 14 — GitHub Pages deployment

The jsDelivr HTML link previously supplied is NOT a deployed website. This repository now has a dedicated Pages build/test/deploy workflow: `.github/workflows/pages.yml`.

## One-time repository setting

A repository administrator must open `Settings > Pages > Build and deployment > Source` and select **GitHub Actions**. Then rerun the failed `deploy` job in the `Deploy SOLSTICE 14 to GitHub Pages` workflow, or run that workflow manually on `main`.

The connected GitHub actions exposed to this chat do not include a repository Pages settings write action. The workflow intentionally does not attempt to elevate its token or embed an administrator credential. If Pages is not enabled, the deploy job stops with a clear error; a passing build alone does not mean the site is published.

Expected URL after a successful deployment: `https://saratchai1.github.io/Blender3d/`. Confirm the successful deployment output and HTTP response before treating that URL as live.

## What is published

`node web/office_10000sqm/tools/build-pages.mjs` creates `.generated/pages` with a root HTML entry, a `.nojekyll` marker, a source-commit/asset-hash manifest, the presentation and viewer, and existing GLB/IFC downloads. Only explicit public website files are copied; no source configuration, environment files, Python runtime or credentials are published.

All presentation runtime resources use relative same-origin URLs. The actual viewer is loaded from `index.html`, so it does not depend on a stale generated standalone document or an HTML file served as plain text by a CDN. No JavaScript `fetch`/`srcdoc` workaround is used.

Presentation repairs include full-height background 3D without the viewer sidebar, a real renderer-ready/error state, visible mobile Explore/Night controls, lazy loading and releasing of the second viewer, and resetting exploded floors when scrolling backwards.

## Verification

The workflow first runs the existing 13 numerical model tests, then the new `pages_smoke.py` test against an HTTP server at `/Blender3d/`. It checks `text/html`, redirects/relative paths, WebGL rendering, mobile width, chapter changes, reverse-scroll reset, day/night, opening/closing the interactive viewer, and an actual IFC download. Screenshots and a JSON report are saved in the `solstice-pages-qa` artifact. Tests use Chromium with a mobile viewport, not a physical iPhone or Safari certification.

Local commands:

```sh
node web/office_10000sqm/tools/build-pages.mjs
python -m pip install playwright==1.57.0
python -m playwright install chromium
python web/office_10000sqm/tools/pages_smoke.py --root .generated/pages
```

The building geometry, conceptual IFC, and source quantity definitions are unchanged by this hosting repair. No photorealistic rendering, energy compliance, validated tender BOQ, or IFC quality certification is claimed here.

References: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site and https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
