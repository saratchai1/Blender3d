const SVG_NS = 'http://www.w3.org/2000/svg';
const DN_TO_INCH = new Map([[15,0.5],[20,0.75],[25,1],[32,1.25],[40,1.5],[50,2],[65,2.5],[80,3],[100,4],[125,5],[150,6]]);

const fmt = (n, d = 3) => Number(n).toLocaleString('th-TH', {
  minimumFractionDigits: d,
  maximumFractionDigits: d,
});

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}

function pipeDiag(data) {
  return (data?.diagnostics || []).find(d => d?.detector === 'sanitary_pipe_network_v8_19') || null;
}

function matchingPipePage(row, data) {
  if (!String(row?.id || '').startsWith('SAN-PIPE-')) return null;
  const diag = pipeDiag(data);
  const system = String(row.evidence?.system || '');
  const diameter = String(row.evidence?.diameter_key || '');
  const candidates = (diag?.pages || []).filter(page => (row.source_pages || []).includes(page.page));
  const primary = candidates.find(page =>
    /plan/i.test(String(page.view_role || '')) &&
    (page.diameter_rows || []).some(x => x.system === system && x.diameter_key === diameter)
  );
  return primary?.page || candidates.find(page =>
    (page.diameter_rows || []).some(x => x.system === system && x.diameter_key === diameter)
  )?.page || null;
}

function preferredPage(row, data) {
  const pipePage = matchingPipePage(row, data);
  if (pipePage) return pipePage;
  const detections = row?.evidence?.detections || [];
  const withPage = detections.find(x => Number.isInteger(Number(x.page)));
  if (withPage) return Number(withPage.page);
  return Number((row?.source_pages || [1])[0] || 1);
}

function evidenceFormula(row) {
  const e = row?.evidence || {};
  if (row.id === 'ARCH-ROOF-METAL') {
    const projected = Number(e.projected_area_m2 || 0);
    const slope = Number(e.slope_deg || 0);
    return `${fmt(projected)} m² projected × 1/cos(${fmt(slope, 1)}°) = ${fmt(row.quantity)} m²`;
  }
  if (row.id === 'ARCH-FASCIA') {
    return `เส้นรอบรูปของ roof-band เดียวกับพื้นที่หลังคา = ${fmt(row.quantity)} m`;
  }
  if (String(row.id || '').startsWith('SAN-PIPE-')) {
    const h = Number(e.horizontal_length_m || 0);
    const v = Number(e.vertical_length_m || 0);
    return `${fmt(h)} m horizontal + ${fmt(v)} m vertical = ${fmt(row.quantity)} m`;
  }
  if (String(row.id || '').startsWith('GEN-SAN-PIPE-')) {
    return `${fmt(row.quantity)} m จาก semantic CAD pipe vectors ที่ผ่าน explicit scale + system/diameter tag assignment`;
  }
  const detections = e.detections || e.matched_tokens || [];
  if (Array.isArray(detections) && detections.length) {
    return `${detections.length} จุดหลักฐานที่ไม่ซ้ำ × 1 = ${fmt(row.quantity, row.unit === 'ea' ? 0 : 3)} ${row.unit}`;
  }
  return `Detector output = ${fmt(row.quantity, row.unit === 'ea' ? 0 : 3)} ${row.unit}`;
}

