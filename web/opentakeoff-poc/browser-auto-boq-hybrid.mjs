import { extractBrowserAutoBoq as extractBrowser } from './browser-auto-boq.mjs';
import { configuredBackendUrl, tryPythonAutoBoq } from './browser-backend-runtime.mjs';

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
        return {
          ...backend.result,
          runtime_execution: {
            engine: 'python-v8.19-profile-gated',
            mode: 'BACKEND_VALIDATED_PROFILE',
            backend_endpoint_configured: true,
            browser_fallback_used: false,
          },
        };
      }
    } catch (error) {
      // Fail open only to the existing fail-closed browser detector. No backend
      // quantity is retained after any transport/schema/reference-isolation error.
    }
  }
  const result = await extractBrowser({ bytes, name, pdfjs, maxPages });
  return {
    ...result,
    runtime_execution: {
      engine: 'browser-pdfjs-fail-closed',
      mode: endpoint ? 'BACKEND_WITHHELD_OR_FAILED_BROWSER_FALLBACK' : 'BROWSER_ONLY_NO_BACKEND_CONFIGURED',
      backend_endpoint_configured: Boolean(endpoint),
      browser_fallback_used: true,
    },
  };
}
