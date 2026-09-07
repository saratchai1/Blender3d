from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / 'integrations' / 'opentakeoff'
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from runtime_backend import MAX_UPLOAD_BYTES, run_registered_pdf

app = FastAPI(title='Automatic BOQ Python Runtime', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'https://saratchai1.github.io',
        'http://127.0.0.1:8000',
        'http://localhost:8000',
    ],
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['content-type', 'x-file-name'],
)


def safe_name(raw: str | None) -> str:
    name = Path(str(raw or 'uploaded.pdf')).name
    name = re.sub(r'[^A-Za-z0-9._ -]+', '_', name).strip() or 'uploaded.pdf'
    if not name.lower().endswith('.pdf'):
        name += '.pdf'
    return name[:160]


@app.get('/api/auto-boq')
def health() -> dict:
    return {
        'status': 'ok',
        'engine': 'python-v8.19-profile-gated',
        'max_upload_bytes': MAX_UPLOAD_BYTES,
        'unknown_profile_policy': 'WITHHOLD_AND_BROWSER_FALLBACK',
        'reference_used_for_generation': False,
    }


@app.post('/api/auto-boq')
async def automatic_boq(request: Request) -> dict:
    content_type = str(request.headers.get('content-type') or '').split(';', 1)[0].strip().lower()
    if content_type != 'application/pdf':
        raise HTTPException(status_code=415, detail='Send the PDF as raw application/pdf request body')
    declared = request.headers.get('content-length')
    if declared:
        try:
            if int(declared) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail='PDF exceeds runtime upload limit')
        except ValueError:
            pass
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail='Empty PDF upload')
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail='PDF exceeds runtime upload limit')
    if not body.startswith(b'%PDF-'):
        raise HTTPException(status_code=400, detail='Upload does not start with a PDF signature')

    filename = safe_name(request.headers.get('x-file-name'))
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix='auto-boq-', suffix='.pdf', delete=False) as fh:
            fh.write(body)
            tmp_path = Path(fh.name)
        result = run_registered_pdf(tmp_path)
        if isinstance(result.get('document'), dict):
            result['document']['name'] = filename
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
