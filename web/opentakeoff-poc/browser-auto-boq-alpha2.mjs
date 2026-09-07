import {
  extractBrowserAutoBoq as extractBaseAutoBoq,
  groupPdfTextItems,
} from './browser-auto-boq.mjs';
import { analyzeBrowserPipeGeometrySafe } from './browser-pipe-geometry-safe.mjs';

function pipeGeometryReason(geometry, tagCount) {
  const pages = geometry?.pages || [];
  if (!pages.length) {
    return `พบ explicit pipe-size/system tags ${tagCount} จุด แต่ยังไม่มี primary-plan page ที่มี visible OCG/CAD pipe layer + scale + tag geometry ครบ จึง WITHHELD pipe length`;
  }
  const details = pages.map(page => {
    const pct = Math.round(Number(page?.diameter_coverage?.assigned_fraction || 0) * 10000) / 100;
    const scale = page?.scale?.unique_ratio ? `1:${page.scale.unique_ratio}` : page?.scale?.status || 'NO_SCALE';
    const straight = Number(page?.vector_segment_count || 0);
    const raw = Number(page?.raw_vector_segment_count || straight);
    return `p.${page.page} straight ${straight}/${raw} seg · coverage ${pct}% · ${scale}`;
  }).join('; ');
  return `Browser Alpha2 trace visible OCG/vector network แบบ straight-only แล้ว (${details}) แต่ pipe length ยัง WITHHELD จน primary diameter coverage ≥95%, scale ชัด, tag association ไม่กำกวม และ unsupported curved geometry ได้รับการพิสูจน์ว่าไม่ใช่ pipe run`;
}

async function rebuildSafePipeDiagnostics({ data, pdfjs, result }) {
  const pageRoles = result?.diagnostics?.page_role_classification || [];
  const pipeTags = result?.diagnostics?.pipe_size_system_tags_evidence_only || [];
  const pagesNeeded = [...new Set(pageRoles
    .filter(role => role?.role === 'primary_plan')
    .map(role => Number(role.page))
    .filter(page => Number.isInteger(page) && pipeTags.some(tag => Number(tag?.page) === page)))]
    .sort((a, b) => a - b);
  if (!pagesNeeded.length) {
    return {
      detector: 'browser_pipe_geometry_alpha2',
      normalization: 'SAFE_VISIBLE_STRAIGHT_SEMANTIC_V1',
      status: 'WITHHELD_NO_PRIMARY_PLAN_PIPE_TAG_PAGES',
      release_status: 'WITHHELD_ALPHA2_DIAGNOSTIC_ONLY',
      min_primary_diameter_coverage: 0.95,
      analyzed_primary_pages: [],
      diagnostic_candidate_pages: [],
      pages: [],
      reference_used_for_generation: false,
    };
  }

  const doc = await pdfjs.getDocument({ data: data.slice() }).promise;
  try {
    const pages = [];
    for (const pageNo of pagesNeeded) {
      const page = await doc.getPage(pageNo);
      const content = await page.getTextContent({ disableNormalization: false });
      pages.push({ page: pageNo, lines: groupPdfTextItems(content.items) });
      page.cleanup?.();
    }
    const geometry = await analyzeBrowserPipeGeometrySafe({ doc, pdfjs, pages, pageRoles, pipeTags });
    geometry.detector = 'browser_pipe_geometry_alpha2';
    geometry.normalization = 'SAFE_VISIBLE_STRAIGHT_SEMANTIC_V1';
    return geometry;
  } finally {
    await doc.destroy?.();
  }
}

export async function extractBrowserAutoBoq({ bytes, name = 'uploaded.pdf', pdfjs, maxPages = 150 }) {
  const data = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes || []);
  const result = await extractBaseAutoBoq({ bytes: data.slice(), name, pdfjs, maxPages });
  let geometry;
  try {
    geometry = await rebuildSafePipeDiagnostics({ data, pdfjs, result });
  } catch (error) {
    geometry = {
      detector: 'browser_pipe_geometry_alpha2',
      normalization: 'SAFE_VISIBLE_STRAIGHT_SEMANTIC_V1',
      status: 'WITHHELD_SAFE_GEOMETRY_ANALYZER_ERROR',
      release_status: 'WITHHELD_ALPHA2_DIAGNOSTIC_ONLY',
      error: String(error?.message || error),
      analyzed_primary_pages: [],
      pages: [],
      reference_used_for_generation: false,
    };
  }

  result.source_policy = {
    ...(result.source_policy || {}),
    generic_pipe_length_min_primary_diameter_coverage: 0.95,
    generic_pipe_length_release_status: 'WITHHELD_ALPHA2_DIAGNOSTIC_ONLY',
    pipe_geometry_normalization: 'SAFE_VISIBLE_STRAIGHT_SEMANTIC_V1',
  };
  result.diagnostics = {
    ...(result.diagnostics || {}),
    pipe_geometry_alpha2: geometry,
  };
  const withheld = result?.coverage?.withheld_detectors || [];
  const pipeWithheld = withheld.find(item => item?.name === 'SAN-PIPE-LENGTH');
  if (pipeWithheld) {
    pipeWithheld.reason = pipeGeometryReason(
      geometry,
      (result?.diagnostics?.pipe_size_system_tags_evidence_only || []).length,
    );
  }
  if (Array.isArray(result.limitations)) {
    result.limitations = result.limitations.filter(item => !String(item).startsWith('Alpha2 traces OCG/CAD pipe vectors'));
    result.limitations.push('Alpha2 diagnostics use visible OCGs only, exclude curved CAD figures from the measured straight-run denominator, and merge duplicate OCG ids only when system + canonical CAD layer name agree. Curved evidence remains a release blocker.');
  }
  return result;
}
