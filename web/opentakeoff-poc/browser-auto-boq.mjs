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

const FLOOR_DRAIN_RX = /(?:Ø|∅)\s*2\s*"?\s*FD\b/giu;
const PIPE_TAG_RX = /(?:Ø|∅)\s*(\d+(?:\s+\d+\s*\/\s*\d+|\s*\/\s*\d+|\.\d+)?)\s*"?\s*(CW|RL|SW|S|W|V)\b/giu;
const DN_BY_INCH = new Map([
  ['1/2', 15], ['3/4', 20], ['1', 25], ['1 1/2', 40], ['2', 50], ['2 1/2', 65], ['4', 100],
]);

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

export function parseSanitaryLines(pages) {
  const detections = [];
  const seen = new Set();
  const floorDrainEvidence = [];
  const floorDrainSeen = new Set();
  const pipeTags = [];
  const pipeSeen = new Set();

  for (const page of pages || []) {
    const pageNo = Number(page?.page);
    if (!Number.isInteger(pageNo) || pageNo < 1) continue;
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
            confidence: rule.confidence,
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
          system,
          diameter_in: inch,
          dn: DN_BY_INCH.get(inch) ?? null,
          matched_text: match[0],
          position_pt: [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000],
        });
      }
    }
  }

  const byId = new Map();
  for (const detection of detections) {
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
        method: 'browser:pdfjs explicit positioned sanitary tag',
        evidence: { detections: [] },
      };
      byId.set(detection.id, row);
    }
    row.quantity += 1;
    if (!row.source_pages.includes(detection.page)) row.source_pages.push(detection.page);
    row.evidence.detections.push(detection);
  }
  const rows = [...byId.values()];
  for (const row of rows) row.source_pages.sort((a, b) => a - b);
  rows.sort((a, b) => a.id.localeCompare(b.id));

  return { rows, detections, floorDrainEvidence, pipeTags };
}

export async function extractBrowserAutoBoq({ bytes, name = 'uploaded.pdf', pdfjs, maxPages = 150 }) {
  if (!pdfjs?.getDocument) throw new Error('PDF.js runtime unavailable');
  const data = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes || []);
  if (data.byteLength < 5) throw new Error('PDF file is empty');
  const doc = await pdfjs.getDocument({ data }).promise;
  const pagesToScan = Math.min(doc.numPages, maxPages);
  const pages = [];
  for (let pageNo = 1; pageNo <= pagesToScan; pageNo += 1) {
    const page = await doc.getPage(pageNo);
    const content = await page.getTextContent({ disableNormalization: false });
    pages.push({ page: pageNo, lines: groupPdfTextItems(content.items) });
    page.cleanup?.();
  }
  const parsed = parseSanitaryLines(pages);
  await doc.destroy?.();

  const withheld = [
    {
      name: 'SAN-PIPE-LENGTH',
      reason: `พบ explicit pipe-size/system tags ${parsed.pipeTags.length} จุด แต่ Browser Runtime Alpha ยังไม่ trace vector network/scale เพื่อคำนวณความยาว จึง WITHHELD`,
    },
    {
      name: 'SAN-FLOOR-DRAIN-2',
      reason: `พบ Ø2\"FD ${parsed.floorDrainEvidence.length} จุด แต่ยังแยก physical drain ออกจาก schedule/detail duplicate ไม่ได้อย่างปลอดภัย จึง WITHHELD`,
    },
    {
      name: 'NON-EXPLICIT-BOQ',
      reason: 'Browser Runtime Alpha รุ่นนี้ปล่อยเฉพาะ explicit sanitary tags ที่ตำแหน่งชัดเจน; fixture/structure/finish และ geometry inference อื่นยัง WITHHELD',
    },
  ];

  return {
    schema: 'blender3d.browser_auto_boq.v1',
    document: { name, bytes: data.byteLength, pages: doc.numPages, scanned_pages: pagesToScan, truncated: doc.numPages > pagesToScan },
    status: parsed.rows.length ? 'PRELIMINARY_EXPLICIT_TAG_ROWS' : 'NO_SAFE_AUTOMATIC_ROWS_FOUND',
    rows: parsed.rows,
    source_policy: {
      reference_used_for_generation: false,
      generation_source: 'USER_UPLOADED_PDF_BROWSER_ONLY',
      max_pages: maxPages,
      scanned_pages: pagesToScan,
    },
    coverage: { withheld_detectors: withheld },
    diagnostics: {
      explicit_sanitary_tag_detections: parsed.detections,
      floor_drain_detections_withheld: parsed.floorDrainEvidence,
      pipe_size_system_tags_evidence_only: parsed.pipeTags,
    },
    limitations: [
      'No OCR in Browser Runtime Alpha.',
      'No vector-network length release yet for arbitrary user PDFs.',
      'No reference/benchmark quantity is read or available to this runtime.',
      'Rows are preliminary and require drawing review before procurement.',
    ],
  };
}
