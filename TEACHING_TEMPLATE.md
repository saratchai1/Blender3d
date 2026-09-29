# Blender Architecture Teaching Template — staging branch

This branch is reserved for the clean teaching template requested for the SOLSTICE 14 workflow.

Target repository name: `saratchai1/blender-architecture-template`

The prepared template includes:
- JSON building spec as a single source of truth
- Blender 4.5 LTS headless procedural modeling
- Eevee / Cycles animation pipeline
- GLB export
- IFC4 export with IfcOpenShell
- Concept BOQ CSV
- Interactive Three.js viewer
- GitHub Pages workflow
- CI and manual animation workflow
- Thai teaching guide

Important: Blender is not installed permanently in GitHub. The Actions runner downloads Blender for each relevant run, produces artifacts, and is then discarded.

The complete ready-to-publish source bundle was generated and validated outside this branch. This staging branch exists so the teaching work remains separate from `main`.
