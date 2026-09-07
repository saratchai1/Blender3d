const SYSTEM_LONG_NAMES = new Map([
  ['COLD WATER', 'CW'],
  ['DOMESTIC COLD WATER', 'CW'],
  ['COLDWATER', 'CW'],
  ['WASTE', 'W'],
  ['SANITARY WASTE', 'W'],
  ['SOIL', 'S'],
  ['SANITARY SOIL', 'S'],
  ['VENT', 'V'],
  ['SANITARY VENT', 'V'],
  ['RAIN LEADER', 'RL'],
  ['RAINWATER LEADER', 'RL'],
  ['ROOF LEADER', 'RL'],
  ['STORM WATER', 'SW'],
  ['STORMWATER', 'SW'],
  ['STORM DRAIN', 'SW'],
]);

const SHORT_SYSTEMS = new Set(['CW', 'W', 'S', 'SW', 'V', 'RL']);
const MAX_SEMANTIC_SEGMENTS_PER_PAGE = 6000;
const MAX_COMPONENT_PAIR_CHECKS = 2_000_000;
const DEFAULT_SNAP_PT = 1.5;
const DEFAULT_TAG_SNAP_PT = 30;
const DEFAULT_TAG_MARGIN_PT = 4;
const DEFAULT_TIE_PT = 0.5;
const MIN_PRIMARY_COVERAGE = 0.95;
const CURVE_STEPS = 8;

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

export function matchPipeLayerSystem(name, pageTagSystems = new Set()) {
  const canonical = canonicalLayerName(name);
  if (!canonical) return null;
  if (SYSTEM_LONG_NAMES.has(canonical)) return SYSTEM_LONG_NAMES.get(canonical);
  for (const [label, system] of SYSTEM_LONG_NAMES) {
    if (canonical.includes(label)) return system;
  }
  const tokens = canonical.split(' ').filter(Boolean);
  for (const token of tokens) {
    if (SHORT_SYSTEMS.has(token) && pageTagSystems.has(token)) return token;
  }
  return null;
}

export function parseScaleEvidence(lines) {
  const candidates = [];
  const seen = new Set();
  for (const line of lines || []) {
    const text = String(line?.text || '').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const patterns = [
      { rx: /\bSCALE\b[^\d]{0,12}1\s*[:=]\s*(\d{2,4})\b/i, basis: 'EXPLICIT_SCALE_LABEL', confidence: 1.0 },
      { rx: /^1\s*[:=]\s*(\d{2,4})$/i, basis: 'STANDALONE_SCALE_RATIO', confidence: 0.96 },
    ];
    for (const { rx, basis, confidence } of patterns) {
      const match = rx.exec(text);
      if (!match) continue;
      const ratio = Number(match[1]);
      if (!Number.isInteger(ratio) || ratio < 10 || ratio > 2000) continue;
      const key = `${ratio}|${basis}|${Math.round(Number(line?.x || 0))}|${Math.round(Number(line?.y || 0))}`;
      if (seen.has(key)) continue;
      seen.add(key);
      candidates.push({ ratio, basis, confidence, matched_text: match[0], position_pt: [round3(line?.x || 0), round3(line?.y || 0)] });
    }
  }
  const ratios = [...new Set(candidates.map(x => x.ratio))].sort((a, b) => a - b);
  return {
    status: ratios.length === 1 ? 'PASS_UNIQUE_EXPLICIT_SCALE' : ratios.length ? 'WITHHELD_AMBIGUOUS_SCALE' : 'WITHHELD_NO_EXPLICIT_SCALE',
    unique_ratio: ratios.length === 1 ? ratios[0] : null,
    ratios,
    candidates,
  };
}

function mul(a, b) {
  return [
    a[0] * b[0] + a[2] * b[1],
    a[1] * b[0] + a[3] * b[1],
    a[0] * b[2] + a[2] * b[3],
    a[1] * b[2] + a[3] * b[3],
    a[0] * b[4] + a[2] * b[5] + a[4],
    a[1] * b[4] + a[3] * b[5] + a[5],
  ];
}

