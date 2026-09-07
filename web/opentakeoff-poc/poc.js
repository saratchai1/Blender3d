import { metricCsv } from './poc-report.mjs';

const $ = s => document.querySelector(s);
const fmt = (n, d = 2) => Number(n).toLocaleString('th-TH', { minimumFractionDigits: d, maximumFractionDigits: d });
const frame = $('#engine');
const status = $('#status');
const names = { floor: 'พื้นที่พื้น', wall: 'ผิวผนัง', linear: 'ความยาว', count: 'จำนวน' };

let snapshot = null;
let workspace = 'demo';
let lastReceived = 0;
let autoData = null;
let benchmark = null;
let userRuntimeData = null;
let userRuntimeFingerprint = '';
let userRuntimeBusy = false;
let lastPdfRequest = 0;

function request() {
  frame.contentWindow?.postMessage({ type: 'ot-poc:refresh' }, location.origin);
}

function requestUserPdf(force = false) {
  if (workspace !== 'user' || !frame.contentWindow) return;
  const now = Date.now();
  if (!force && now - lastPdfRequest < 2500) return;
  lastPdfRequest = now;
  frame.contentWindow.postMessage({ type: 'ot-poc:get-pdf' }, location.origin);
}

function tab(name) {
  document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('selected', p.id === name));
  if (name === 'boq') request();
  if (name === 'auto' && workspace === 'user') requestUserPdf(true);
}

document.querySelectorAll('[data-tab]').forEach(b => b.addEventListener('click', () => {
  if (!b.disabled) tab(b.dataset.tab);
}));

function setStatus(text, state) {
  status.textContent = text;
  status.dataset.state = state;
}

function manualRender() {
  const r = snapshot?.report;
  if (!r) return;
  const frag = document.createDocumentFragment();
  for (const row of r.rows) {
    const tr = document.createElement('tr');
    const values = [
      row.description,
      names[row.kind],
      row.net == null ? '—' : fmt(row.net, row.kind === 'count' ? 0 : 2),
      fmt(row.waste_pct, 0),
      row.order == null ? '—' : fmt(row.order, row.kind === 'count' ? 0 : 2),
      row.unit,
      row.pending ? `รอตรวจ ${row.pending} จุด` : row.warning ? 'ต้องตรวจแก้' : 'เบื้องต้น',
    ];
    values.forEach((v, i) => {
      const td = document.createElement('td');
      td.textContent = v;
      if ([2, 3, 4].includes(i)) td.className = 'num';
      if (i === 0) {
        const small = document.createElement('small');
        small.textContent = row.sheets.join(' · ');
        td.append(small);
      }
      tr.append(td);
    });
    frag.append(tr);
  }
  if (!r.rows.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 7;
    td.className = 'empty';
    td.textContent = 'ยังไม่มี Manual Takeoff — เปิดแบบแล้ววัด/แก้เฉพาะรายการที่ต้อง review';
    tr.append(td);
    frag.append(tr);
  }
  $('#rows').replaceChildren(frag);
  for (const kind of Object.keys(names)) {
    const rs = r.rows.filter(x => x.kind === kind);
    $(`#${kind}-total`).textContent = rs.some(x => x.net == null)
      ? 'ต้องตรวจ'
      : fmt(rs.reduce((n, x) => n + (x.net ?? 0), 0), kind === 'count' ? 0 : 2);
  }
  $('#review-note').textContent = `${r.shape_count} เส้นวัด / จุด · ${r.pending} รายการยังรอตรวจ · manual/review only`;
  $('#csv').disabled = !r.rows.length;
  $('#json').disabled = !snapshot.takeoff;
}

function confidenceLabel(c) {
  if (c >= .9) return ['สูง', 'high'];
  if (c >= .8) return ['ค่อนข้างสูง', 'mid'];
  return ['ต้องตรวจ', 'review'];
}

function renderWithheld(items) {
  const list = document.createDocumentFragment();
  for (const x of items || []) {
    const item = document.createElement('span');
    item.className = 'withheld';
    item.textContent = `${x.name}: WITHHELD`;
    item.title = x.reason;
    list.append(item);
  }
  $('#withheld-list').replaceChildren(list);
}

