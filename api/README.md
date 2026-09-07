# Automatic BOQ Python Runtime API

`POST /api/auto-boq` accepts a raw `application/pdf` request body with optional `X-File-Name`.

Safety contract:
- exact SHA-256 profile gate before any profile-specific evidence is used;
- validated Family4 SHA runs Python `auto_boq_v8_19` and retains the existing source-page/reference isolation gates;
- unknown PDFs return `WITHHELD_UNREGISTERED_DRAWING_PROFILE` with zero backend rows so the client can continue with the browser fail-closed runtime;
- no Family4 page roles, detail links, roof levels, valve evidence, or reference quantities are borrowed for a different PDF.

`GET /api/auto-boq` returns runtime health/capability metadata.
