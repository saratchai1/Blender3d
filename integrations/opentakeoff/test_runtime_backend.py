#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import fitz

import runtime_backend as runtime


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        unknown = Path(td) / 'unknown.pdf'
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), 'GENERAL NOTES ONLY')
        doc.save(unknown)
        doc.close()
        result = runtime.run_registered_pdf(unknown)
        assert result['runtime_status'] == 'WITHHELD_GENERIC_INFERENCE', result
        assert result['rows'] == [], result
        assert result['source_policy']['reference_used_for_generation'] is False, result
        assert result['source_policy']['generic_profile_inference'] is True, result
        assert result['runtime_profile_sha256_gate'] is None, result

    family = runtime.PROFILE_REGISTRY[runtime.FAMILY4_SHA256]
    assert family.id == 'family4-v8.19'
    assert family.profile.is_file()
    assert family.roof_evidence.is_file()
    assert family.equipment_evidence.is_file()
    print('AUTO_BOQ_RUNTIME_BACKEND_UNIT_PASS', json.dumps({
        'unknown_pdf': 'generic-inference-withheld',
        'family4_hash_gate': True,
        'registered_profiles': [p.id for p in runtime.PROFILE_REGISTRY.values()],
    }))


if __name__ == '__main__':
    main()