function tx(m, x, y) {
  return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
}

function pointSegmentDistance(point, a, b) {
  const vx = b[0] - a[0], vy = b[1] - a[1];
  const wx = point[0] - a[0], wy = point[1] - a[1];
  const denom = vx * vx + vy * vy;
  if (denom <= 1e-12) return Math.hypot(point[0] - a[0], point[1] - a[1]);
  const t = Math.max(0, Math.min(1, (wx * vx + wy * vy) / denom));
  return Math.hypot(point[0] - (a[0] + t * vx), point[1] - (a[1] + t * vy));
}

function paintIsStroke(fnArray, index, OPS) {
  const strokes = new Set([
    OPS.stroke, OPS.closeStroke, OPS.fillStroke, OPS.eoFillStroke,
    OPS.closeFillStroke, OPS.closeEOFillStroke,
  ].filter(Number.isFinite));
  for (let j = index + 1; j < fnArray.length && j <= index + 4; j += 1) {
    const fn = fnArray[j];
    if (fn === OPS.clip || fn === OPS.eoClip) continue;
    if (fn === OPS.endPath || fn === OPS.fill || fn === OPS.eoFill) return false;
    return strokes.has(fn);
  }
  return false;
}

function currentLayer(mcStack) {
  for (let i = mcStack.length - 1; i >= 0; i -= 1) if (mcStack[i]) return mcStack[i];
  return null;
}

function semanticGroups(groups, pageTagSystems) {
  const out = new Map();
  for (const [id, group] of Object.entries(groups || {})) {
    const name = String(group?.name || '');
    const system = matchPipeLayerSystem(name, pageTagSystems);
    if (!system || !pageTagSystems.has(system)) continue;
    out.set(String(id), { id: String(id), name, system, visible: group?.visible !== false });
  }
  return out;
}

