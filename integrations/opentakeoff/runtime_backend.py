#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

FAMILY4_SHA256 = 'f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'
MAX_UPLOAD_BYTES = 30 * 1024 * 1024


@dataclass(frozen=True)
class RuntimeProfile:
    id: str
    sha256: str
    profile: Path
    roof_evidence: Path
    equipment_evidence: Path
    engine: str = 'auto_boq_v8_19'


PROFILE_REGISTRY = {
    FAMILY4_SHA256: RuntimeProfile(
        id='family4-v8.19',
        sha256=FAMILY4_SHA256,
        profile=HERE / 'profiles' / 'family4.json',
        roof_evidence=HERE / 'profiles' / 'family4_roof_level_evidence.json',
        equipment_evidence=HERE / 'profiles' / 'family4_equipment_vertical_evidence.json',
    )
}


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def registered_profile(path: Path) -> RuntimeProfile | None:
    return PROFILE_REGISTRY.get(sha256_path(path))


def _withheld_unregistered(path: Path, digest: str) -> dict[str, Any]:
    return {
        'schema': 'blender3d.auto_boq.runtime.v1',
        'runtime_status': 'WITHHELD_UNREGISTERED_DRAWING_PROFILE',
        'engine': None,
        'profile': None,
        'document': {
            'name': path.name,
            'sha256': digest,
            'bytes': path.stat().st_size,
        },
        'rows': [],
        'source_policy': {
            'reference_used_for_generation': False,
            'profile_hash_gate': True,
            'unknown_profile_fallback': 'BROWSER_FAIL_CLOSED_RUNTIME',
        },
        'limitations': [
            'No validated Python drawing profile matches this exact PDF, so the backend does not borrow Family4 page roles, detail links, roof levels, equipment evidence, or reference quantities.',
            'Client may continue with the browser fail-closed detector; full Python pipe publication remains withheld until a drawing profile is validated or inferred and gated.',
        ],
    }


def run_registered_pdf(path: Path) -> dict[str, Any]:
    path = path.resolve()
    size = path.stat().st_size
    if size <= 0:
        raise ValueError('empty PDF upload')
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(f'PDF upload exceeds {MAX_UPLOAD_BYTES} byte runtime limit')
    if path.suffix.lower() != '.pdf':
        raise ValueError('runtime accepts PDF files only')

    digest = sha256_path(path)
    profile = PROFILE_REGISTRY.get(digest)
    if profile is None:
        return _withheld_unregistered(path, digest)

    import auto_boq_v8_19 as engine

    result = engine.extract(
        path,
        profile.profile,
        profile.roof_evidence,
        profile.equipment_evidence,
    )
    pipe_rows = [r for r in result.get('rows', []) if str(r.get('id', '')).startswith('SAN-PIPE-')]
    pipe_total = round(sum(float(r.get('quantity') or 0.0) for r in pipe_rows), 3)
    if len(result.get('rows', [])) != 27 or len(pipe_rows) != 8 or abs(pipe_total - 92.5) > 1e-6:
        raise RuntimeError(
            f'validated profile regression: rows={len(result.get("rows", []))} pipes={len(pipe_rows)} pipe_total={pipe_total}'
        )
    if result.get('source_policy', {}).get('reference_used_for_generation') is not False:
        raise RuntimeError('reference-generation isolation regression')

    return {
        **result,
        'runtime_status': 'PUBLISHED_VALIDATED_PROFILE_BOQ',
        'runtime_engine': profile.engine,
        'runtime_profile': profile.id,
        'runtime_profile_sha256_gate': digest,
        'runtime_pipe_summary': {
            'published_rows': len(pipe_rows),
            'published_total_m': pipe_total,
        },
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = run_registered_pdf(args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('AUTO_BOQ_RUNTIME_BACKEND_OK', json.dumps({
        'runtime_status': result.get('runtime_status'),
        'rows': len(result.get('rows', [])),
        'runtime_profile': result.get('runtime_profile'),
        'runtime_pipe_summary': result.get('runtime_pipe_summary'),
        'reference_used_for_generation': result.get('source_policy', {}).get('reference_used_for_generation'),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