function renderDemoAuto() {
  if (!autoData || !benchmark || workspace !== 'demo') return;
  const cmp = new Map(benchmark.comparisons.filter(x => x.detected).map(x => [x.id, x]));
  const frag = document.createDocumentFragment();
  for (const r of autoData.rows) {
    const c = cmp.get(r.id);
    const tr = document.createElement('tr');
    const tdName = document.createElement('td');
    const strong = document.createElement('strong');
    strong.textContent = r.description;
    tdName.append(strong);
    const code = document.createElement('small');
    code.textContent = r.id;
    tdName.append(code);
    tr.append(tdName);

    const q = document.createElement('td');
    q.className = 'num';
    q.textContent = fmt(r.quantity, r.unit === 'ea' ? 0 : 3);
    tr.append(q);

    const unit = document.createElement('td');
    unit.textContent = r.unit;
    tr.append(unit);

    const conf = document.createElement('td');
    const [label, cls] = confidenceLabel(r.confidence);
    const badge = document.createElement('span');
    badge.className = `confidence ${cls}`;
    badge.textContent = `${Math.round(r.confidence * 100)}% · ${label}`;
    conf.append(badge);
    tr.append(conf);

    const page = document.createElement('td');
    r.source_pages.forEach((p, i) => {
      const a = document.createElement('a');
      a.href = `./engine/?workspace=demo&sheet=family4.pdf%23${p}`;
      a.target = '_blank';
      a.rel = 'noopener';
      a.className = 'page-link';
      a.textContent = `p.${p}`;
      page.append(a);
      if (i < r.source_pages.length - 1) page.append(document.createTextNode(' '));
    });
    tr.append(page);

    const method = document.createElement('td');
    method.textContent = r.method;
    tr.append(method);

    const err = document.createElement('td');
    err.className = 'num';
    err.textContent = c ? `${c.error_pct > 0 ? '+' : ''}${fmt(c.error_pct, 3)}%` : '—';
    if (c) err.title = `Auto ${c.generated_quantity} / Reference ${c.reference_quantity}`;
    tr.append(err);
    frag.append(tr);
  }
  $('#auto-rows-body').replaceChildren(frag);
  $('#auto-rows').textContent = autoData.rows.length;
  $('#auto-coverage').textContent = fmt(benchmark.coverage_pct, 2);
  $('#auto-accuracy').textContent = fmt(benchmark.detected_rows_accuracy_pct, 0);
  $('#auto-mae').textContent = fmt(benchmark.mean_absolute_error_pct, 3);
  $('#auto-note').textContent = `${benchmark.detected_reference_rows}/${benchmark.reference_rows} รายการใน audit subset ตรวจพบ · ${benchmark.detected_rows_within_5pct}/${benchmark.detected_reference_rows} อยู่ใน ±5% · ไม่ใช่ full BOQ coverage`;
  renderWithheld(autoData.coverage.withheld_detectors || []);
}

function renderUserPlaceholder(message = 'อัปโหลด PDF ในแท็บ แบบ / ตรวจ แล้วระบบจะเริ่ม Browser Automatic Alpha ให้เอง') {
  const tr = document.createElement('tr');
  const td = document.createElement('td');
  td.colSpan = 7;
  td.className = 'empty';
  td.textContent = message;
  tr.append(td);
  $('#auto-rows-body').replaceChildren(tr);
  $('#auto-rows').textContent = '—';
  $('#auto-coverage').textContent = '—';
  $('#auto-accuracy').textContent = '—';
  $('#auto-mae').textContent = '—';
  $('#auto-note').textContent = 'User PDF Runtime Alpha ไม่อ่าน BOQ/reference และจะปล่อยเฉพาะ explicit sanitary tags ที่หลักฐานชัดเจน';
  renderWithheld([]);
}