export function extractLayeredPipeSegmentsFromOpList({ opList, viewportTransform, OPS, groups, pageTagSystems }) {
  const semantic = semanticGroups(groups, pageTagSystems);
  const segments = [];
  const unsupported = { curved_segments: 0, work_cap_exceeded: false };
  if (!semantic.size) return { segments, semantic_layers: [], unsupported };

  let m = Array.isArray(viewportTransform) ? viewportTransform.slice() : [1, 0, 0, 1, 0, 0];
  const stack = [];
  const mcStack = [];
  const fns = opList?.fnArray || [];
  const argsArray = opList?.argsArray || [];

  const addSegment = (layer, a, b, curved = false) => {
    const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (!(length > 0.05)) return;
    if (curved) unsupported.curved_segments += 1;
    segments.push({
      index: segments.length,
      layer_id: layer.id,
      layer_name: layer.name,
      system: layer.system,
      a,
      b,
      length_pt: length,
      curved,
    });
    if (segments.length > MAX_SEMANTIC_SEGMENTS_PER_PAGE) unsupported.work_cap_exceeded = true;
  };

  for (let i = 0; i < fns.length; i += 1) {
    if (unsupported.work_cap_exceeded) break;
    const fn = fns[i];
    const args = argsArray[i] || [];
    if (fn === OPS.save) stack.push(m.slice());
    else if (fn === OPS.restore) { const prev = stack.pop(); if (prev) m = prev; }
    else if (fn === OPS.transform) m = mul(m, args);
    else if (fn === OPS.paintFormXObjectBegin) { stack.push(m.slice()); if (args?.[0]) m = mul(m, args[0]); }
    else if (fn === OPS.paintFormXObjectEnd) { const prev = stack.pop(); if (prev) m = prev; }
    else if (fn === OPS.beginMarkedContent) mcStack.push(null);
    else if (fn === OPS.beginMarkedContentProps) {
      const data = args?.[0] === 'OC' ? args?.[1] : null;
      let id = null;
      if (data && typeof data === 'object') {
        if (typeof data.id === 'string' && data.id) id = data.id;
        else if (Array.isArray(data.ids) && data.ids.length === 1 && typeof data.ids[0] === 'string') id = data.ids[0];
      }
      mcStack.push(id);
    } else if (fn === OPS.endMarkedContent) {
      if (mcStack.length) mcStack.pop();
    } else if (fn === OPS.constructPath) {
      const layerId = currentLayer(mcStack);
      const layer = layerId ? semantic.get(String(layerId)) : null;
      if (!layer || !paintIsStroke(fns, i, OPS)) continue;
      const ops = args?.[0] || [];
      const co = args?.[1] || [];
      let c = 0;
      let cur = null;
      let start = null;
      for (const op of ops) {
        if (op === OPS.moveTo) {
          cur = tx(m, co[c], co[c + 1]); start = cur; c += 2;
        } else if (op === OPS.lineTo) {
          const p = tx(m, co[c], co[c + 1]); c += 2;
          if (cur) addSegment(layer, cur, p, false);
          cur = p;
        } else if (op === OPS.curveTo || op === OPS.curveTo2 || op === OPS.curveTo3) {
          let p1, p2, p3;
          if (op === OPS.curveTo) {
            p1 = tx(m, co[c], co[c + 1]); p2 = tx(m, co[c + 2], co[c + 3]); p3 = tx(m, co[c + 4], co[c + 5]); c += 6;
          } else if (op === OPS.curveTo2) {
            p1 = cur || tx(m, co[c], co[c + 1]); p2 = tx(m, co[c], co[c + 1]); p3 = tx(m, co[c + 2], co[c + 3]); c += 4;
          } else {
            p1 = tx(m, co[c], co[c + 1]); p2 = p3 = tx(m, co[c + 2], co[c + 3]); c += 4;
          }
          const p0 = cur || p1;
          let prev = p0;
          for (let k = 1; k <= CURVE_STEPS; k += 1) {
            const t = k / CURVE_STEPS, u = 1 - t;
            const q = [
              u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
              u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1],
            ];
            addSegment(layer, prev, q, true); prev = q;
          }
          cur = p3;
        } else if (op === OPS.closePath) {
          if (cur && start) addSegment(layer, cur, start, false);
          cur = start;
        } else if (op === OPS.rectangle) {
          const x = co[c], y = co[c + 1], w = co[c + 2], h = co[c + 3]; c += 4;
          const q = [tx(m, x, y), tx(m, x + w, y), tx(m, x + w, y + h), tx(m, x, y + h)];
          for (let k = 0; k < 4; k += 1) addSegment(layer, q[k], q[(k + 1) % 4], false);
          cur = q[0]; start = q[0];
        }
      }
    }
  }
  if (segments.length > MAX_SEMANTIC_SEGMENTS_PER_PAGE) segments.length = MAX_SEMANTIC_SEGMENTS_PER_PAGE;
  return { segments, semantic_layers: [...semantic.values()], unsupported };
}

function segmentsLinked(a, b, snapPt) {
  const boxMiss = Math.max(
    Math.min(a.a[0], a.b[0]) - Math.max(b.a[0], b.b[0]),
    Math.min(b.a[0], b.b[0]) - Math.max(a.a[0], a.b[0]),
    Math.min(a.a[1], a.b[1]) - Math.max(b.a[1], b.b[1]),
    Math.min(b.a[1], b.b[1]) - Math.max(a.a[1], a.b[1]),
  );
  if (boxMiss > snapPt) return false;
  return [a.a, a.b].some(p => pointSegmentDistance(p, b.a, b.b) <= snapPt)
    || [b.a, b.b].some(p => pointSegmentDistance(p, a.a, a.b) <= snapPt);
}

