// Blender3d downstream entry point. Upstream measurement code is unmodified.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router';
import TakeoffCanvas from './pages/TakeoffCanvas.jsx';
import { GoogleAuthProvider } from './lib/google/AuthContext.jsx';
import { localStore, emptyAnnotations } from './lib/store.js';
import { conditionTotals } from './lib/totals.js';
import { initTheme } from './lib/theme.js';
import { initDrawStyle } from './lib/drawStyles.js';
import { initDraftOutline } from './lib/draftOutline.js';
import './styles/tokens.css';
import './styles/app.css';
import './styles/print.css';
import { toMetricReport } from './poc-report.mjs';

const workspace = new URLSearchParams(location.search).get('workspace') === 'demo' ? 'demo' : 'user';
const UPSTREAM = '7a3c8eb44252d0d9083157ad9677866f92f711bb';
const DEMO_NAME = 'family4.pdf';
const DEMO_START_PAGE = 11; // Original PDF: architectural ground-floor plan, 1:100.
function post(type, data) {
  if (parent !== window) parent.postMessage({type, workspace, ...data}, location.origin);
}
function report(payload) {
  const result = toMetricReport(payload, conditionTotals);
  post('ot-poc:report', { report: result, takeoff: payload, upstream: UPSTREAM });
}
const originalSave = localStore.saveAnnotations.bind(localStore);
localStore.saveAnnotations = async (payload) => {
  await originalSave(payload);
  report(payload);
};
window.addEventListener('message', async (event) => {
  if (event.origin !== location.origin || event.source !== parent || event.data?.type !== 'ot-poc:refresh') return;
  try { report(await localStore.loadAnnotations()); }
  catch (error) { post('ot-poc:error', {message: String(error.message || error)}); }
});

async function seedDemo() {
  if ((await localStore.listSheets()).length) return; // Never overwrite benchmark edits.
  const response = await fetch('../demo/family4.pdf', { cache: 'force-cache' });
  if (!response.ok) throw new Error(`Could not load the verified Family 4 benchmark PDF (${response.status}).`);
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== 13058241 || String.fromCharCode(...new Uint8Array(bytes.slice(0, 5))) !== '%PDF-') {
    throw new Error('Family 4 benchmark PDF failed the runtime size/header check.');
  }
  await localStore.addPdf(new File([bytes], DEMO_NAME, {type:'application/pdf'}));
  // Intentionally seed ZERO takeoff shapes. The official BOQ later in this same
  // document is a benchmark/reference, never smuggled into generated quantities.
  const payload={...emptyAnnotations(),
    project_name:'บ้านครอบครัวไทยร่วมสมัย 4 — BOQ accuracy benchmark',
    units:'metric',conditions:[],shapes:[],
    sheet_tabs:[`${DEMO_NAME}#${DEMO_START_PAGE}`],sheet_group:[],last_group:[],
    sheet_levels:{
      [`${DEMO_NAME}#${DEMO_START_PAGE}`]:'Architecture — floor plan',
      [`${DEMO_NAME}#72`]:'Reference BOQ — spread footing',
      [`${DEMO_NAME}#84`]:'Reference BOQ — pile foundation',
    }
  };
  await originalSave(payload);
}

async function boot(){
  // POC defaults to SI display. The upstream storage contract remains feet/SF.
  try { if(!localStorage.getItem('opentakeoff_units')) localStorage.setItem('opentakeoff_units','metric'); } catch { /* private browsing */ }
  initTheme();initDrawStyle();initDraftOutline();
  if(workspace==='demo') await seedDemo();
  createRoot(document.getElementById('root')).render(<MemoryRouter><GoogleAuthProvider><TakeoffCanvas /></GoogleAuthProvider></MemoryRouter>);
  report(await localStore.loadAnnotations());
  post('ot-poc:ready',{});
}
boot().catch(error=>{
  const el=document.getElementById('root');
  el.textContent=`OpenTakeoff could not open local storage/sample: ${error.message}. Try a normal browser tab with storage enabled.`;
  post('ot-poc:error',{message:error.message});
});