function renderUserAuto(data) {
  if (workspace !== 'user') return;
  const frag = document.createDocumentFragment();
  for (const r of data.rows || []) {
    const tr = document.createElement('tr');
    const tdName = document.createElement('td');
    const strong = document.createElement('strong');
    strong.textContent = r.description;
    tdName.append(strong);
    const code = document.createElement('small');
    code.textContent = r.id;
    tdName.append(code);
    tr.append(tdName);

    const q = document.createElement('td');
    q.className = 'num';
    q.textContent = fmt(r.quantity, r.unit === 'ea' ? 0 : 3);
    tr.append(q);

    const unit = document.createElement('td');
    unit.textContent = r.unit;
    tr.append(unit);

    const conf = document.createElement('td');
    const [label, cls] = confidenceLabel(r.confidence);
    const badge = document.createElement('span');
    badge.className = `confidence ${cls}`;
    badge.textContent = `${Math.round(r.confidence * 100)}% · ${label}`;
    conf.append(badge);
    tr.append(conf);

    const page = document.createElement('td');
    r.source_pages.forEach((p, i) => {
      const a = document.createElement('a');
      a.href = `./engine/?workspace=user&sheet=${encodeURIComponent(`${data.document.name}#${p}`)}`;
      a.target = '_blank';
      a.rel = 'noopener';
      a.className = 'page-link';
      a.textContent = `p.${p}`;
      page.append(a);
      if (i < r.source_pages.length - 1) page.append(document.createTextNode(' '));
    });
    tr.append(page);

    const method = document.createElement('td');
    method.textContent = r.method;
    tr.append(method);

    const err = document.createElement('td');
    err.className = 'num';
    err.textContent = '—';
    err.title = 'User PDF runtime has no reference quantity';
    tr.append(err);
    frag.append(tr);
  }
  if (!(data.rows || []).length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 7;
    td.className = 'empty';
    td.textContent = 'ยังไม่พบรายการที่ปล่อยอัตโนมัติได้อย่างปลอดภัย — ดู WITHHELD ด้านล่างและใช้ Manual/Review สำหรับส่วนที่เหลือ';
    tr.append(td);
    frag.append(tr);
  }
  $('#auto-rows-body').replaceChildren(frag);
  $('#auto-rows').textContent = data.rows.length;
  $('#auto-coverage').textContent = '—';
  $('#auto-accuracy').textContent = '—';
  $('#auto-mae').textContent = '—';
  const d = data.document;
  $('#auto-note').textContent = `Browser Runtime Alpha · ${d.name} · อ่าน ${d.scanned_pages}/${d.pages} หน้า · reference isolation = true · pipe length ยัง WITHHELD`;
  renderWithheld(data.coverage?.withheld_detectors || []);
  const runtimeDownload = $('#user-auto-json');
  if (runtimeDownload) runtimeDownload.disabled = false;
}

async function loadDemoAuto() {
  try {
    const [a, b] = await Promise.all([
      fetch('./auto-boq.json', { cache: 'no-store' }),
      fetch('./auto-boq-benchmark.json', { cache: 'no-store' }),
    ]);
    if (!a.ok || !b.ok) throw new Error('automatic BOQ build artifacts missing');
    autoData = await a.json();
    benchmark = await b.json();
    if (autoData.schema !== 'blender3d.auto_boq.v1' || benchmark.schema !== 'blender3d.auto_boq.benchmark.v1') throw new Error('automatic BOQ schema mismatch');
    if (autoData.source_policy.reference_used_for_generation !== false) throw new Error('reference isolation not proven');
    renderDemoAuto();
  } catch (e) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 7;
    td.className = 'empty';
    td.textContent = `Automatic BOQ โหลดไม่สำเร็จ: ${e.message}`;
    tr.append(td);
    $('#auto-rows-body').replaceChildren(tr);
    $('#auto-note').textContent = 'Automatic BOQ artifact error';
  }
}

async function runUserPdfRuntime(pdf) {
  if (workspace !== 'user' || !pdf?.bytes || userRuntimeBusy) return;
  const bytes = pdf.bytes instanceof Uint8Array ? pdf.bytes : new Uint8Array(pdf.bytes);
  const fingerprint = `${pdf.name}:${bytes.byteLength}`;
  if (fingerprint === userRuntimeFingerprint && userRuntimeData) {
    renderUserAuto(userRuntimeData);
    return;
  }
  userRuntimeBusy = true;
  setStatus('กำลังถอด Automatic Alpha จาก PDF ของคุณ…', 'loading');
  renderUserPlaceholder(`กำลังอ่าน ${pdf.name} ด้วย PDF.js ใน browser…`);
  try {
    const [runtime, pdfjs] = await Promise.all([
      import('./browser-auto-boq.mjs'),
      import('./vendor/pdf.mjs'),
    ]);
    pdfjs.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdf.worker.mjs', import.meta.url).href;
    const result = await runtime.extractBrowserAutoBoq({ bytes, name: pdf.name, pdfjs });
    if (result.source_policy?.reference_used_for_generation !== false) throw new Error('reference isolation failed');
    userRuntimeData = result;
    userRuntimeFingerprint = fingerprint;
    renderUserAuto(result);
    setStatus(`Automatic Alpha เสร็จ · ${result.rows.length} รายการปลอดภัย`, 'ready');
  } catch (error) {
    userRuntimeData = null;
    renderUserPlaceholder(`Automatic Alpha ยังรันไม่สำเร็จ: ${error.message}`);
    setStatus('Automatic Alpha ต้องตรวจแก้', 'error');
  } finally {
    userRuntimeBusy = false;
  }
}