export function buildPipeComponents(segments, snapPt = DEFAULT_SNAP_PT) {
  const adjacency = Array.from({ length: segments.length }, () => new Set());
  let pairChecks = 0;
  for (let i = 0; i < segments.length; i += 1) {
    for (let j = i + 1; j < segments.length; j += 1) {
      if (segments[i].layer_id !== segments[j].layer_id || segments[i].system !== segments[j].system) continue;
      pairChecks += 1;
      if (pairChecks > MAX_COMPONENT_PAIR_CHECKS) return { components: [], adjacency, work_cap_exceeded: true, pair_checks: pairChecks };
      if (!segmentsLinked(segments[i], segments[j], snapPt)) continue;
      adjacency[i].add(j); adjacency[j].add(i);
    }
  }
  const components = [];
  const seen = new Set();
  for (let i = 0; i < segments.length; i += 1) {
    if (seen.has(i)) continue;
    const stack = [i]; seen.add(i); const indexes = [];
    while (stack.length) {
      const cur = stack.pop(); indexes.push(cur);
      for (const next of adjacency[cur]) if (!seen.has(next)) { seen.add(next); stack.push(next); }
    }
    const id = components.length;
    for (const idx of indexes) segments[idx].component_id = id;
    components.push({ id, system: segments[i].system, layer_id: segments[i].layer_id, layer_name: segments[i].layer_name, segment_indexes: indexes.sort((a, b) => a - b) });
  }
  return { components, adjacency, work_cap_exceeded: false, pair_checks: pairChecks };
}

function classForTag(tag) {
  const dn = Number.isFinite(Number(tag?.dn)) ? Number(tag.dn) : null;
  const diameterIn = String(tag?.diameter_in || '').trim();
  return {
    system: String(tag?.system || ''),
    diameter_key: dn ? `DN${dn}` : diameterIn ? `${diameterIn}in` : 'UNKNOWN',
    dn,
    diameter_in: diameterIn || null,
  };
}

export function associatePipeTagsToSegments(tags, segments, viewportTransform, { maxDistancePt = DEFAULT_TAG_SNAP_PT, minMarginPt = DEFAULT_TAG_MARGIN_PT } = {}) {
  const accepted = [];
  const withheld = [];
  for (const tag of tags || []) {
    const raw = Array.isArray(tag?.position_pt) ? tag.position_pt : null;
    if (!raw || raw.length < 2) { withheld.push({ ...tag, association_status: 'WITHHELD_NO_POSITION' }); continue; }
    const point = tx(viewportTransform || [1, 0, 0, 1, 0, 0], Number(raw[0]), Number(raw[1]));
    const candidates = segments
      .filter(seg => seg.system === tag.system)
      .map(seg => ({ index: seg.index, component_id: seg.component_id, distance_pt: pointSegmentDistance(point, seg.a, seg.b) }))
      .sort((a, b) => a.distance_pt - b.distance_pt || a.index - b.index);
    if (!candidates.length || candidates[0].distance_pt > maxDistancePt) {
      withheld.push({ ...tag, association_status: 'WITHHELD_NO_NEARBY_SYSTEM_SEGMENT', transformed_position_pt: point.map(round3), nearest_distance_pt: candidates[0] ? round3(candidates[0].distance_pt) : null });
      continue;
    }
    const nearest = candidates[0];
    const secondDifferentComponent = candidates.find(c => c.component_id !== nearest.component_id);
    const margin = secondDifferentComponent ? secondDifferentComponent.distance_pt - nearest.distance_pt : Infinity;
    if (Number.isFinite(margin) && margin < minMarginPt) {
      withheld.push({ ...tag, association_status: 'WITHHELD_AMBIGUOUS_COMPONENT_PROXIMITY', transformed_position_pt: point.map(round3), nearest_segment: nearest.index, nearest_distance_pt: round3(nearest.distance_pt), component_margin_pt: round3(margin) });
      continue;
    }
    accepted.push({ ...tag, ...classForTag(tag), association_status: 'ACCEPTED_NEAREST_SYSTEM_COMPONENT', transformed_position_pt: point.map(round3), nearest_segment: nearest.index, component_id: nearest.component_id, nearest_distance_pt: round3(nearest.distance_pt), component_margin_pt: Number.isFinite(margin) ? round3(margin) : null });
  }
  return { accepted, withheld };
}

function heapPush(heap, item) {
  heap.push(item);
  let i = heap.length - 1;
  while (i > 0) {
    const p = Math.floor((i - 1) / 2);
    if (heap[p][0] <= item[0]) break;
    heap[i] = heap[p]; i = p;
  }
  heap[i] = item;
}

