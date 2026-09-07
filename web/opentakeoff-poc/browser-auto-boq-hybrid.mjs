import { extractBrowserAutoBoq as extractBrowser } from './browser-auto-boq.mjs';
import { configuredBackendUrl, tryPythonAutoBoq } from './browser-backend-runtime.mjs';

const EVIDENCE_RUNTIME_EVENT = 'boq-evidence:runtime-result';
const EVIDENCE_RUNTIME_STATE = '__BOQ_EVIDENCE_RUNTIME__';

function publishEvidenceRuntime(result, { bytes, name }) {
  try {
    const pdfBytes = bytes instanceof Uint8Array
      ? bytes.slice()
      : new Uint8Array(bytes || []).slice();
    const detail = {
      result,
      name,
      pdfBytes,
      fingerprint: `${result?.document?.sha256 || ''}:${name || result?.document?.name || ''}:${pdfBytes.byteLength}`,
    };
    // Persist the latest runtime evidence in the page as well as emitting an
    // event. The BOQ table is rendered immediately after extraction returns, so
    // the viewer can recover deterministically even if the event arrived before
    // the table's MutationObserver saw the final rows.
    globalThis[EVIDENCE_RUNTIME_STATE] = detail;
    if (typeof globalThis?.dispatchEvent === 'function' && typeof globalThis?.CustomEvent === 'function') {
      globalThis.dispatchEvent(new globalThis.CustomEvent(EVIDENCE_RUNTIME_EVENT, { detail }));
    }
  } catch (error) {
    // Evidence UI is supplementary. Never make quantity extraction fail because
    // a browser cannot publish the viewer state/event.
  }
  return result;
}

export async function extractBrowserAutoBoq({ bytes, name = 'uploaded.pdf', pdfjs, maxPages = 150, backendUrl = '', fetchImpl = fetch }) {
  const endpoint = backendUrl || configuredBackendUrl({
    search: globalThis?.location?.search || '',
    storage: globalThis?.localStorage || null,
    globalValue: globalThis?.AUTO_BOQ_BACKEND_URL || globalThis?.__AUTO_BOQ_BACKEND_URL__ || '',
  });
  if (endpoint) {
    try {
      const backend = await tryPythonAutoBoq({ endpoint, bytes, name, fetchImpl });
      if (backend.status === 'PUBLISHED_VALIDATED_PROFILE_BOQ' && backend.result) {
        return publishEvidenceRuntime({
          ...backend.result,
          runtime_execution: {
            engine: 'python-v8.19-profile-gated',
            mode: 'BACKEND_VALIDATED_PROFILE',
            backend_endpoint_configured: true,
            browser_fallback_used: false,
          },
        }, { bytes, name });
      }
      if (backend.status === 'PUBLISHED_GENERIC_INFERRED_BOQ' && backend.result) {
        return publishEvidenceRuntime({
          ...backend.result,
          runtime_execution: {
            engine: 'python-generic-vector-sanitary-v0',
            mode: 'BACKEND_GENERIC_INFERRED',
            backend_endpoint_configured: true,
            browser_fallback_used: false,
          },
        }, { bytes, name });
      }
    } catch (error) {
      // Any backend transport/schema/reference-isolation failure discards all
      // backend quantities and continues only with the fail-closed browser path.
    }
  }
  const result = await extractBrowser({ bytes, name, pdfjs, maxPages });
  return publishEvidenceRuntime({
    ...result,
    runtime_execution: {
      engine: 'browser-pdfjs-fail-closed',
      mode: endpoint ? 'BACKEND_WITHHELD_OR_FAILED_BROWSER_FALLBACK' : 'BROWSER_ONLY_NO_BACKEND_CONFIGURED',
      backend_endpoint_configured: Boolean(endpoint),
      browser_fallback_used: true,
    },
  }, { bytes, name });
}
