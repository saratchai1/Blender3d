const STORAGE_KEY = 'blender3d.auto_boq_backend_url';
const TIMEOUT_MS = 120000;

function cleanEndpoint(raw) {
  const value = String(raw || '').trim();
  if (!value) return '';
  try {
    const url = new URL(value, location?.href || 'https://example.invalid/');
    if (!/^https?:$/.test(url.protocol)) return '';
    return url.href;
  } catch {
    return '';
  }
}

export function configuredBackendUrl({ search = '', storage = null, globalValue = '' } = {}) {
  const query = new URLSearchParams(String(search || '').replace(/^\?/, '')).get('boq_backend');
  const fromQuery = cleanEndpoint(query);
  if (fromQuery) {
    try { storage?.setItem?.(STORAGE_KEY, fromQuery); } catch {}
    return fromQuery;
  }
  const fromGlobal = cleanEndpoint(globalValue);
  if (fromGlobal) return fromGlobal;
  try {
    return cleanEndpoint(storage?.getItem?.(STORAGE_KEY));
  } catch {
    return '';
  }
}

export async function tryPythonAutoBoq({ endpoint, bytes, name, fetchImpl = fetch, timeoutMs = TIMEOUT_MS }) {
  const url = cleanEndpoint(endpoint);
  if (!url) return { status: 'SKIPPED_NO_BACKEND', result: null };
  const payload = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes || []);
  if (!payload.byteLength) return { status: 'SKIPPED_EMPTY_PDF', result: null };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(url, {
      method: 'POST',
      headers: {
        'content-type': 'application/pdf',
        'x-file-name': String(name || 'uploaded.pdf'),
      },
      body: payload,
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Python backend HTTP ${response.status}`);
    const result = await response.json();
    if (result?.source_policy?.reference_used_for_generation !== false) {
      throw new Error('Python backend reference isolation failed');
    }
    if (result?.runtime_status === 'WITHHELD_UNREGISTERED_DRAWING_PROFILE') {
      return { status: 'WITHHELD_UNREGISTERED_DRAWING_PROFILE', result: null, backend_result: result };
    }
    if (result?.runtime_status !== 'PUBLISHED_VALIDATED_PROFILE_BOQ') {
      return { status: String(result?.runtime_status || 'WITHHELD_BACKEND_RESULT'), result: null, backend_result: result };
    }
    if (!Array.isArray(result.rows) || !result.rows.length) throw new Error('Python backend published status without BOQ rows');
    return { status: 'PUBLISHED_VALIDATED_PROFILE_BOQ', result };
  } finally {
    clearTimeout(timer);
  }
}

export const BACKEND_STORAGE_KEY = STORAGE_KEY;