function evidenceFacts(row, data, pageNo) {
  const e = row?.evidence || {};
  const facts = [];
  facts.push(`วิธีตรวจ: ${row.method}`);
  facts.push(`Confidence evidence: ${Math.round(Number(row.confidence || 0) * 100)}%`);
  facts.push(`Drawing page ที่กำลังแสดง: p.${pageNo}`);
  if (e.bounds_pt) facts.push(`ขอบเขตที่วัดบน PDF: [${e.bounds_pt.map(x => fmt(x, 1)).join(', ')}] pt`);
  if (e.projected_area_m2 != null) facts.push(`Projected area ก่อน slope correction: ${fmt(e.projected_area_m2)} m²`);
  if (e.hatch_lines != null) facts.push(`เส้น hatch ที่ยืนยันขอบเขต: ${e.hatch_lines} เส้น`);
  if (e.threshold != null) facts.push(`Template threshold: ${fmt(e.threshold, 2)}`);
  if (e.token) facts.push(`Drawing tag ที่อ่าน: ${e.token}`);
  if (e.tokens) facts.push(`Drawing token: ${e.tokens.join(', ')}`);
  if (String(row.id || '').startsWith('SAN-PIPE-')) {
    facts.push(`ระบบ / ขนาด: ${e.system} / ${e.diameter_key}`);
    facts.push(`Horizontal ที่นำมาคิด: ${fmt(e.horizontal_length_m || 0)} m`);
    facts.push(`Vertical ที่นำมาคิด: ${fmt(e.vertical_length_m || 0)} m`);
    for (const role of e.evidence_roles || []) facts.push(`Evidence role: ${role}`);
    const diag = pipeDiag(data);
    const p = (diag?.pages || []).find(x => x.page === pageNo);
    const dr = (p?.diameter_rows || []).find(x => x.system === e.system && x.diameter_key === e.diameter_key);
    if (dr) facts.push(`หน้า p.${pageNo} trace ได้ ${fmt(dr.length_m_candidate)} m จาก ${dr.segment_count} vector segments ที่ผ่าน diameter assignment`);
    if (e.non_additive_contract) facts.push(`กันนับซ้ำ: ${e.non_additive_contract}`);
  }
  if (String(row.id || '').startsWith('GEN-SAN-PIPE-')) {
    if (e.scale_ratio != null) facts.push(`Scale ที่อ่านจากแบบ: 1:${e.scale_ratio}`);
    if (e.assigned_fraction != null) facts.push(`Semantic pipe linework ที่ classify system/diameter ได้: ${fmt(Number(e.assigned_fraction) * 100, 1)}%`);
    if (e.segment_count != null) facts.push(`Vector segments ที่นำมารวม: ${e.segment_count}`);
  }
  return facts;
}

function collectOverlay(row, data, pageNo) {
  const out = [];
  const e = row?.evidence || {};
  if (e.bounds_pt && Number(row.source_pages?.[0]) === pageNo) {
    out.push({ type: 'rect', rect: e.bounds_pt, kind: row.unit === 'm²' ? 'area' : 'linear', label: row.unit === 'm²' ? 'พื้นที่ที่ระบบใช้คำนวณ' : 'ขอบเขตที่ระบบใช้คำนวณ' });
  }
  for (const hit of e.matched_tokens || []) {
    if (hit.bbox_pt) out.push({ type: 'rect', rect: hit.bbox_pt, kind: 'tag', label: hit.text || 'tag' });
  }
  let count = 0;
  for (const hit of e.detections || []) {
    if (Number(hit.page) !== pageNo) continue;
    count += 1;
    if (hit.bbox_pt) out.push({ type: 'rect', rect: hit.bbox_pt, kind: 'detection', label: `${count}` });
    else if (hit.x_norm != null && hit.y_norm != null) out.push({ type: 'point', x: hit.x_norm, y: hit.y_norm, kind: 'detection', label: `${count}` });
    else if (Array.isArray(hit.position_pt) && hit.position_pt.length >= 2) {
      out.push({ type: 'pdf_point', x: Number(hit.position_pt[0]), y: Number(hit.position_pt[1]), kind: 'detection', label: `${count}` });
    }
  }
  for (const segment of e.published_segments || []) {
    if (Number(segment.page) !== pageNo) continue;
    if ([segment.x0_pt, segment.y0_pt, segment.x1_pt, segment.y1_pt].every(Number.isFinite)) {
      out.push({ type: 'line', x0: Number(segment.x0_pt), y0: Number(segment.y0_pt), x1: Number(segment.x1_pt), y1: Number(segment.y1_pt), kind: 'pipe', label: segment.publish_reason || 'published vector segment' });
    }
  }
  if (String(row.id || '').startsWith('SAN-PIPE-')) {
    const diag = pipeDiag(data);
    const page = (diag?.pages || []).find(x => x.page === pageNo);
    const system = String(e.system || '');
    const diameter = String(e.diameter_key || '');
    const targetInch = DN_TO_INCH.get(Number(e.dn));
    for (const tag of page?.tags || []) {
      if (tag.system === system && tag.diameter_key === diameter && tag.bbox_pt) {
        out.push({ type: 'rect', rect: tag.bbox_pt, kind: 'tag', label: tag.text || `${system} ${diameter}` });
      }
    }
    for (const comp of page?.candidate_components || []) {
      const matches = targetInch != null && (comp.classes || []).some(c =>
        c.system === system && Number.isFinite(Number(c.diameter_in)) && Math.abs(Number(c.diameter_in) - targetInch) < 1e-6
      );
      if (matches && comp.bbox_pt) {
        out.push({ type: 'rect', rect: comp.bbox_pt, kind: 'pipe', label: `${system} ${diameter} · ${fmt(comp.length_m_candidate || 0)} m seed` });
      }
    }
  }
  return out;
}

