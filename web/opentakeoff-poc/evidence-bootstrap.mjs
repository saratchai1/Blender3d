import { evidenceController } from './evidence-viewer.mjs';

const SVG_NS = 'http://www.w3.org/2000/svg';
const EVIDENCE_RUNTIME_EVENT = 'boq-evidence:runtime-result';
const EVIDENCE_RUNTIME_STATE = '__BOQ_EVIDENCE_RUNTIME__';

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}

function isPipeRow(row) {
  return String(row?.id || '').startsWith('SAN-PIPE-');
}

function exactEvidenceForPage(row, pageNo) {
  const e = row?.evidence || {};
  const horizontal = (e.published_segments || [])
    .filter(segment => Number(segment.page) === Number(pageNo))
    .map(segment => ({ ...segment, exactRole: 'horizontal' }));
  const vertical = [];
  for (const run of e.published_vertical_runs || []) {
    for (const segment of run.source_segments || []) {
      if (Number(segment.page) !== Number(pageNo)) continue;
      vertical.push({
        ...segment,
        exactRole: 'vertical',
        publishedVerticalLengthM: Number(run.published_vertical_length_m || 0),
        runClassification: String(run.classification_status || ''),
        runQuantityBasis: String(run.quantity_basis || ''),
      });
    }
  }
  return { horizontal, vertical };
}

async function drawExactPipeEvidence(controller) {
  const row = controller.row;
  const pageNo = Number(controller.pageNo);
  const host = controller.host;
  if (!isPipeRow(row) || !host || !Number.isFinite(pageNo)) return;
  const overlay = host.querySelector('#evidence-overlay');
  if (!overlay || overlay.hidden) return;

  const exact = exactEvidenceForPage(row, pageNo);
  const segments = [...exact.horizontal, ...exact.vertical];
  if (!segments.length) return;

  const pdf = await controller.getPdf();
  const page = await pdf.getPage(pageNo);
  const base = page.getViewport({ scale: 1 });
  const viewBox = overlay.viewBox?.baseVal;
  const width = Number(viewBox?.width || overlay.getAttribute('width') || 0);
  const height = Number(viewBox?.height || overlay.getAttribute('height') || 0);
  if (!(width > 0 && height > 0 && base.width > 0 && base.height > 0)) return;
  const sx = width / base.width;
  const sy = height / base.height;

  for (const segment of segments) {
    const x0 = Number(segment.x0_pt);
    const y0 = Number(segment.y0_pt);
    const x1 = Number(segment.x1_pt);
    const y1 = Number(segment.y1_pt);
    if (![x0, y0, x1, y1].every(Number.isFinite)) continue;
    const vertical = segment.exactRole === 'vertical';
    const line = svgEl('line', {
      x1: x0 * sx,
      y1: y0 * sy,
      x2: x1 * sx,
      y2: y1 * sy,
      class: `evidence-shape pipe exact-pipe-segment ${vertical ? 'exact-vertical-source-stroke' : 'exact-horizontal-segment'}`,
      'data-segment-index': segment.segment_index,
      'data-evidence-role': vertical ? 'vertical-source-stroke' : 'published-horizontal-segment',
      'stroke-linecap': 'round',
    });
    const title = svgEl('title');
    title.textContent = vertical
      ? `${row.id} · source segment ${segment.segment_index} · vertical run ${Number(segment.publishedVerticalLengthM || 0).toFixed(3)} m · ${segment.runClassification || 'validated run'}`
      : `${row.id} · published segment ${segment.segment_index} · ${Number(segment.segment_length_m || 0).toFixed(6)} m · ${segment.publish_reason || 'validated assignment'}`;
    line.append(title);
    overlay.append(line);
  }

  const facts = host.querySelector('#evidence-facts');
  if (facts) {
    facts.querySelectorAll('.exact-pipe-fact').forEach(node => node.remove());
    if (exact.horizontal.length) {
      const item = document.createElement('li');
      item.className = 'exact-pipe-fact proof-pass';
      item.textContent = `PASS: p.${pageNo} แสดง exact published horizontal vector ${exact.horizontal.length} segment จาก detector segment_index จริง`;
      facts.append(item);
    }
    if (exact.vertical.length) {
      const runCount = new Set((row.evidence?.published_vertical_runs || [])
        .filter(run => (run.source_segments || []).some(segment => Number(segment.page) === pageNo))
        .map((run, index) => `${index}:${run.classification_status || ''}:${run.published_vertical_length_m || 0}`)).size;
      const item = document.createElement('li');
      item.className = 'exact-pipe-fact proof-pass';
      item.textContent = `PASS: p.${pageNo} แสดง exact vertical source strokes ${exact.vertical.length} segment / ${runCount} calibrated run; ปริมาณ vertical ใช้ run-level physical span ไม่ใช่ผลรวมความยาวเส้นหมึก`;
      facts.append(item);
    }
    const status = row.evidence?.exact_segment_evidence_status;
    if (status) {
      const item = document.createElement('li');
      item.className = `exact-pipe-fact ${status === 'PASS_EXACT_SOURCE_GEOMETRY_RECONCILED' ? 'proof-pass' : 'proof-fail'}`;
      item.textContent = `Exact geometry gate: ${status}`;
      facts.append(item);
    }
  }

  const label = host.querySelector('#evidence-page-label');
  if (label && segments.length) label.textContent += ` · exact ${segments.length} source segments`;
}

