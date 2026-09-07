const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}

function pipeDiag(data) {
  return (data?.diagnostics || []).find(d => d?.detector === 'sanitary_pipe_network_v8_19') || null;
}

function classMatches(classes, system, diameterKey) {
  return Array.isArray(classes) && classes.length === 1 &&
    String(classes[0]?.system || '') === system &&
    String(classes[0]?.diameter_key || '') === diameterKey;
}

function horizontalSegmentIndexes(page, system, diameterKey) {
  if (String(page?.contribution_policy || '') !== 'PRIMARY_PLAN_HORIZONTAL') return [];
  return (page?.diameter_assignments || [])
    .filter(a => !String(a?.status || '').startsWith('WITHHELD') && classMatches(a?.classes, system, diameterKey))
    .map(a => Number(a.segment_index))
    .filter(Number.isInteger);
}

function verticalSegmentIndexes(diag, pageNo, system, diameterKey) {
  if (Number(pageNo) !== 57) return [];
  const vertical = diag?.vertical_level_bounded_reconciliation || {};
  const indexes = new Set();
  for (const key of ['candidate_runs', 'direct_branch_promoted_runs', 'valve_leader_promoted_runs', 'roof_extended_runs']) {
    for (const run of vertical[key] || []) {
      if (String(run?.system || '') !== system || String(run?.diameter_key || '') !== diameterKey) continue;
      for (const index of run.segment_indexes || []) {
        const value = Number(index);
        if (Number.isInteger(value)) indexes.add(value);
      }
    }
  }
  return [...indexes];
}

function selectedGeometry(controller) {
  const row = controller?.row;
  if (!String(row?.id || '').startsWith('SAN-PIPE-')) return [];
  const diag = pipeDiag(controller.data);
  const page = (diag?.pages || []).find(p => Number(p.page) === Number(controller.pageNo));
  if (!page || page.segment_geometry_status !== 'EXACT_RECONSTRUCTION_MATCH') return [];
  const system = String(row.evidence?.system || '');
  const diameterKey = String(row.evidence?.diameter_key || '');
  const indexes = new Set([
    ...horizontalSegmentIndexes(page, system, diameterKey),
    ...verticalSegmentIndexes(diag, controller.pageNo, system, diameterKey),
  ]);
  if (!indexes.size) return [];
  return (page.segment_geometry || []).filter(segment => indexes.has(Number(segment.segment_index)));
}

function appendAuditFact(controller, geometry) {
  const facts = controller.host?.querySelector('#evidence-facts');
  if (!facts || !geometry.length) return;
  facts.querySelectorAll('[data-pipe-segment-audit]').forEach(node => node.remove());
  const diag = pipeDiag(controller.data);
  const page = (diag?.pages || []).find(p => Number(p.page) === Number(controller.pageNo));
  const row = controller.row;
  const li = document.createElement('li');
  li.dataset.pipeSegmentAudit = 'true';
  li.className = 'proof-pass';
  if (String(page?.contribution_policy || '') === 'PRIMARY_PLAN_HORIZONTAL') {
    const dr = (page?.diameter_rows || []).find(x =>
      String(x?.system || '') === String(row.evidence?.system || '') &&
      String(x?.diameter_key || '') === String(row.evidence?.diameter_key || '')
    );
    const pageLength = dr?.length_m_candidate != null ? ` · ${Number(dr.length_m_candidate).toFixed(3)} m on this plan` : '';
    li.textContent = `EXACT VECTOR AUDIT: ${geometry.length} source-PDF pipe segments highlighted${pageLength}; no synthetic gap length is drawn.`;
  } else {
    li.textContent = `EXACT VECTOR AUDIT: ${geometry.length} source-PDF schematic segments underpin the accepted vertical reconciliation; published vertical length remains level-bounded, not raw drawn-line length.`;
  }
  facts.append(li);
}

function ensureLegend(controller) {
  const legend = controller.host?.querySelector('.evidence-legend');
  if (!legend || legend.querySelector('[data-pipe-segment-legend]')) return;
  const item = document.createElement('span');
  item.dataset.pipeSegmentLegend = 'true';
  const sample = document.createElement('i');
  sample.style.cssText = 'display:inline-block;width:18px;height:0;border-top:4px solid #2372b2;border-radius:2px';
  item.append(sample, document.createTextNode('เส้น vector ที่ใช้จริง'));
  legend.append(item);
}

async function renderExactPipeSegments(controller) {
  const rowId = String(controller?.row?.id || '');
  const pageNo = Number(controller?.pageNo);
  if (!rowId.startsWith('SAN-PIPE-') || !Number.isInteger(pageNo)) return;
  const overlay = controller.host?.querySelector('#evidence-overlay');
  if (!overlay || overlay.hidden) return;
  overlay.querySelectorAll('.pipe-segment').forEach(node => node.remove());
  const geometry = selectedGeometry(controller);
  if (!geometry.length) return;

  const pdf = await controller.getPdf();
  const page = await pdf.getPage(pageNo);
  if (rowId !== String(controller?.row?.id || '') || pageNo !== Number(controller?.pageNo)) return;
  const base = page.getViewport({ scale: 1 });
  const viewBox = overlay.viewBox.baseVal;
  const sx = viewBox.width / base.width;
  const sy = viewBox.height / base.height;
  for (const segment of geometry) {
    const [ax, ay] = segment.a_pt.map(Number);
    const [bx, by] = segment.b_pt.map(Number);
    const line = svgEl('line', {
      x1: ax * sx,
      y1: ay * sy,
      x2: bx * sx,
      y2: by * sy,
      class: 'evidence-shape pipe pipe-segment',
      'data-segment-index': segment.segment_index,
      'data-component-id': segment.component_id ?? '',
      style: 'stroke-dasharray:none;stroke-width:4;opacity:.92;fill:none',
    });
    const title = svgEl('title');
    title.textContent = `${rowId} · source vector segment ${segment.segment_index} · layer ${segment.layer || 'unlayered'} · ${Number(segment.length_pt).toFixed(3)} pt`;
    line.append(title);
    overlay.append(line);
  }
  appendAuditFact(controller, geometry);
  ensureLegend(controller);
  const pageLabel = controller.host?.querySelector('#evidence-page-label');
  if (pageLabel && !pageLabel.textContent.includes('exact pipe segments')) {
    pageLabel.textContent += ` · ${geometry.length} exact pipe segments`;
  }
}

export function installPipeSegmentOverlay(controller) {
  if (!controller || controller.__pipeSegmentOverlayInstalled) return;
  controller.__pipeSegmentOverlayInstalled = true;
  const originalRender = controller.render.bind(controller);
  controller.render = async function (...args) {
    const result = await originalRender(...args);
    try {
      await renderExactPipeSegments(this);
    } catch (error) {
      console.error('BOQ_PIPE_SEGMENT_EVIDENCE_ERROR', error);
    }
    return result;
  };
}
