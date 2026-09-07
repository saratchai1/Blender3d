const STORAGE_KEY = 'blender3d.auto_boq_backend_url';
const TIMEOUT_MS = 300000;
const BUSY_RETRY_ATTEMPTS = 45;
const BUSY_RETRY_DELAY_MS = 3000;
const RETRYABLE_EDGE_STATUSES = new Set([502, 503, 504]);
export const DEFAULT_BACKEND_URL = 'https://blender3d-auto-boq.onrender.com/api/auto-boq';

function cleanEndpoint(raw) {
  const value = String(raw || '').trim();
  if (!value) return '';
  try {
    const url = new URL(value, globalThis.location?.href || 'https://example.invalid/');
    if (!/^https?:$/.test(url.protocol)) return '';
    return url.href;
  } catch {
    return '';
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export function configuredBackendUrl({ search = '', storage = null, globalValue = '', defaultValue = DEFAULT_BACKEND_URL } = {}) {
  const params = new URLSearchParams(String(search || '').replace(/^\?/, ''));
  const query = params.get('boq_backend');
  if (query && /^(?:off|none|disabled)$/i.test(String(query).trim())) return '';
  const fromQuery = cleanEndpoint(query);
  if (fromQuery) {
    try { storage?.setItem?.(STORAGE_KEY, fromQuery); } catch {}
    return fromQuery;
  }
  const fromGlobal = cleanEndpoint(globalValue);
  if (fromGlobal) return fromGlobal;
  try {
    const fromStorage = cleanEndpoint(storage?.getItem?.(STORAGE_KEY));
    if (fromStorage) return fromStorage;
  } catch {}
  return cleanEndpoint(defaultValue);
}

export async function tryPythonAutoBoq({
  endpoint,
  bytes,
  name,
  fetchImpl = globalThis.fetch,
  timeoutMs = TIMEOUT_MS,
  busyRetryAttempts = BUSY_RETRY_ATTEMPTS,
  busyRetryDelayMs = BUSY_RETRY_DELAY_MS,
  sleepImpl = sleep,
}) {
  const url = cleanEndpoint(endpoint);
  if (!url) return { status: 'SKIPPED_NO_BACKEND', result: null };
  const payload = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes || []);
  if (!payload.byteLength) return { status: 'SKIPPED_EMPTY_PDF', result: null };
  if (typeof fetchImpl !== 'function') throw new Error('Python backend fetch is unavailable');

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const maxAttempts = Math.max(1, Number(busyRetryAttempts) || 1);
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      const response = await fetchImpl(url, {
        method: 'POST',
        headers: {
          'content-type': 'application/pdf',
          'x-file-name': String(name || 'uploaded.pdf'),
        },
        body: payload,
        signal: controller.signal,
      });
      if (response.status === 429) {
        if (attempt >= maxAttempts) throw new Error(`Python backend busy after ${attempt} attempts`);
        const retryAfter = Number(response.headers?.get?.('retry-after'));
        const delay = Number.isFinite(retryAfter) && retryAfter > 0
          ? retryAfter * 1000
          : Math.max(0, Number(busyRetryDelayMs) || 0);
        await sleepImpl(delay);
        continue;
      }
      if (RETRYABLE_EDGE_STATUSES.has(response.status)) {
        if (attempt >= maxAttempts) throw new Error(`Python backend edge HTTP ${response.status} after ${attempt} attempts`);
        await sleepImpl(Math.max(0, Number(busyRetryDelayMs) || 0));
        continue;
      }
      if (!response.ok) throw new Error(`Python backend HTTP ${response.status}`);
      const result = await response.json();
      if (result?.source_policy?.reference_used_for_generation !== false) {
        throw new Error('Python backend reference isolation failed');
      }
      const status = String(result?.runtime_status || 'WITHHELD_BACKEND_RESULT');
      if (status === 'WITHHELD_UNREGISTERED_DRAWING_PROFILE' || status === 'WITHHELD_GENERIC_INFERENCE') {
        return { status, result: null, backend_result: result };
      }
      if (!['PUBLISHED_VALIDATED_PROFILE_BOQ', 'PUBLISHED_GENERIC_INFERRED_BOQ'].includes(status)) {
        return { status, result: null, backend_result: result };
      }
      if (!Array.isArray(result.rows) || !result.rows.length) throw new Error('Python backend published status without BOQ rows');
      return { status, result };
    }
    throw new Error('Python backend busy retry loop exhausted');
  } finally {
    clearTimeout(timer);
  }
}

export const BACKEND_STORAGE_KEY = STORAGE_KEY;
export const BACKEND_BUSY_RETRY_ATTEMPTS = BUSY_RETRY_ATTEMPTS;
export const BACKEND_BUSY_RETRY_DELAY_MS = BUSY_RETRY_DELAY_MS;
