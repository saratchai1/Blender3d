import {
  extractBrowserAutoBoq as extractBaseAutoBoq,
  groupPdfTextItems,
} from './browser-auto-boq.mjs';
import {
  analyzeBrowserPipeGeometrySafe,
  normalizePipeTagDiameter,
} from './browser-pipe-geometry-safe.mjs';

const RAW_PIPE_TAG_RX = /(?:Ø|∅)\s*(\d+(?:\s+\d+\s*\/\s*\d+|\s*\/\s*\d+|\.\d+)?)\s*"?\s*(CW|RL|SW|S|W|V)\b/giu;
const RAW_RFD_RL_RX = /(?:Ø|∅)\s*(\d+(?:\s+\d+\s*\/\s*\d+|\s*\/\s*\d+|\.\d+)?)\s*"?\s*RFD\s*\+\s*RL\b/giu;
const ROW_Y_TOLERANCE_PT = 3;
const MAX_TEXT_GAP_PT = 24;

function round3(value) {
  return Math.round(Number(value) * 1000) / 1000;
}

function positionedChunks(items) {
  const rows = [];
  for (const item of items || []) {
    const text = String(item?.str || '').trim();
    const tr = Array.isArray(item?.transform) ? item.transform : [];
    const x = Number(tr[4]);
    const y = Number(tr[5]);
    if (!text || tr.length < 6 || !Number.isFinite(x) || !Number.isFinite(y)) continue;
    const width = Number(item?.width);
    let row = rows.find(r => Math.abs(r.y - y) <= ROW_Y_TOLERANCE_PT);
    if (!row) {
      row = { y, parts: [] };
      rows.push(row);
    }
    row.parts.push({ x, y, width: Number.isFinite(width) && width >= 0 ? width : null, text });
    row.y = (row.y * (row.parts.length - 1) + y) / row.parts.length;
  }

  const chunks = [];
  for (const row of rows) {
    row.parts.sort((a, b) => a.x - b.x);
    let current = null;
    let previous = null;
    for (const part of row.parts) {
      const previousEnd = previous
        ? previous.x + (previous.width ?? Math.max(1, previous.text.length * 4))
        : null;
      const gap = previousEnd === null ? 0 : part.x - previousEnd;
      if (!current || gap > MAX_TEXT_GAP_PT) {
        current = { text: '', parts: [], y: row.y };
        chunks.push(current);
      }
      const separator = current.text ? ' ' : '';
      const start = current.text.length + separator.length;
      current.text += `${separator}${part.text}`;
      current.parts.push({ ...part, start, end: start + part.text.length });
      previous = part;
    }
  }
  return chunks;
}

function anchorForMatch(chunk, match) {
  const start = Number(match?.index || 0);
  const end = start + String(match?.[0] || '').length;
  const part = chunk.parts.find(p => p.end > start && p.start < end) || chunk.parts[0];
  return part ? [round3(part.x), round3(part.y)] : [0, round3(chunk.y)];
}

function addTag(out, seen, { page, pageRole, system, diameter, matchedText, position, source }) {
  const normalized = normalizePipeTagDiameter({
    page,
    page_role: pageRole,
    system,
    diameter_in: diameter,
    dn: null,
    matched_text: matchedText,
    position_pt: position,
    tag_source: source,
  });
  const key = [
    normalized.page,
    normalized.system,
    normalized.diameter_in,
    Math.round(Number(position?.[0] || 0) * 10),
    Math.round(Number(position?.[1] || 0) * 10),
  ].join('|');
  if (seen.has(key)) return;
  seen.add(key);
  out.push(normalized);
}

export function extractRawPositionedPipeTags(items, page, pageRole = 'primary_plan') {
  const out = [];
  const seen = new Set();
  for (const chunk of positionedChunks(items)) {
    RAW_PIPE_TAG_RX.lastIndex = 0;
    for (const match of chunk.text.matchAll(RAW_PIPE_TAG_RX)) {
      addTag(out, seen, {
        page,
        pageRole,
        system: String(match[2]).toUpperCase(),
        diameter: match[1],
        matchedText: match[0],
        position: anchorForMatch(chunk, match),
        source: 'RAW_POSITIONED_PDFJS_TEXT_ITEM',
      });
    }

    RAW_RFD_RL_RX.lastIndex = 0;
    for (const match of chunk.text.matchAll(RAW_RFD_RL_RX)) {
      addTag(out, seen, {
        page,
        pageRole,
        system: 'RL',
        diameter: match[1],
        matchedText: match[0],
        position: anchorForMatch(chunk, match),
        source: 'RAW_POSITIONED_COMPOUND_RFD_PLUS_RL',
      });
    }
  }
  return out.sort((a, b) => Number(a.page) - Number(b.page)
    || Number(a.position_pt?.[1] || 0) - Number(b.position_pt?.[1] || 0)
    || Number(a.position_pt?.[0] || 0) - Number(b.position_pt?.[0] || 0)
    || String(a.system).localeCompare(String(b.system)));
}

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
    const positioned = Number(page?.raw_positioned_pipe_tag_count || page?.explicit_pipe_tag_count || 0);
    return `p.${page.page} straight ${straight}/${raw} seg · positioned tags ${positioned} · coverage ${pct}% · ${scale}`;
  }).join('; ');
  return `Browser Alpha3 trace visible OCG/vector network แบบ straight-only + raw-positioned tags แล้ว (${details}) แต่ pipe length ยัง WITHHELD จน primary diameter coverage ≥95%, scale ชัด, tag association ไม่กำกวม และ unsupported curved geometry ได้รับการพิสูจน์ว่าไม่ใช่ pipe run`;
}