window.addEventListener('message', e => {
  if (e.origin !== location.origin || e.source !== frame.contentWindow || e.data?.workspace !== workspace) return;
  if (e.data.type === 'ot-poc:report') {
    if (e.data.report?.schema !== 'blender3d.takeoff-poc.v1' || !Array.isArray(e.data.report.rows)) return;
    snapshot = e.data;
    lastReceived = Date.now();
    manualRender();
    setStatus('เครื่องมือพร้อม · บันทึกในเบราว์เซอร์', 'ready');
    $('#engine-error').hidden = true;
    if (workspace === 'user') requestUserPdf();
  } else if (e.data.type === 'ot-poc:ready') {
    setStatus('เครื่องมือพร้อม · บันทึกในเบราว์เซอร์', 'ready');
    request();
    if (workspace === 'user') requestUserPdf(true);
  } else if (e.data.type === 'ot-poc:pdf') {
    if (workspace !== 'user') return;
    if (!e.data.pdf) {
      userRuntimeData = null;
      userRuntimeFingerprint = '';
      renderUserPlaceholder();
      return;
    }
    runUserPdfRuntime(e.data.pdf);
  } else if (e.data.type === 'ot-poc:error') {
    setStatus('เปิดเครื่องมือไม่สำเร็จ', 'error');
    $('#engine-error').hidden = false;
    $('#error-text').textContent = e.data.message;
  }
});

function setWorkspaceAutoControls() {
  const demo = workspace === 'demo';
  const demoJson = $('#auto-json-download');
  const accuracy = $('#accuracy-download');
  const userJson = $('#user-auto-json');
  if (demoJson) demoJson.hidden = !demo;
  if (accuracy) accuracy.hidden = !demo;
  if (userJson) {
    userJson.hidden = demo;
    userJson.disabled = !userRuntimeData;
  }
}

$('#workspace').addEventListener('change', e => {
  workspace = e.target.value === 'demo' ? 'demo' : 'user';
  snapshot = null;
  lastReceived = 0;
  $('#csv').disabled = true;
  $('#json').disabled = true;
  for (const kind of Object.keys(names)) $(`#${kind}-total`).textContent = '—';
  $('#rows').replaceChildren();
  $('#review-note').textContent = 'กำลังอ่านพื้นที่ทำงานที่เลือก…';
  const autoButton = document.querySelector('[data-tab="auto"]');
  autoButton.disabled = false;
  $('#workspace-note').textContent = workspace === 'demo'
    ? 'Automatic detector อ่านเฉพาะหน้ารูปแบบ 1–71; BOQ หน้า 72+ ใช้ตรวจคะแนนภายหลังเท่านั้น'
    : 'PDF ของคุณจะรัน Browser Automatic Alpha หลังอัปโหลด: ปล่อยเฉพาะ explicit sanitary tags ที่ชัดเจน และ WITHHOLD สิ่งที่ยังพิสูจน์ไม่ได้';
  const url = `./engine/?workspace=${workspace}`;
  frame.src = url;
  $('#full-engine').href = url;
  $('#reference-boq').hidden = workspace !== 'demo';
  setStatus('กำลังเปิดพื้นที่ทำงาน…', 'loading');
  $('#engine-error').hidden = true;
  setWorkspaceAutoControls();
  if (workspace === 'demo') {
    renderDemoAuto();
    tab('auto');
  } else {
    renderUserPlaceholder();
    tab('plan');
  }
});

function download(content, name, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

$('#csv').onclick = () => snapshot && download(metricCsv(snapshot.report), `takeoff-${workspace}-preliminary.csv`, 'text/csv;charset=utf-8');
$('#json').onclick = () => snapshot && download(JSON.stringify(snapshot.takeoff, null, 2), `takeoff-${workspace}.json`, 'application/json');
$('#user-auto-json').onclick = () => userRuntimeData && download(JSON.stringify(userRuntimeData, null, 2), `auto-boq-${userRuntimeData.document.name}.json`, 'application/json');
$('#refresh').onclick = request;
$('#retry').onclick = () => {
  frame.src = `./engine/?workspace=${workspace}`;
  $('#engine-error').hidden = true;
  setStatus('กำลังลองใหม่…', 'loading');
};
frame.addEventListener('load', () => {
  request();
  if (workspace === 'user') requestUserPdf(true);
});
setInterval(() => {
  if (!document.hidden) {
    request();
    if (workspace === 'user') requestUserPdf();
  }
}, 4000);
setTimeout(() => {
  if (!lastReceived) setStatus('เครื่องมือ review ยังไม่ตอบกลับ — Automatic BOQ ยังดูได้', 'error');
}, 60000);

setWorkspaceAutoControls();
loadDemoAuto();