// PDF.js rejects concurrent render() operations that target the same canvas.
// bindRows auto-opens the first evidence row, while a user may click that row
// before the first render completes. Serialize those renders so every request
// uses the canvas only after the previous render has settled.
const originalRender = evidenceController.render.bind(evidenceController);
let evidenceRenderQueue = Promise.resolve();
evidenceController.render = function patchedEvidenceRender() {
  const controller = this;
  const queued = evidenceRenderQueue
    .catch(() => {})
    .then(async () => {
      await originalRender();
      await drawExactPipeEvidence(controller);
    });
  evidenceRenderQueue = queued;
  return queued;
};

function tableRowIds(tbody) {
  return Array.from(tbody.querySelectorAll('td:first-child small'))
    .map(x => x.textContent || '')
    .filter(Boolean);
}

function resultRowIds(data) {
  return (data?.rows || []).map(row => String(row.id || '')).filter(Boolean);
}

function sameIds(left, right) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function normalizedRuntimeEvidence(detail) {
  const data = detail?.result;
  if (!data || data.source_policy?.reference_used_for_generation !== false) return null;
  const bytes = detail.pdfBytes instanceof Uint8Array
    ? detail.pdfBytes
    : new Uint8Array(detail.pdfBytes || []);
  return {
    data,
    name: detail.name || data.document?.name || 'uploaded.pdf',
    pdfBytes: bytes,
    fingerprint: detail.fingerprint || `${data.document?.sha256 || ''}:${detail.name || data.document?.name || ''}:${bytes.byteLength}`,
  };
}

async function main() {
  const tbody = document.querySelector('#auto-rows-body');
  const workspace = document.querySelector('#workspace');
  if (!tbody || !workspace) return;

  const response = await fetch('./auto-boq.json', { cache: 'no-store' });
  if (!response.ok) throw new Error('auto-boq.json unavailable for evidence viewer');
  const demoAuto = await response.json();
  if (demoAuto.source_policy?.reference_used_for_generation !== false) throw new Error('evidence viewer requires reference-isolated Automatic BOQ');

  let signature = '';
  let pendingUserEvidence = normalizedRuntimeEvidence(globalThis[EVIDENCE_RUNTIME_STATE]);

  const bind = (data, context, key) => {
    const host = evidenceController.ensureHost();
    signature = key;
    evidenceController.resetPdf();
    evidenceController.bindRows(tbody, data, context);
    host.hidden = false;
  };

  const refreshBindings = (data, context, expected) => {
    const buttonCount = tbody.querySelectorAll('.evidence-open').length;
    if (buttonCount !== expected.length) evidenceController.bindRows(tbody, data, context);
  };

  const sync = () => {
    const host = evidenceController.ensureHost();
    const ids = tableRowIds(tbody);
    const demo = workspace.value === 'demo';

    if (demo) {
      const expected = resultRowIds(demoAuto);
      const next = `demo:${ids.join('|')}`;
      if (!ids.length || !sameIds(ids, expected)) {
        signature = '';
        host.hidden = true;
        return;
      }
      const context = { workspace: 'demo', pdfUrl: './demo/family4.pdf' };
      if (next === signature) {
        host.hidden = false;
        refreshBindings(demoAuto, context, expected);
        return;
      }
      bind(demoAuto, context, next);
      return;
    }

    // Extraction may publish its evidence state before the BOQ table mutation is
    // observed. Recover from the page-level state on every sync so event ordering
    // cannot leave the viewer permanently hidden.
    pendingUserEvidence = normalizedRuntimeEvidence(globalThis[EVIDENCE_RUNTIME_STATE]) || pendingUserEvidence;
    if (!pendingUserEvidence) {
      signature = '';
      host.hidden = true;
      return;
    }

    const expected = resultRowIds(pendingUserEvidence.data);
    if (!expected.length || !ids.length || !sameIds(ids, expected)) {
      signature = '';
      host.hidden = true;
      return;
    }
    const next = `user:${pendingUserEvidence.fingerprint}:${ids.join('|')}`;
    const context = {
      workspace: 'user',
      pdfBytes: pendingUserEvidence.pdfBytes,
      pdfName: pendingUserEvidence.name,
    };
    if (next === signature) {
      host.hidden = false;
      // The POC refreshes the user BOQ table on repeated PDF state messages.
      // Re-attach row evidence controls without resetting the selected evidence.
      refreshBindings(pendingUserEvidence.data, context, expected);
      return;
    }
    bind(pendingUserEvidence.data, context, next);
  };

  globalThis.addEventListener(EVIDENCE_RUNTIME_EVENT, event => {
    const latest = normalizedRuntimeEvidence(event?.detail || {});
    if (!latest) return;
    pendingUserEvidence = latest;
    signature = '';
    if (workspace.value === 'user') queueMicrotask(sync);
  });

  new MutationObserver(sync).observe(tbody, { childList: true, subtree: true });
  workspace.addEventListener('change', () => {
    signature = '';
    evidenceController.resetPdf();
    const host = evidenceController.ensureHost();
    host.hidden = true;
    queueMicrotask(sync);
  });
  sync();
}

main().catch(error => {
  console.error('BOQ_EVIDENCE_VIEWER_ERROR', error);
});
