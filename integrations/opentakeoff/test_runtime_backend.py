#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import runtime_backend as runtime


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        unknown = Path(td) / 'unknown.pdf'
        unknown.write_bytes(b'%PDF-1.4\n% unregistered test fixture\n')
        result = runtime.run_registered_pdf(unknown)
        assert result['runtime_status'] == 'WITHHELD_UNREGISTERED_DRAWING_PROFILE', result
        assert result['rows'] == [], result
        assert result['source_policy']['reference_used_for_generation'] is False, result
        assert result['source_policy']['profile_hash_gate'] is True, result
        assert result['source_policy']['unknown_profile_fallback'] == 'BROWSER_FAIL_CLOSED_RUNTIME', result
        assert result['profile'] is None and result['engine'] is None, result

    family = runtime.PROFILE_REGISTRY[runtime.FAMILY4_SHA256]
    assert family.id == 'family4-v8.19'
    assert family.profile.is_file()
    assert family.roof_evidence.is_file()
    assert family.equipment_evidence.is_file()
    print('AUTO_BOQ_RUNTIME_BACKEND_UNIT_PASS', json.dumps({
        'unknown_pdf': 'withheld',
        'profile_hash_gate': True,
        'registered_profiles': [p.id for p in runtime.PROFILE_REGISTRY.values()],
    }))


if __name__ == '__main__':
    main()