function heapPop(heap) {
  if (!heap.length) return null;
  const root = heap[0];
  const last = heap.pop();
  if (!heap.length) return root;
  let i = 0;
  while (true) {
    let child = i * 2 + 1;
    if (child >= heap.length) break;
    if (child + 1 < heap.length && heap[child + 1][0] < heap[child][0]) child += 1;
    if (heap[child][0] >= last[0]) break;
    heap[i] = heap[child]; i = child;
  }
  heap[i] = last;
  return root;
}

export function assignPipeDiameters(segments, components, adjacency, tags, tieTolerancePt = DEFAULT_TIE_PT) {
  const byComponent = new Map();
  for (const tag of tags || []) {
    if (!Number.isInteger(tag?.component_id) || !Number.isInteger(tag?.nearest_segment)) continue;
    const list = byComponent.get(tag.component_id) || []; list.push(tag); byComponent.set(tag.component_id, list);
  }
  const assignments = [];
  for (const component of components || []) {
    const seeds = byComponent.get(component.id) || [];
    if (!seeds.length) {
      for (const index of component.segment_indexes) assignments.push({ segment_index: index, component_id: component.id, status: 'WITHHELD_NO_DIAMETER_EVIDENCE', classes: [] });
      continue;
    }
    const meta = new Map();
    const seedsByIndex = new Map();
    for (const tag of seeds) {
      const cls = classForTag(tag); const key = `${cls.system}|${cls.diameter_key}`;
      meta.set(key, cls);
      const set = seedsByIndex.get(tag.nearest_segment) || new Set(); set.add(key); seedsByIndex.set(tag.nearest_segment, set);
    }
    const unique = new Set([...seedsByIndex.values()].flatMap(set => [...set]));
    if (unique.size === 1) {
      const key = [...unique][0];
      for (const index of component.segment_indexes) assignments.push({ segment_index: index, component_id: component.id, status: seedsByIndex.has(index) ? 'EXPLICIT_TAG_SEED' : 'COMPONENT_SINGLE_CLASS_PROPAGATION', classes: [meta.get(key)] });
      continue;
    }
    const best = new Map(component.segment_indexes.map(i => [i, Infinity]));
    const labels = new Map(component.segment_indexes.map(i => [i, new Set()]));
    const heap = [];
    for (const [index, classes] of seedsByIndex) for (const key of classes) heapPush(heap, [0, index, key]);
    while (heap.length) {
      const [distance, index, key] = heapPop(heap);
      if (distance > best.get(index) + tieTolerancePt) continue;
      if (distance + tieTolerancePt < best.get(index)) { best.set(index, distance); labels.set(index, new Set([key])); }
      else if (Math.abs(distance - best.get(index)) <= tieTolerancePt) labels.get(index).add(key);
      for (const next of adjacency[index] || []) {
        const weight = (segments[index].length_pt + segments[next].length_pt) / 2;
        if (distance + weight <= best.get(next) + tieTolerancePt) heapPush(heap, [distance + weight, next, key]);
      }
    }
    for (const index of component.segment_indexes) {
      const keys = labels.get(index) || new Set();
      const classes = [...keys].sort().map(k => meta.get(k));
      const status = keys.size === 1 ? (seedsByIndex.has(index) && seedsByIndex.get(index).size === 1 ? 'EXPLICIT_TAG_SEED' : 'NETWORK_NEAREST_TAG_PROPAGATION') : keys.size > 1 ? 'WITHHELD_DIAMETER_TIE' : 'WITHHELD_UNREACHABLE_FROM_DIAMETER_SEED';
      assignments.push({ segment_index: index, component_id: component.id, status, classes });
    }
  }
  return assignments.sort((a, b) => a.component_id - b.component_id || a.segment_index - b.segment_index);
}

