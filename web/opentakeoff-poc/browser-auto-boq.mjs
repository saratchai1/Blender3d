import { analyzeBrowserPipeGeometry } from './browser-pipe-geometry.mjs';

const TAG_RULES = [
  {
    id: 'SAN-FCO-4',
    description: 'Floor Cleanout Ø4"',
    rx: /(?:Ø|∅)\s*4\s*"?\s*FCO\b/giu,
    confidence: 0.94,
  },
  {
    id: 'SAN-CO-2.5',
    description: 'Cleanout Ø2½"',
    rx: /(?:Ø|∅)\s*(?:2\s*1\s*\/\s*2|2\s*½|2\.5)\s*"?\s*CO\b/giu,
    confidence: 0.93,
  },
  {
    id: 'SAN-RFD-2.5',
    description: 'Roof Floor Drain Ø2½"',
    rx: /(?:Ø|∅)\s*(?:2\s*1\s*\/\s*2|2\s*½|2\.5)\s*"?\s*RFD\b/giu,
    confidence: 0.93,
  },
  {
    id: 'SAN-AVC-2',
    description: 'Air Vent Cap Ø2"',
    rx: /(?:Ø|∅)\s*2\s*"?\s*AVC\b/giu,
    confidence: 0.94,
  },
];

const STANDALONE_DEVICE_RULES = [
  {
    id: 'SAN-FCO-UNSIZED',
    description: 'Floor Cleanout (FCO) — size WITHHELD',
    rx: /^FCO\.?$/iu,
    confidence: 0.88,
    allowedRoles: new Set(['primary_plan', 'detail_plan']),
  },
  {
    id: 'SAN-CO-UNSIZED',
    description: 'Cleanout (CO) — size WITHHELD',
    rx: /^CO\.?$/iu,
    confidence: 0.86,
    allowedRoles: new Set(['primary_plan', 'detail_plan']),
  },
];

const FLOOR_DRAIN_RX = /(?:Ø|∅)\s*2\s*"?\s*FD\b/giu;
const PIPE_TAG_RX = /(?:Ø|∅)\s*(\d+(?:\s+\d+\s*\/\s*\d+|\s*\/\s*\d+|\.\d+)?)\s*"?\s*(CW|RL|SW|S|W|V)\b/giu;
const DN_BY_INCH = new Map([
  ['1/2', 15], ['3/4', 20], ['1', 25], ['1 1/2', 40], ['2', 50], ['2 1/2', 65], ['4', 100],
]);
const FIXTURE_SCHEDULE_TOKENS = new Set(['WC', 'WC1', 'LAV', 'UR', 'SH', 'C', 'SINK', 'FD']);

function canonicalInch(raw) {
  return String(raw || '')
    .replace(/\s+/g, ' ')
    .replace(/\s*\/\s*/g, '/')
    .trim();
}

function uniquePush(list, seen, key, value) {
  if (seen.has(key)) return;
  seen.add(key);
  list.push(value);
}

function positionedTextItems(items) {
  return (items || []).map(item => {
    const text = String(item?.str || '').trim();
    const tr = Array.isArray(item?.transform) ? item.transform : [];
    const x = Number(tr[4]); const y = Number(tr[5]);
    if (!text || tr.length < 6 || !Number.isFinite(x) || !Number.isFinite(y)) return null;
    return { text, x, y };
  }).filter(Boolean);
}

function countMatches(texts, rx) {
  let count = 0;
  for (const text of texts) { rx.lastIndex = 0; count += [...String(text).matchAll(rx)].length; }
  return count;
}