async function rebuildSafePipeDiagnostics({ data, pdfjs, result }) {
  const pageRoles = result?.diagnostics?.page_role_classification || [];
  const legacyPipeTags = result?.diagnostics?.pipe_size_system_tags_evidence_only || [];
  const pagesNeeded = [...new Set(pageRoles
    .filter(role => role?.role === 'primary_plan')
    .map(role => Number(role.page))
    .filter(page => Number.isInteger(page) && legacyPipeTags.some(tag => Number(tag?.page) === page)))]
    .sort((a, b) => a - b);
  if (!pagesNeeded.length) {
    return {
      detector: 'browser_pipe_geometry_alpha3',
      normalization: 'SAFE_VISIBLE_STRAIGHT_SEMANTIC_RAW_POSITIONED_V2',
      tag_source: 'RAW_POSITIONED_PDFJS_TEXT_ITEM_WITH_LEGACY_ZERO_FALLBACK',
      status: 'WITHHELD_NO_PRIMARY_PLAN_PIPE_TAG_PAGES',
      release_status: 'WITHHELD_ALPHA3_DIAGNOSTIC_ONLY',
      min_primary_diameter_coverage: 0.95,
      analyzed_primary_pages: [],
      diagnostic_candidate_pages: [],
      pages: [],
      reference_used_for_generation: false,
    };
  }

  const roleByPage = new Map(pageRoles.map(role => [Number(role.page), role]));
  const doc = await pdfjs.getDocument({ data: data.slice() }).promise;
  try {
    const pages = [];
    const effectivePipeTags = [];
    const tagDiagnostics = [];
    for (const pageNo of pagesNeeded) {
      const page = await doc.getPage(pageNo);
      const content = await page.getTextContent({ disableNormalization: false });
      const role = roleByPage.get(pageNo)?.role || 'primary_plan';
      const rawTags = extractRawPositionedPipeTags(content.items, pageNo, role);
      const fallback = legacyPipeTags.filter(tag => Number(tag?.page) === pageNo);
      const selected = rawTags.length ? rawTags : fallback.map(tag => ({ ...tag, tag_source: 'LEGACY_GROUPED_TEXT_ZERO_RAW_FALLBACK' }));
      effectivePipeTags.push(...selected);
      tagDiagnostics.push({
        page: pageNo,
        raw_positioned_count: rawTags.length,
        legacy_grouped_count: fallback.length,
        selected_source: rawTags.length ? 'RAW_POSITIONED_PDFJS_TEXT_ITEM' : 'LEGACY_GROUPED_TEXT_ZERO_RAW_FALLBACK',
        tags: selected,
      });
      pages.push({ page: pageNo, lines: groupPdfTextItems(content.items) });
      page.cleanup?.();
    }
    const geometry = await analyzeBrowserPipeGeometrySafe({ doc, pdfjs, pages, pageRoles, pipeTags: effectivePipeTags });
    geometry.detector = 'browser_pipe_geometry_alpha3';
    geometry.normalization = 'SAFE_VISIBLE_STRAIGHT_SEMANTIC_RAW_POSITIONED_V2';
    geometry.tag_source = 'RAW_POSITIONED_PDFJS_TEXT_ITEM_WITH_LEGACY_ZERO_FALLBACK';
    geometry.positioned_tag_diagnostics = tagDiagnostics;
    for (const pageDiag of geometry.pages || []) {
      const diag = tagDiagnostics.find(item => Number(item.page) === Number(pageDiag.page));
      pageDiag.raw_positioned_pipe_tag_count = Number(diag?.raw_positioned_count || 0);
      pageDiag.legacy_grouped_pipe_tag_count = Number(diag?.legacy_grouped_count || 0);
      pageDiag.pipe_tag_source = diag?.selected_source || 'UNKNOWN';
    }
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
      detector: 'browser_pipe_geometry_alpha3',
      normalization: 'SAFE_VISIBLE_STRAIGHT_SEMANTIC_RAW_POSITIONED_V2',
      tag_source: 'RAW_POSITIONED_PDFJS_TEXT_ITEM_WITH_LEGACY_ZERO_FALLBACK',
      status: 'WITHHELD_SAFE_GEOMETRY_ANALYZER_ERROR',
      release_status: 'WITHHELD_ALPHA3_DIAGNOSTIC_ONLY',
      error: String(error?.message || error),
      analyzed_primary_pages: [],
      pages: [],
      reference_used_for_generation: false,
    };
  }

  result.source_policy = {
    ...(result.source_policy || {}),
    generic_pipe_length_min_primary_diameter_coverage: 0.95,
    generic_pipe_length_release_status: 'WITHHELD_ALPHA3_DIAGNOSTIC_ONLY',
    pipe_geometry_normalization: 'SAFE_VISIBLE_STRAIGHT_SEMANTIC_RAW_POSITIONED_V2',
    pipe_tag_position_policy: 'RAW_POSITIONED_PDFJS_TEXT_ITEMS; compound RFD+RL yields explicit RL class; legacy grouped x is zero-raw fallback only',
  };
  result.diagnostics = {
    ...(result.diagnostics || {}),
    pipe_geometry_alpha3: geometry,
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
    result.limitations = result.limitations.filter(item => !String(item).startsWith('Alpha2 diagnostics use visible OCGs only'));
    result.limitations.push('Alpha3 diagnostics use visible OCGs only, straight measured geometry only, raw PDF.js positioned pipe tags, compact mixed-fraction normalization, and explicit compound RFD+RL→RL evidence. Pipe rows remain diagnostic-only until the generic 95% release gate and ambiguity gates pass.');
  }
  return result;
}