export function aggregatePipeAssignments(segments, assignments, scaleRatio) {
  const grouped = new Map();
  let total = 0, assigned = 0, withheld = 0;
  for (const assignment of assignments || []) {
    const seg = segments[assignment.segment_index];
    if (!seg) continue;
    total += seg.length_pt;
    if (assignment.status.startsWith('WITHHELD') || assignment.classes.length !== 1) { withheld += seg.length_pt; continue; }
    assigned += seg.length_pt;
    const cls = assignment.classes[0]; const key = `${cls.system}|${cls.diameter_key}`;
    const row = grouped.get(key) || { system: cls.system, diameter_key: cls.diameter_key, dn: cls.dn, diameter_in: cls.diameter_in, length_pt: 0, segment_count: 0 };
    row.length_pt += seg.length_pt; row.segment_count += 1; grouped.set(key, row);
  }
  const rows = [...grouped.values()].map(row => ({ ...row, length_pt: round3(row.length_pt), ...(scaleRatio ? { scale_ratio: scaleRatio, length_m_candidate: round3(row.length_pt / 72 * 0.0254 * scaleRatio) } : {}) })).sort((a, b) => a.system.localeCompare(b.system) || a.diameter_key.localeCompare(b.diameter_key));
  return {
    rows,
    coverage: {
      total_length_pt: round3(total),
      assigned_length_pt: round3(assigned),
      withheld_length_pt: round3(withheld),
      assigned_fraction: total > 0 ? Math.round(assigned / total * 10000) / 10000 : 0,
    },
  };
}

export async function analyzeBrowserPipeGeometry({ doc, pdfjs, pages, pageRoles, pipeTags, minPrimaryCoverage = MIN_PRIMARY_COVERAGE }) {
  const roleMap = new Map((pageRoles || []).map(x => [Number(x.page), x]));
  const linesByPage = new Map((pages || []).map(x => [Number(x.page), x.lines || []]));
  const tagsByPage = new Map();
  for (const tag of pipeTags || []) {
    const list = tagsByPage.get(Number(tag.page)) || []; list.push(tag); tagsByPage.set(Number(tag.page), list);
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
    const extracted = extractLayeredPipeSegmentsFromOpList({ opList, viewportTransform: viewport.transform, OPS: pdfjs.OPS, groups, pageTagSystems: systems });
    const componentResult = buildPipeComponents(extracted.segments);
    const associations = componentResult.work_cap_exceeded ? { accepted: [], withheld: tags.map(t => ({ ...t, association_status: 'WITHHELD_COMPONENT_WORK_CAP' })) } : associatePipeTagsToSegments(tags, extracted.segments, viewport.transform);
    const assignments = componentResult.work_cap_exceeded ? [] : assignPipeDiameters(extracted.segments, componentResult.components, componentResult.adjacency, associations.accepted);
    const scale = parseScaleEvidence(linesByPage.get(pageNo) || []);
    const aggregate = aggregatePipeAssignments(extracted.segments, assignments, scale.unique_ratio);
    const blockers = [];
    if (!extracted.semantic_layers.length) blockers.push('NO_RECOGNIZED_PIPE_OCG_LAYER');
    if (extracted.unsupported.work_cap_exceeded || componentResult.work_cap_exceeded) blockers.push('VECTOR_WORK_CAP_EXCEEDED');
    if (extracted.unsupported.curved_segments > 0) blockers.push('CURVED_PIPE_LAYER_GEOMETRY_PRESENT');
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
    detector: 'browser_pipe_geometry_alpha2',
    status: pageDiagnostics.length ? 'DIAGNOSTIC_ONLY_NO_PIPE_ROW_PUBLICATION' : 'WITHHELD_NO_PRIMARY_PLAN_PIPE_TAG_PAGES',
    release_status: 'WITHHELD_ALPHA2_DIAGNOSTIC_ONLY',
    min_primary_diameter_coverage: minPrimaryCoverage,
    optional_content_group_count: Object.keys(groups || {}).length,
    analyzed_primary_pages: pageDiagnostics.map(x => x.page),
    diagnostic_candidate_pages: candidatePages.map(x => x.page),
    pages: pageDiagnostics,
    cross_view_policy: 'PRIMARY_PLAN_HORIZONTAL_ONLY; vertical/detail views remain non-additive evidence and are not measured here',
    reference_used_for_generation: false,
  };
}