export function groupPdfTextItems(items, tolerancePt = 3) {
  const rows = [];
  for (const item of items || []) {
    const text = String(item?.str || '').trim();
    const tr = Array.isArray(item?.transform) ? item.transform : [];
    if (!text || tr.length < 6) continue;
    const x = Number(tr[4]);
    const y = Number(tr[5]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    let row = rows.find(r => Math.abs(r.y - y) <= tolerancePt);
    if (!row) {
      row = { y, parts: [] };
      rows.push(row);
    }
    row.parts.push({ x, text });
    row.y = (row.y * (row.parts.length - 1) + y) / row.parts.length;
  }
  return rows
    .map(row => {
      row.parts.sort((a, b) => a.x - b.x);
      return {
        text: row.parts.map(p => p.text).join(' ').replace(/\s+/g, ' ').trim(),
        x: row.parts.length ? row.parts[0].x : 0,
        y: row.y,
      };
    })
    .filter(row => row.text)
    .sort((a, b) => b.y - a.y || a.x - b.x);
}

export function classifyDrawingPage(lines) {
  const texts = (lines || []).map(line => String(line?.text || '').trim()).filter(Boolean);
  const scale50 = countMatches(texts, /(?:^|\s)1\s*[:.]\s*50(?=\s|$)/gi);
  const scale100 = countMatches(texts, /(?:^|\s)1\s*[:.]\s*100(?=\s|$)/gi);
  const levelMarkers = countMatches(texts, /(?:^|\s)\+\s*\d+(?:\.\d+)?(?=\s|$)/g);
  const fixtureTokens = new Set();
  for (const text of texts) {
    const upper = text.toUpperCase();
    for (const match of upper.matchAll(/(?:^|\s)(WC1?|LAV|UR|SH|C|SINK|FD)\.(?=\s|$)/g)) fixtureTokens.add(match[1]);
  }
  const standaloneDevices = countMatches(texts, /(?:^|\s)(?:FCO|CO)\.?(?=\s|$)/gi);
  const sheetCodes = countMatches(texts, /(?:^|\s)[A-Z]{1,4}-\d{1,3}(?=\s|$)/gi);
  const pipeTagCount = texts.filter(text => { PIPE_TAG_RX.lastIndex = 0; return PIPE_TAG_RX.test(text); }).length;

  if ((scale50 >= 2 && fixtureTokens.size >= 3) || (fixtureTokens.size >= 5 && standaloneDevices >= 1)) {
    return { role: 'detail_plan', confidence: 0.94, evidence: { scale50, scale100, levelMarkers, fixture_schedule_tokens: [...fixtureTokens].sort(), standaloneDevices, sheetCodes, pipeTagCount } };
  }
  if (levelMarkers >= 2 && scale50 >= 1 && pipeTagCount >= 2) {
    return { role: 'vertical_schematic', confidence: 0.92, evidence: { scale50, scale100, levelMarkers, fixture_schedule_tokens: [...fixtureTokens].sort(), standaloneDevices, sheetCodes, pipeTagCount } };
  }
  if (scale100 >= 1 && sheetCodes >= 1) {
    return { role: 'primary_plan', confidence: 0.90, evidence: { scale50, scale100, levelMarkers, fixture_schedule_tokens: [...fixtureTokens].sort(), standaloneDevices, sheetCodes, pipeTagCount } };
  }
  return { role: 'unknown', confidence: 0.0, evidence: { scale50, scale100, levelMarkers, fixture_schedule_tokens: [...fixtureTokens].sort(), standaloneDevices, sheetCodes, pipeTagCount } };
}

function choosePhysicalDetections(all, pageRoles) {
  const byId = new Map();
  for (const det of all) {
    const list = byId.get(det.id) || [];
    list.push(det);
    byId.set(det.id, list);
  }
  const kept = [];
  const suppressed = [];
  for (const [id, list] of byId) {
    const hasPrimary = list.some(det => pageRoles.get(det.page)?.role === 'primary_plan');
    const hasDetail = list.some(det => pageRoles.get(det.page)?.role === 'detail_plan');
    for (const det of list) {
      const role = pageRoles.get(det.page)?.role || 'unknown';
      let suppressReason = null;
      if (hasPrimary && (role === 'detail_plan' || role === 'vertical_schematic')) {
        suppressReason = 'NON_ADDITIVE_CROSS_VIEW_PRIMARY_PRECEDENCE';
      } else if (!hasPrimary && hasDetail && role === 'vertical_schematic') {
        suppressReason = 'NON_ADDITIVE_CROSS_VIEW_DETAIL_PRECEDENCE';
      }
      if (suppressReason) suppressed.push({ ...det, suppressed_reason: suppressReason });
      else kept.push(det);
    }
  }
  return { kept, suppressed };
}

export function parseSanitaryLines(pages) {
  const detections = [];
  const seen = new Set();
  const withheldStandalone = [];
  const floorDrainEvidence = [];
  const floorDrainSeen = new Set();
  const pipeTags = [];
  const pipeSeen = new Set();
  const pageRoles = new Map();

  for (const page of pages || []) {
    const pageNo = Number(page?.page);
    if (!Number.isInteger(pageNo) || pageNo < 1) continue;
    const roleInfo = classifyDrawingPage(page?.lines || []);
    pageRoles.set(pageNo, roleInfo);
    const rawItems = Array.isArray(page?.items) ? page.items : (page?.lines || []).map(line => ({ text: line.text, x: line.x, y: line.y }));
    for (const item of rawItems) {
      const rawText = String(item?.text || '').trim();
      const rawX = Number(item?.x || 0); const rawY = Number(item?.y || 0);
      for (const rule of STANDALONE_DEVICE_RULES) {
        rule.rx.lastIndex = 0;
        if (!rule.rx.test(rawText)) continue;
        const evidence = {
          id: rule.id, description: rule.description, page: pageNo, page_role: roleInfo.role,
          confidence: rule.confidence, size_status: 'WITHHELD_NO_EXPLICIT_SIZE', matched_text: rawText,
          position_pt: [Math.round(rawX * 1000) / 1000, Math.round(rawY * 1000) / 1000],
        };
        if (rule.allowedRoles.has(roleInfo.role)) {
          const key = `${rule.id}|${pageNo}|${Math.round(rawX)}|${Math.round(rawY)}`;
          uniquePush(detections, seen, key, evidence);
        } else {
          withheldStandalone.push({ ...evidence, withheld_reason: 'STANDALONE_DEVICE_TOKEN_WITHOUT_DRAWING_PLAN_DETAIL_CONTEXT' });
        }
      }
    }
    for (const line of page?.lines || []) {
      const text = String(line?.text || '');
      const x = Number(line?.x || 0);
      const y = Number(line?.y || 0);
      for (const rule of TAG_RULES) {
        rule.rx.lastIndex = 0;
        for (const match of text.matchAll(rule.rx)) {
          const key = `${rule.id}|${pageNo}|${Math.round(x)}|${Math.round(y)}|${match.index}`;
          uniquePush(detections, seen, key, {
            id: rule.id,
            description: rule.description,
            page: pageNo,
            page_role: roleInfo.role,
            confidence: rule.confidence,
            size_status: 'EXPLICIT',
            matched_text: match[0],
            position_pt: [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000],
          });
        }
      }

      FLOOR_DRAIN_RX.lastIndex = 0;
      for (const match of text.matchAll(FLOOR_DRAIN_RX)) {
        const key = `FD|${pageNo}|${Math.round(x)}|${Math.round(y)}|${match.index}`;
        uniquePush(floorDrainEvidence, floorDrainSeen, key, {
          page: pageNo,
          page_role: roleInfo.role,
          matched_text: match[0],
          position_pt: [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000],
        });
      }

      PIPE_TAG_RX.lastIndex = 0;
      for (const match of text.matchAll(PIPE_TAG_RX)) {
        const inch = canonicalInch(match[1]);
        const system = String(match[2]).toUpperCase();
        const key = `PIPE|${pageNo}|${Math.round(x)}|${Math.round(y)}|${match.index}|${system}|${inch}`;
        uniquePush(pipeTags, pipeSeen, key, {
          page: pageNo,
          page_role: roleInfo.role,
          system,
          diameter_in: inch,
          dn: DN_BY_INCH.get(inch) ?? null,
          matched_text: match[0],
          position_pt: [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000],
        });
      }
    }
  }

  const reconciled = choosePhysicalDetections(detections, pageRoles);
  const byId = new Map();
  for (const detection of reconciled.kept) {
    let row = byId.get(detection.id);
    if (!row) {
      row = {
        id: detection.id,
        description: detection.description,
        category: 'Sanitary',
        quantity: 0,
        unit: 'ea',
        confidence: detection.confidence,
        source_pages: [],
        method: detection.size_status === 'EXPLICIT'
          ? 'browser:pdfjs explicit positioned sanitary tag + non-additive view reconciliation'
          : 'browser:pdfjs exact device token count; size withheld + drawing-context gate',
        review: 'REVIEW_REQUIRED',
        evidence: {
          size_status: detection.size_status,
          cross_view_policy: 'PRIMARY_PLAN > DETAIL_PLAN > VERTICAL_SCHEMATIC; unknown pages are not silently discarded',
          detections: [],
        },
      };
      byId.set(detection.id, row);
    }
    row.quantity += 1;
    row.confidence = Math.min(row.confidence, detection.confidence);
    if (!row.source_pages.includes(detection.page)) row.source_pages.push(detection.page);
    row.evidence.detections.push(detection);
  }
  const rows = [...byId.values()];
  for (const row of rows) row.source_pages.sort((a, b) => a - b);
  rows.sort((a, b) => a.id.localeCompare(b.id));

  return {
    rows,
    detections,
    releasedDetections: reconciled.kept,
    crossViewSuppressed: reconciled.suppressed,
    withheldStandalone,
    floorDrainEvidence,
    pipeTags,
    pageRoles: [...pageRoles.entries()].map(([page, info]) => ({ page, ...info })),
  };
}

function pipeGeometryWithheldReason(pipeGeometry, pipeTagCount) {
  const pages = pipeGeometry?.pages || [];
  if (!pages.length) return `พบ explicit pipe-size/system tags ${pipeTagCount} จุด แต่ยังไม่มี primary-plan page ที่มี OCG/CAD pipe layer + scale + tag geometry ครบ จึง WITHHELD pipe length`;
  const details = pages.map(page => {
    const pct = Math.round(Number(page?.diameter_coverage?.assigned_fraction || 0) * 10000) / 100;
    const scale = page?.scale?.unique_ratio ? `1:${page.scale.unique_ratio}` : page?.scale?.status || 'NO_SCALE';
    return `p.${page.page} coverage ${pct}% / ${scale}`;
  }).join('; ');
  return `Browser Alpha2 trace OCG/vector pipe network แล้ว (${details}) แต่ generic pipe release ยัง WITHHELD จน primary diameter coverage ≥95%, scale ชัดเจน, tag association ไม่กำกวม และ unsupported geometry = 0`;
}

export async function extractBrowserAutoBoq({ bytes, name = 'uploaded.pdf', pdfjs, maxPages = 150 }) {
  if (!pdfjs?.getDocument) throw new Error('PDF.js runtime unavailable');
  const data = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes || []);
  if (data.byteLength < 5) throw new Error('PDF file is empty');
  const doc = await pdfjs.getDocument({ data }).promise;
  const numPages = doc.numPages;
  const pagesToScan = Math.min(numPages, maxPages);
  const pages = [];
  for (let pageNo = 1; pageNo <= pagesToScan; pageNo += 1) {
    const page = await doc.getPage(pageNo);
    const content = await page.getTextContent({ disableNormalization: false });
    pages.push({ page: pageNo, lines: groupPdfTextItems(content.items), items: positionedTextItems(content.items) });
    page.cleanup?.();
  }
  const parsed = parseSanitaryLines(pages);
  let pipeGeometry;
  try {
    pipeGeometry = await analyzeBrowserPipeGeometry({ doc, pdfjs, pages, pageRoles: parsed.pageRoles, pipeTags: parsed.pipeTags });
  } catch (error) {
    pipeGeometry = {
      detector: 'browser_pipe_geometry_alpha2',
      status: 'WITHHELD_GEOMETRY_ANALYZER_ERROR',
      release_status: 'WITHHELD_ALPHA2_DIAGNOSTIC_ONLY',
      error: String(error?.message || error),
      pages: [],
      reference_used_for_generation: false,
    };
  }
  await doc.destroy?.();

  const withheld = [
    {
      name: 'SAN-PIPE-LENGTH',
      reason: pipeGeometryWithheldReason(pipeGeometry, parsed.pipeTags.length),
    },
    {
      name: 'SAN-FLOOR-DRAIN-2',
      reason: `พบ Ø2"FD ${parsed.floorDrainEvidence.length} จุด แต่ยังแยก physical drain ออกจาก schedule/detail duplicate ไม่ได้อย่างปลอดภัย จึง WITHHELD`,
    },
    {
      name: 'SAN-FCO/CO-SIZE',
      reason: 'FCO/CO ที่พิมพ์เฉพาะ device token นับจำนวนได้บน drawing plan/detail แต่ห้ามเดาขนาดท่อ; size จึง WITHHELD จน PDF มี explicit size หรือหลักฐานที่ตรวจสอบได้',
    },
    {
      name: 'NON-EXPLICIT-BOQ',
      reason: 'Browser Runtime Alpha รุ่นนี้ปล่อยเฉพาะ explicit sanitary tags/device tokens ที่ผ่าน drawing-context และ cross-view gate; fixture/structure/finish และ geometry inference อื่นยัง WITHHELD',
    },
  ];

  return {
    schema: 'blender3d.browser_auto_boq.v1',
    document: { name, bytes: data.byteLength, pages: numPages, scanned_pages: pagesToScan, truncated: numPages > pagesToScan },
    status: parsed.rows.length ? 'PRELIMINARY_EXPLICIT_TAG_ROWS' : 'NO_SAFE_AUTOMATIC_ROWS_FOUND',
    rows: parsed.rows,
    source_policy: {
      reference_used_for_generation: false,
      generation_source: 'USER_UPLOADED_PDF_BROWSER_ONLY',
      release_requires_drawing_context: true,
      non_additive_cross_view_reconciliation: true,
      generic_pipe_length_min_primary_diameter_coverage: 0.95,
      generic_pipe_length_release_status: pipeGeometry?.release_status || 'WITHHELD',
      max_pages: maxPages,
      scanned_pages: pagesToScan,
    },
    coverage: { withheld_detectors: withheld },
    diagnostics: {
      page_role_classification: parsed.pageRoles,
      explicit_sanitary_tag_detections: parsed.detections,
      released_sanitary_detections: parsed.releasedDetections,
      cross_view_duplicate_detections_suppressed: parsed.crossViewSuppressed,
      standalone_device_tokens_withheld_outside_plan_detail: parsed.withheldStandalone,
      floor_drain_detections_withheld: parsed.floorDrainEvidence,
      pipe_size_system_tags_evidence_only: parsed.pipeTags,
      pipe_geometry_alpha2: pipeGeometry,
    },
    limitations: [
      'No OCR in Browser Runtime Alpha.',
      'Alpha2 traces OCG/CAD pipe vectors on primary plan pages for diagnostics, but no arbitrary-user pipe-length row is released until the generic 95% diameter/scale/ambiguity gates pass.',
      'Standalone FCO/CO device labels do not prove a diameter; size remains WITHHELD.',
      'No benchmark quantity is imported into or available to this runtime.',
      'Rows are preliminary and require drawing review before procurement.',
    ],
  };
}
