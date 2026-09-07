import assert from 'node:assert/strict';
import test from 'node:test';
import { BACKEND_STORAGE_KEY, configuredBackendUrl, tryPythonAutoBoq } from './browser-backend-runtime.mjs';

function storageStub(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: key => data.has(key) ? data.get(key) : null,
    setItem: (key, value) => data.set(key, String(value)),
    data,
  };
}

function response(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

test('query backend URL wins and persists for later uploads', () => {
  const storage = storageStub();
  const url = configuredBackendUrl({ search: '?boq_backend=https%3A%2F%2Fboq.example%2Fapi%2Fauto-boq', storage });
  assert.equal(url, 'https://boq.example/api/auto-boq');
  assert.equal(storage.data.get(BACKEND_STORAGE_KEY), url);
  assert.equal(configuredBackendUrl({ storage }), url);
});

test('published validated backend result is accepted only with reference isolation', async () => {
  const calls = [];
  const result = await tryPythonAutoBoq({
    endpoint: 'https://boq.example/api/auto-boq',
    bytes: new Uint8Array([1, 2, 3]),
    name: 'x.pdf',
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return response(200, {
        runtime_status: 'PUBLISHED_VALIDATED_PROFILE_BOQ',
        source_policy: { reference_used_for_generation: false },
        rows: [{ id: 'SAN-PIPE-CW-DN20', quantity: 1, unit: 'm' }],
      });
    },
  });
  assert.equal(result.status, 'PUBLISHED_VALIDATED_PROFILE_BOQ');
  assert.equal(result.result.rows.length, 1);
  assert.equal(calls[0].init.headers['content-type'], 'application/pdf');
  assert.equal(calls[0].init.headers['x-file-name'], 'x.pdf');
});

test('unregistered drawing profile falls through to browser instead of borrowing evidence', async () => {
  const result = await tryPythonAutoBoq({
    endpoint: 'https://boq.example/api/auto-boq',
    bytes: new Uint8Array([1]),
    name: 'other.pdf',
    fetchImpl: async () => response(200, {
      runtime_status: 'WITHHELD_UNREGISTERED_DRAWING_PROFILE',
      source_policy: { reference_used_for_generation: false },
      rows: [],
    }),
  });
  assert.equal(result.status, 'WITHHELD_UNREGISTERED_DRAWING_PROFILE');
  assert.equal(result.result, null);
});

test('backend that cannot prove reference isolation is rejected', async () => {
  await assert.rejects(() => tryPythonAutoBoq({
    endpoint: 'https://boq.example/api/auto-boq',
    bytes: new Uint8Array([1]),
    fetchImpl: async () => response(200, {
      runtime_status: 'PUBLISHED_VALIDATED_PROFILE_BOQ',
      source_policy: { reference_used_for_generation: true },
      rows: [{ id: 'bad' }],
    }),
  }), /reference isolation failed/);
});

test('no configured backend is a clean browser-only no-op', async () => {
  const result = await tryPythonAutoBoq({ endpoint: '', bytes: new Uint8Array([1]), fetchImpl: null });
  assert.equal(result.status, 'SKIPPED_NO_BACKEND');
});
