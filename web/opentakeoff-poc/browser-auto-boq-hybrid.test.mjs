import assert from 'node:assert/strict';
import test from 'node:test';
import { tryPythonAutoBoq } from './browser-backend-runtime.mjs';

test('validated backend response is accepted', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({
    runtime_status: 'PUBLISHED_VALIDATED_PROFILE_BOQ',
    source_policy: { reference_used_for_generation: false },
    rows: [{ id: 'SAN-PIPE-CW-DN15', quantity: 1, unit: 'm' }],
  }) });
  const out = await tryPythonAutoBoq({ endpoint: 'https://example.com/api/auto-boq', bytes: new Uint8Array([1]), name: 'x.pdf', fetchImpl });
  assert.equal(out.status, 'PUBLISHED_VALIDATED_PROFILE_BOQ');
  assert.equal(out.result.rows.length, 1);
});

test('unknown profile returns no backend rows so caller can fall back', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({
    runtime_status: 'WITHHELD_UNREGISTERED_DRAWING_PROFILE',
    source_policy: { reference_used_for_generation: false },
    rows: [],
  }) });
  const out = await tryPythonAutoBoq({ endpoint: 'https://example.com/api/auto-boq', bytes: new Uint8Array([1]), name: 'x.pdf', fetchImpl });
  assert.equal(out.status, 'WITHHELD_UNREGISTERED_DRAWING_PROFILE');
  assert.equal(out.result, null);
});

test('reference leakage is rejected before any backend result can be used', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({
    runtime_status: 'PUBLISHED_VALIDATED_PROFILE_BOQ',
    source_policy: { reference_used_for_generation: true },
    rows: [{ id: 'BAD' }],
  }) });
  await assert.rejects(() => tryPythonAutoBoq({ endpoint: 'https://example.com/api/auto-boq', bytes: new Uint8Array([1]), fetchImpl }), /reference isolation failed/);
});
