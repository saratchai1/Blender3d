import assert from 'node:assert/strict';
import test from 'node:test';
import { configuredBackendUrl, DEFAULT_BACKEND_URL, tryPythonAutoBoq } from './browser-backend-runtime.mjs';

test('verified Render backend is the default when no override is configured', () => {
  assert.equal(configuredBackendUrl(), DEFAULT_BACKEND_URL);
  assert.equal(DEFAULT_BACKEND_URL, 'https://blender3d-auto-boq.onrender.com/api/auto-boq');
});

test('query, global and stored backends override the default in that order', () => {
  const storage = {
    value: 'https://stored.example/api/auto-boq',
    getItem() { return this.value; },
    setItem(_key, value) { this.value = value; },
  };
  assert.equal(
    configuredBackendUrl({ search: '?boq_backend=https%3A%2F%2Fquery.example%2Fapi', storage, globalValue: 'https://global.example/api' }),
    'https://query.example/api',
  );
  assert.equal(configuredBackendUrl({ storage, globalValue: 'https://global.example/api' }), 'https://global.example/api');
  assert.equal(configuredBackendUrl({ storage }), 'https://query.example/api');
});

test('boq_backend=off explicitly disables network for deterministic offline fallback', () => {
  const storage = { getItem: () => DEFAULT_BACKEND_URL };
  assert.equal(configuredBackendUrl({ search: '?boq_backend=off', storage }), '');
  assert.equal(configuredBackendUrl({ search: '?boq_backend=disabled', storage }), '');
});

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

test('generic inferred backend response is accepted', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({
    runtime_status: 'PUBLISHED_GENERIC_INFERRED_BOQ',
    runtime_profile: 'generic-inferred-vector-sanitary-v0',
    source_policy: { reference_used_for_generation: false },
    rows: [{ id: 'GEN-SAN-PIPE-CW-DN20', quantity: 7.056, unit: 'm' }],
  }) });
  const out = await tryPythonAutoBoq({ endpoint: 'https://example.com/api/auto-boq', bytes: new Uint8Array([1]), name: 'generic.pdf', fetchImpl });
  assert.equal(out.status, 'PUBLISHED_GENERIC_INFERRED_BOQ');
  assert.equal(out.result.rows[0].id, 'GEN-SAN-PIPE-CW-DN20');
});

test('withheld generic inference returns no backend rows so caller can fall back', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({
    runtime_status: 'WITHHELD_GENERIC_INFERENCE',
    source_policy: { reference_used_for_generation: false },
    rows: [],
  }) });
  const out = await tryPythonAutoBoq({ endpoint: 'https://example.com/api/auto-boq', bytes: new Uint8Array([1]), name: 'x.pdf', fetchImpl });
  assert.equal(out.status, 'WITHHELD_GENERIC_INFERENCE');
  assert.equal(out.result, null);
});

test('reference leakage is rejected before any backend result can be used', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({
    runtime_status: 'PUBLISHED_GENERIC_INFERRED_BOQ',
    source_policy: { reference_used_for_generation: true },
    rows: [{ id: 'BAD' }],
  }) });
  await assert.rejects(() => tryPythonAutoBoq({ endpoint: 'https://example.com/api/auto-boq', bytes: new Uint8Array([1]), fetchImpl }), /reference isolation failed/);
});
