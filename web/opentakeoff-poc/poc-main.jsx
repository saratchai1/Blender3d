// Blender3d downstream entry point. Upstream measurement code is unmodified.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router';
import { PDFDocument, StandardFonts, rgb } from 'pdf-lib';
import TakeoffCanvas from './pages/TakeoffCanvas.jsx';
import { GoogleAuthProvider } from './lib/google/AuthContext.jsx';
import { localStore, emptyAnnotations } from './lib/store.js';
import { conditionTotals } from './lib/totals.js';
import { computeShapeMetrics } from './lib/shapeMetrics.js';
import { RENDER_SCALE } from './lib/sheets';
import { initTheme } from './lib/theme.js';
import { initDrawStyle } from './lib/drawStyles.js';
import { initDraftOutline } from './lib/draftOutline.js';
import './styles/tokens.css';
import './styles/app.css';
import './styles/print.css';
import { toMetricReport } from './poc-report.mjs';

const workspace = new URLSearchParams(location.search).get('workspace') === 'demo' ? 'demo' : 'user';
const UPSTREAM = '7a3c8eb44252d0d9083157ad9677866f92f711bb';
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
  if ((await localStore.listSheets()).length) return; // Never overwrite previous work.
  const name = 'POC-OFFICE-240m2.pdf';
  const W=1000, H=720, X=110, Y=118, K=36; // PDF points; top-left drawing frame.
  const doc = await PDFDocument.create();
  doc.setTitle('OpenTakeoff POC | Synthetic 240 m2 office');
  const page=doc.addPage([W,H]);
  const font=await doc.embedFont(StandardFonts.Helvetica);
  const bold=await doc.embedFont(StandardFonts.HelveticaBold);
  const text=(s,x,y,size=11,strong=false)=>page.drawText(s,{x,y:H-y-size,size,font:strong?bold:font,color:rgb(.12,.18,.24)});
  const line=(x1,y1,x2,y2,width=1)=>page.drawLine({start:{x:x1,y:H-y1},end:{x:x2,y:H-y2},thickness:width,color:rgb(.2,.28,.33)});
  text('BLENDER3D / OPENTAKEOFF LAB',55,32,12,true);
  text('OFFICE FINISH PLAN',55,53,25,true);
  text('Synthetic test drawing - NOT the SOLSTICE 14 design - NOT FOR CONSTRUCTION',55,90,10);
  const rooms=[
    {id:'CPT-01',label:'OPEN OFFICE',x:0,y:0,w:12,h:8,color:'#4a85b7',waste:7},
    {id:'CPT-02',label:'MEETING ROOM',x:12,y:0,w:8,h:5,color:'#ad8053',waste:5},
    {id:'TIL-01',label:'PANTRY',x:12,y:5,w:8,h:3,color:'#438d77',waste:8},
    {id:'VIN-01',label:'CIRCULATION',x:0,y:8,w:20,h:4,color:'#8676b1',waste:3},
  ];
  const conditions=rooms.map(r=>({id:r.id,finish_tag:`${r.id} ${r.label}`,color:r.color,fill:'solid',hatch:'',multiplier:1,waste_pct:r.waste,materials:[]}));
  conditions.push(
    {id:'BASE-01',finish_tag:'BASE-01 Skirting demo',color:'#b78638',fill:'solid',hatch:'',multiplier:1,waste_pct:5,materials:[],thickness_in:0},
    {id:'PNT-01',finish_tag:'PNT-01 Wall finish H=3m',color:'#ac6069',fill:'solid',hatch:'',multiplier:1,waste_pct:5,materials:[],height_ft:3/.3048},
    {id:'LGT-01',finish_tag:'LGT-01 Light fittings',color:'#48546f',fill:'solid',hatch:'',multiplier:1,waste_pct:0,materials:[]}
  );
  const shapes=[];
  function addShape(id,condition,role,points,label,extra={}) {
    const shape={id,sheet_id:name,condition_id:condition,measure_role:role,
      verts_norm:points.map(([x,y])=>[(X+x*K)/W,(Y+y*K)/H]),label,
      author:'Scripted POC fixture (not AI detection)',created_at:new Date().toISOString(),
      origin:{actor:'agent',method:'poc_fixture_v1',reviewed:false},...extra};
    shape.computed=computeShapeMetrics(shape,{w:W*RENDER_SCALE,h:H*RENDER_SCALE},1/(K*RENDER_SCALE*.3048),conditions.find(c=>c.id===condition));
    shapes.push(shape);
  }
  for(const r of rooms){
    page.drawRectangle({x:X+r.x*K,y:H-(Y+(r.y+r.h)*K),width:r.w*K,height:r.h*K,borderWidth:2,borderColor:rgb(.16,.22,.27),color:rgb(.98,.98,.97)});
    const xx=X+(r.x+r.w/2)*K, yy=Y+(r.y+r.h/2)*K;
    text(r.label,xx-r.label.length*3.2,yy-13,12,true);
    text(`${r.w}m x ${r.h}m  /  ${r.id}`,xx-60,yy+7,10);
    addShape(`room-${r.id}`,r.id,'floor_area',[[r.x,r.y],[r.x+r.w,r.y],[r.x+r.w,r.y+r.h],[r.x,r.y+r.h]],r.label);
  }
  // Dimension strings are true to the geometry; scaling is also explicitly seeded.
  line(X,Y+12*K+28,X+20*K,Y+12*K+28);
  for (const x of [X,X+20*K]) line(x,Y+12*K+20,x,Y+12*K+36);
  text('20.00 m',X+10*K-24,Y+12*K+34,12,true);
  line(X-32,Y,X-32,Y+12*K);
  for (const y of [Y,Y+12*K]) line(X-40,y,X-24,y);
  text('12.00 m',15,Y+6*K,11,true);
  addShape('skirting','BASE-01','linear',[[0,12],[20,12]],'South edge: 20m');
  addShape('wall-paint','PNT-01','surface_area',[[0,0],[20,0]],'North wall: 20m x 3m',{height_ft:3/.3048});
  [[3,2],[6,2],[9,2],[3,6],[6,6],[9,6]].forEach(([x,y],i)=>{
    const px=X+x*K,py=Y+y*K;
    page.drawCircle({x:px,y:H-py,size:6,borderWidth:1,borderColor:rgb(.23,.3,.38)});
    line(px-4,py,px+4,py);line(px,py-4,px,py+4);
    addShape(`light-${i+1}`,'LGT-01','count',[[x,y]],`Light ${i+1}`);
  });
  text('EXPECTED CHECKS',55,636,11,true);
  text('Floor: 96 + 40 + 24 + 80 = 240 m2 | Wall finish: 60 m2 | Skirting: 20m | Lights: 6',55,655,11);
  text('Areas exclude no wall thickness/openings. Waste is illustrative. Traces are scripted review proposals, not automatic room detection.',55,678,9);
  await localStore.addPdf(new File([await doc.save()],name,{type:'application/pdf'}));
  const payload={...emptyAnnotations(),project_name:'POC / Synthetic office 240 m2',units:'metric',conditions,shapes,
    sheets:[{sheet_id:name,units_per_px:1/(K*RENDER_SCALE*.3048),scale_source:'synthetic metric fixture',scale_confirmed:false}],
    sheet_tabs:[name],sheet_group:[name],last_group:[name],sheet_levels:{[name]:'POC - not a real building floor'},
    shape_labels:rooms.map(r=>r.label)};
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
  el.textContent=`OpenTakeoff could not open local storage: ${error.message}. Try a normal browser tab with storage enabled.`;
  post('ot-poc:error',{message:error.message});
});
