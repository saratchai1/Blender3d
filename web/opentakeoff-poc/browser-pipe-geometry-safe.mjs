import {
  aggregatePipeAssignments,
  assignPipeDiameters,
  associatePipeTagsToSegments,
  buildPipeComponents,
  extractLayeredPipeSegmentsFromOpList,
  parseScaleEvidence,
} from './browser-pipe-geometry.mjs';

const DN_BY_INCH = new Map([
  ['1/2', 15], ['3/4', 20], ['1', 25], ['1 1/2', 40], ['2', 50], ['2 1/2', 65], ['4', 100],
]);
const MIN_PRIMARY_COVERAGE = 0.95;

function round3(value) {
  return Math.round(Number(value) * 1000) / 1000;
}

function canonicalLayerName(name) {
  return String(name || '')
    .toUpperCase()
    .replace(/\$\d+\$/g, ' ')
    .replace(/[|:_./\\-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function normalizePipeDiameterIn(raw) {
  let value = String(raw || '').replace(/\s+/g, ' ').replace(/\s*\/\s*/g, '/').trim();
  const mixed = /^(\d+)([1-7])\/([248])$/.exec(value);
  if (mixed && Number(mixed[2]) < Number(mixed[3])) value = `${mixed[1]} ${mixed[2]}/${mixed[3]}`;
  return value;
}

export function normalizePipeTagDiameter(tag) {
  const diameterIn = normalizePipeDiameterIn(tag?.diameter_in);
  const explicitDn = tag?.dn !== null && tag?.dn !== undefined && Number.isFinite(Number(tag.dn)) && Number(tag.dn) > 0
    ? Number(tag.dn)
    : null;
  const dn = explicitDn ?? DN_BY_INCH.get(diameterIn) ?? null;
  return { ...tag, diameter_in: diameterIn || null, dn };
}

export function sanitizeExtractedPipeGeometry(extracted) {
  const layers = Array.isArray(extracted?.semantic_layers) ? extracted.semantic_layers : [];
  const hiddenIds = new Set(layers.filter(layer => layer?.visible === false).map(layer => String(layer.id)));
  const visibleLayers = layers
    .filter(layer => layer?.visible !== false)
    .map(layer => ({
      ...layer,
      canonical_name: canonicalLayerName(layer?.name),
      semantic_key: `${String(layer?.system || '')}|${canonicalLayerName(layer?.name)}`,
    }));
  const layerById = new Map(visibleLayers.map(layer => [String(layer.id), layer]));
  const sourceSegments = Array.isArray(extracted?.segments) ? extracted.segments : [];
  let hiddenLength = 0;
  let curvedLength = 0;
  let hiddenCount = 0;
  let curvedCount = 0;
  const segments = [];
  for (const original of sourceSegments) {
    if (hiddenIds.has(String(original?.layer_id))) {
      hiddenCount += 1;
      hiddenLength += Number(original?.length_pt || 0);
      continue;
    }
    if (original?.curved === true) {
      curvedCount += 1;
      curvedLength += Number(original?.length_pt || 0);
      continue;
    }
    const layer = layerById.get(String(original?.layer_id));
    if (!layer) continue;
    segments.push({
      ...original,
      index: segments.length,
      source_layer_id: String(original.layer_id),
      layer_id: layer.semantic_key,
      semantic_key: layer.semantic_key,
      layer_name: layer.name,
      curved: false,
    });
  }
  return {
    segments,
    semantic_layers: visibleLayers,
    unsupported: {
      ...(extracted?.unsupported || {}),
      curved_segments_source: curvedCount,
      curved_length_pt_source: round3(curvedLength),
      hidden_segments_excluded: hiddenCount,
      hidden_length_pt_excluded: round3(hiddenLength),
    },
  };
}

export async function analyzeBrowserPipeGeometrySafe({ doc, pdfjs, pages, pageRoles, pipeTags, minPrimaryCoverage = MIN_PRIMARY_COVERAGE }) {
  const roleMap = new Map((pageRoles || []).map(x => [Number(x.page), x]));
  const linesByPage = new Map((pages || []).map(x => [Number(x.page), x.lines || []]));
  const tagsByPage = new Map();
  for (const rawTag of pipeTags || []) {
    const tag = normalizePipeTagDiameter(rawTag);
    const list = tagsByPage.get(Number(tag.page)) || [];
    list.push(tag);
    tagsByPage.set(Number(tag.page), list);
  }

  let groups = {};
  try {
    const cfg = await doc.getOptionalContentConfig();
    groups = cfg?.getGroups?.() || {};
  } catch {
    groups = {};
  }

  const pageDiagnostics = [];
  for (const [pageNo, role] of roleMap) {
    if (role?.role !== 'primary_plan') continue;
    const tags = tagsByPage.get(pageNo) || [];
    if (!tags.length) continue;
    const systems = new Set(tags.map(t => t.system).filter(Boolean));
    const page = await doc.getPage(pageNo);
    const viewport = page.getViewport({ scale: 1 });
    const opList = await page.getOperatorList();
    const raw = extractLayeredPipeSegmentsFromOpList({
      opList,
      viewportTransform: viewport.transform,
      OPS: pdfjs.OPS,
      groups,
      pageTagSystems: systems,
    });
    const extracted = sanitizeExtractedPipeGeometry(raw);
    const componentResult = buildPipeComponents(extracted.segments);
    const associations = componentResult.work_cap_exceeded
      ? { accepted: [], withheld: tags.map(t => ({ ...t, association_status: 'WITHHELD_COMPONENT_WORK_CAP' })) }
      : associatePipeTagsToSegments(tags, extracted.segments, viewport.transform);
    const assignments = componentResult.work_cap_exceeded
      ? []
      : assignPipeDiameters(extracted.segments, componentResult.components, componentResult.adjacency, associations.accepted);
    const scale = parseScaleEvidence(linesByPage.get(pageNo) || []);
    const aggregate = aggregatePipeAssignments(extracted.segments, assignments, scale.unique_ratio);

    const blockers = [];
    if (!extracted.semantic_layers.length) blockers.push('NO_RECOGNIZED_VISIBLE_PIPE_OCG_LAYER');
    if (raw?.unsupported?.work_cap_exceeded || componentResult.work_cap_exceeded) blockers.push('VECTOR_WORK_CAP_EXCEEDED');
    if (Number(raw?.unsupported?.curved_segments || 0) > 0) blockers.push('CURVED_PIPE_LAYER_GEOMETRY_PRESENT');
    if (scale.status !== 'PASS_UNIQUE_EXPLICIT_SCALE') blockers.push(scale.status);
    if (aggregate.coverage.assigned_fraction < minPrimaryCoverage) blockers.push('DIAMETER_COVERAGE_BELOW_RELEASE_GATE');
    if (associations.withheld.length) blockers.push('UNASSOCIATED_OR_AMBIGUOUS_PIPE_TAGS');

    pageDiagnostics.push({
      page: pageNo,
      page_role: role.role,
      page_role_confidence: role.confidence,
      explicit_pipe_tag_count: tags.length,
      tag_systems: [...systems].sort(),
      semantic_layers: extracted.semantic_layers,
      raw_vector_segment_count: Array.isArray(raw?.segments) ? raw.segments.length : 0,
      vector_segment_count: extracted.segments.length,
      component_count: componentResult.components.length,
      pair_checks: componentResult.pair_checks,
      unsupported: extracted.unsupported,
      scale,
      tag_associations: associations,
      diameter_coverage: aggregate.coverage,
      diameter_rows: aggregate.rows,
      blockers,
      diagnostic_gate_status: blockers.length ? 'WITHHELD' : 'PASS_DIAGNOSTIC_CANDIDATE',
    });
    page.cleanup?.();
  }

  const candidatePages = pageDiagnostics.filter(x => x.diagnostic_gate_status === 'PASS_DIAGNOSTIC_CANDIDATE');
  return {
    detector: 'browser_pipe_geometry_alpha2_safe',
    status: pageDiagnostics.length ? 'DIAGNOSTIC_ONLY_NO_PIPE_ROW_PUBLICATION' : 'WITHHELD_NO_PRIMARY_PLAN_PIPE_TAG_PAGES',
    release_status: 'WITHHELD_ALPHA2_DIAGNOSTIC_ONLY',
    min_primary_diameter_coverage: minPrimaryCoverage,
    optional_content_group_count: Object.keys(groups || {}).length,
    analyzed_primary_pages: pageDiagnostics.map(x => x.page),
    diagnostic_candidate_pages: candidatePages.map(x => x.page),
    pages: pageDiagnostics,
    cross_view_policy: 'PRIMARY_PLAN_HORIZONTAL_ONLY; vertical/detail views remain non-additive evidence and are not measured here',
    geometry_policy: 'VISIBLE_OCG_ONLY; CURVED_FIGURES_EXCLUDED_FROM_MEASURED_DENOMINATOR_BUT_REMAIN_RELEASE_BLOCKERS; SAME_SYSTEM_AND_CANONICAL_LAYER_NAME_SHARE_TOPOLOGY_KEY',
    reference_used_for_generation: false,
  };
}