function makeViewer() {
  const host = el('section', 'evidence-lab');
  host.id = 'evidence-lab';
  const head = el('div', 'evidence-head');
  const titleWrap = el('div');
  titleWrap.append(el('span', 'eyebrow', 'AUDIT TRAIL · PDF → GEOMETRY → QUANTITY'));
  titleWrap.append(el('h3', null, 'หลักฐานการถอด BOQ จากแบบจริง'));
  titleWrap.append(el('p', null, 'กด “ดูหลักฐาน” ในรายการ BOQ แล้วระบบจะเปิดหน้า PDF ที่ใช้จริง พร้อม overlay จุด/พื้นที่/tag/network evidence และสูตรที่สร้าง quantity นั้น'));
  head.append(titleWrap);
  const badge = el('span', 'evidence-proof-badge', 'SOURCE DRAWING ONLY');
  head.append(badge);
  host.append(head);

  const grid = el('div', 'evidence-grid');
  const viewer = el('div', 'evidence-viewer');
  const toolbar = el('div', 'evidence-toolbar');
  const prev = el('button', 'button evidence-nav', '← หน้า evidence ก่อน'); prev.id = 'evidence-prev';
  const pageLabel = el('strong', 'evidence-page-label', 'เลือก BOQ ด้านล่าง'); pageLabel.id = 'evidence-page-label';
  const next = el('button', 'button evidence-nav', 'หน้า evidence ถัดไป →'); next.id = 'evidence-next';
  toolbar.append(prev, pageLabel, next);
  viewer.append(toolbar);
  const stage = el('div', 'evidence-stage'); stage.id = 'evidence-stage';
  const empty = el('div', 'evidence-empty', 'เลือก BOQ หนึ่งรายการเพื่อเปิดหลักฐานจาก PDF'); empty.id = 'evidence-empty';
  const canvas = document.createElement('canvas'); canvas.id = 'evidence-canvas'; canvas.hidden = true;
  const overlay = svgEl('svg'); overlay.id = 'evidence-overlay'; overlay.setAttribute('aria-label', 'Automatic BOQ evidence overlay'); overlay.hidden = true;
  stage.append(empty, canvas, overlay);
  viewer.append(stage);
  grid.append(viewer);

  const details = el('aside', 'evidence-details');
  const id = el('code', 'evidence-id', '—'); id.id = 'evidence-id';
  const name = el('h3', 'evidence-title', 'ยังไม่ได้เลือกรายการ'); name.id = 'evidence-title';
  const quantity = el('div', 'evidence-quantity', '—'); quantity.id = 'evidence-quantity';
  const formula = el('div', 'evidence-formula', 'PDF → detector → quantity'); formula.id = 'evidence-formula';
  const pages = el('div', 'evidence-pages'); pages.id = 'evidence-pages';
  const factTitle = el('h4', null, 'Audit trail');
  const facts = el('ul', 'evidence-facts'); facts.id = 'evidence-facts';
  const legend = el('div', 'evidence-legend');
  for (const [cls, text] of [['area','พื้นที่/ขอบเขต'],['detection','จุดที่นับ'],['tag','tag/label'],['pipe','CAD network seed']]) {
    const item = el('span'); const dot = el('i', `legend-dot ${cls}`); item.append(dot, document.createTextNode(text)); legend.append(item);
  }
  details.append(id, name, quantity, formula, pages, factTitle, facts, legend);
  grid.append(details);
  host.append(grid);
  return host;
}

class EvidenceController {
  constructor() {
    this.data = null;
    this.context = null;
    this.row = null;
    this.pageNo = null;
    this.pdfPromise = null;
    this.renderSeq = 0;
    this.host = null;
  }

  ensureHost() {
    if (this.host?.isConnected) return this.host;
    this.host = document.querySelector('#evidence-lab');
    if (!this.host) {
      this.host = makeViewer();
      const review = document.querySelector('#auto .review-line');
      if (review) review.after(this.host);
      else document.querySelector('#auto')?.prepend(this.host);
    }
    this.host.querySelector('#evidence-prev')?.addEventListener('click', () => this.shiftPage(-1));
    this.host.querySelector('#evidence-next')?.addEventListener('click', () => this.shiftPage(1));
    return this.host;
  }

  resetPdf() {
    this.pdfPromise = null;
    this.row = null;
    this.pageNo = null;
  }

  async getPdf() {
    if (this.pdfPromise) return this.pdfPromise;
    const pdfjs = await import('./vendor/pdf.mjs');
    pdfjs.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdf.worker.mjs', import.meta.url).href;
    const source = this.context?.pdfBytes
      ? { data: (this.context.pdfBytes instanceof Uint8Array ? this.context.pdfBytes : new Uint8Array(this.context.pdfBytes)).slice() }
      : this.context?.pdfUrl || './demo/family4.pdf';
    this.pdfPromise = pdfjs.getDocument(source).promise;
    return this.pdfPromise;
  }

