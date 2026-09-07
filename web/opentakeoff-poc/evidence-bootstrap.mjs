import { evidenceController } from './evidence-viewer.mjs';

async function main() {
  const tbody = document.querySelector('#auto-rows-body');
  const workspace = document.querySelector('#workspace');
  if (!tbody || !workspace) return;
  const response = await fetch('./auto-boq.json', { cache: 'no-store' });
  if (!response.ok) throw new Error('auto-boq.json unavailable for evidence viewer');
  const auto = await response.json();
  if (auto.source_policy?.reference_used_for_generation !== false) throw new Error('evidence viewer requires reference-isolated Automatic BOQ');

  let signature = '';
  const sync = () => {
    const host = evidenceController.ensureHost();
    const demo = workspace.value === 'demo';
    host.hidden = !demo;
    if (!demo) { signature = ''; return; }
    const ids = Array.from(tbody.querySelectorAll('td:first-child small')).map(x => x.textContent || '').filter(Boolean);
    const next = ids.join('|');
    if (!ids.length || next === signature) return;
    signature = next;
    evidenceController.bindRows(tbody, auto, { workspace: 'demo', pdfUrl: './demo/family4.pdf' });
  };

  new MutationObserver(sync).observe(tbody, { childList: true, subtree: true });
  workspace.addEventListener('change', () => { signature = ''; queueMicrotask(sync); });
  sync();
}

main().catch(error => {
  console.error('BOQ_EVIDENCE_VIEWER_ERROR', error);
});