  bindRows(tbody, data, context = {}) {
    this.ensureHost();
    this.data = data;
    this.context = context;
    this.pdfPromise = null;
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const byId = new Map((data?.rows || []).map(row => [String(row.id), row]));
    for (const tr of rows) {
      const code = tr.querySelector('td:first-child small');
      const row = byId.get(code?.textContent || '');
      if (!row) continue;
      tr.classList.add('evidence-row');
      tr.tabIndex = 0;
      tr.dataset.evidenceId = row.id;
      const td = tr.querySelector('td:first-child');
      if (td && !td.querySelector('.evidence-open')) {
        const button = el('button', 'evidence-open', 'ดูหลักฐานบน PDF');
        button.type = 'button';
        button.addEventListener('click', ev => { ev.stopPropagation(); this.open(row); });
        td.append(button);
      }
      tr.addEventListener('click', ev => {
        if (ev.target.closest('a,button')) return;
        this.open(row);
      });
      tr.addEventListener('keydown', ev => {
        if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); this.open(row); }
      });
    }
    if (!this.row && data?.rows?.length) {
      const first = data.rows.find(r => r.id === 'ARCH-ROOF-METAL') || data.rows[0];
      this.open(first, { scroll: false });
    }
  }

  async open(row, { scroll = true, page = null } = {}) {
    this.ensureHost();
    this.row = row;
    this.pageNo = Number(page || preferredPage(row, this.data));
    document.querySelectorAll('#auto-rows-body tr.evidence-row').forEach(tr => tr.classList.toggle('evidence-selected', tr.dataset.evidenceId === row.id));
    if (scroll) this.host.scrollIntoView({ behavior: 'smooth', block: 'start' });
    await this.render();
  }

  shiftPage(delta) {
    if (!this.row) return;
    const pages = [...new Set((this.row.source_pages || []).map(Number))];
    const idx = Math.max(0, pages.indexOf(this.pageNo));
    const next = pages[Math.min(pages.length - 1, Math.max(0, idx + delta))];
    if (next != null && next !== this.pageNo) this.open(this.row, { scroll: false, page: next });
  }

  async render() {
    const seq = ++this.renderSeq;
    const host = this.ensureHost();
    const empty = host.querySelector('#evidence-empty');
    const canvas = host.querySelector('#evidence-canvas');
    const overlay = host.querySelector('#evidence-overlay');
    empty.hidden = false; empty.textContent = `กำลังเปิด PDF p.${this.pageNo} และวาง evidence overlay…`;
    canvas.hidden = true; overlay.hidden = true;
    this.renderDetails();
    try {
      const pdf = await this.getPdf();
      if (seq !== this.renderSeq) return;
      const page = await pdf.getPage(this.pageNo);
      const base = page.getViewport({ scale: 1 });
      const stage = host.querySelector('#evidence-stage');
      const targetWidth = Math.max(360, Math.min(1050, stage.clientWidth - 24));
      const scale = targetWidth / base.width;
      const viewport = page.getViewport({ scale });
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      canvas.style.aspectRatio = `${viewport.width}/${viewport.height}`;
      await page.render({ canvasContext: canvas.getContext('2d', { alpha: false }), viewport }).promise;
      if (seq !== this.renderSeq) return;
      overlay.setAttribute('viewBox', `0 0 ${viewport.width} ${viewport.height}`);
      overlay.setAttribute('width', String(viewport.width));
      overlay.setAttribute('height', String(viewport.height));
      overlay.replaceChildren();
      const evidence = collectOverlay(this.row, this.data, this.pageNo);
      const sx = viewport.width / base.width;
      const sy = viewport.height / base.height;
      evidence.forEach((item, index) => {
        if (item.type === 'rect') {
          const [x0, y0, x1, y1] = item.rect.map(Number);
          const rect = svgEl('rect', { x: x0 * sx, y: y0 * sy, width: Math.max(3, (x1 - x0) * sx), height: Math.max(3, (y1 - y0) * sy), class: `evidence-shape ${item.kind}` });
          const title = svgEl('title'); title.textContent = item.label || `evidence ${index + 1}`; rect.append(title); overlay.append(rect);
          if (item.label) {
            const text = svgEl('text', { x: x0 * sx + 4, y: Math.max(13, y0 * sy - 5), class: `evidence-label ${item.kind}` });
            text.textContent = item.label; overlay.append(text);
          }
        } else if (item.type === 'point') {
          const x = Number(item.x) * viewport.width; const y = Number(item.y) * viewport.height;
          const circle = svgEl('circle', { cx: x, cy: y, r: 10, class: `evidence-point ${item.kind}` });
          const title = svgEl('title'); title.textContent = item.label || `detection ${index + 1}`; circle.append(title); overlay.append(circle);
          const text = svgEl('text', { x: x + 13, y: y + 4, class: `evidence-label ${item.kind}` }); text.textContent = item.label || String(index + 1); overlay.append(text);
        } else if (item.type === 'pdf_point') {
          const [x, y] = viewport.convertToViewportPoint(Number(item.x), Number(item.y));
          const circle = svgEl('circle', { cx: x, cy: y, r: 10, class: `evidence-point ${item.kind}` });
          const title = svgEl('title'); title.textContent = item.label || `detection ${index + 1}`; circle.append(title); overlay.append(circle);
          const text = svgEl('text', { x: x + 13, y: y + 4, class: `evidence-label ${item.kind}` }); text.textContent = item.label || String(index + 1); overlay.append(text);
        } else if (item.type === 'line') {
          const line = svgEl('line', { x1: Number(item.x0) * sx, y1: Number(item.y0) * sy, x2: Number(item.x1) * sx, y2: Number(item.y1) * sy, class: `evidence-shape ${item.kind}`, 'stroke-linecap': 'round' });
          const title = svgEl('title'); title.textContent = item.label || `vector ${index + 1}`; line.append(title); overlay.append(line);
        }
      });
      empty.hidden = true; canvas.hidden = false; overlay.hidden = false;
      host.querySelector('#evidence-page-label').textContent = `${this.row.id} · PDF p.${this.pageNo} · ${evidence.length} overlay evidence`;
    } catch (error) {
      empty.hidden = false; empty.textContent = `เปิดหลักฐาน PDF ไม่สำเร็จ: ${error.message}`;
    }
  }

  renderDetails() {
    const host = this.ensureHost();
    const row = this.row;
    if (!row) return;
    host.querySelector('#evidence-id').textContent = row.id;
    host.querySelector('#evidence-title').textContent = row.description;
    host.querySelector('#evidence-quantity').textContent = `${fmt(row.quantity, row.unit === 'ea' ? 0 : 3)} ${row.unit}`;
    host.querySelector('#evidence-formula').textContent = evidenceFormula(row);
    const pages = host.querySelector('#evidence-pages');
    pages.replaceChildren();
    for (const pageNo of row.source_pages || []) {
      const button = el('button', `page-link evidence-page-chip${Number(pageNo) === this.pageNo ? ' active' : ''}`, `p.${pageNo}`);
      button.type = 'button';
      button.addEventListener('click', () => this.open(row, { scroll: false, page: Number(pageNo) }));
      pages.append(button);
    }
    const facts = host.querySelector('#evidence-facts'); facts.replaceChildren();
    for (const fact of evidenceFacts(row, this.data, this.pageNo)) facts.append(el('li', null, fact));
    const family4Fence = this.context?.workspace === 'demo' || this.data?.runtime_profile === 'family4-v8.19';
    const referenceIsolated = this.data?.source_policy?.reference_used_for_generation === false;
    const badge = host.querySelector('.evidence-proof-badge');
    if (family4Fence) {
      const sourceOnly = row.source_pages?.every(p => Number(p) <= 71);
      facts.append(el('li', sourceOnly ? 'proof-pass' : 'proof-fail', sourceOnly ? 'PASS: หลักฐานทั้งหมดอยู่ใน Family4 drawing pages ≤ 71' : 'WARNING: พบ source page เกิน Family4 generation fence'));
      if (badge) badge.textContent = sourceOnly ? 'FAMILY4 DRAWING PAGES ≤ 71' : 'SOURCE FENCE WARNING';
    } else {
      facts.append(el('li', referenceIsolated ? 'proof-pass' : 'proof-fail', referenceIsolated ? 'PASS: quantity นี้สร้างจาก PDF ที่อัปโหลดโดย reference_used_for_generation = false' : 'WARNING: ไม่สามารถยืนยัน reference isolation ของ quantity นี้ได้'));
      if (badge) badge.textContent = referenceIsolated ? 'UPLOADED PDF · REFERENCE ISOLATED' : 'EVIDENCE REVIEW';
    }
    const p = [...new Set((row.source_pages || []).map(Number))];
    host.querySelector('#evidence-prev').disabled = p.indexOf(this.pageNo) <= 0;
    host.querySelector('#evidence-next').disabled = p.indexOf(this.pageNo) >= p.length - 1;
  }
}

export const evidenceController = new EvidenceController();
