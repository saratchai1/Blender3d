import { metricCsv } from './poc-report.mjs';
const $=s=>document.querySelector(s);
let snapshot=null,workspace='demo',lastReceived=0;
const frame=$('#engine'), status=$('#status');
const fmt=(n,d=2)=>Number(n).toLocaleString('th-TH',{minimumFractionDigits:d,maximumFractionDigits:d});
const names={floor:'พื้นที่พื้น',wall:'ผิวผนัง',linear:'ความยาว',count:'จำนวน'};
function request(){frame.contentWindow?.postMessage({type:'ot-poc:refresh'},location.origin);}
function tab(name){
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));
  document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('selected',p.id===name));
  if(name==='boq')request();
}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
function setStatus(text,state){status.textContent=text;status.dataset.state=state;}
function render(){
  const r=snapshot?.report;if(!r)return;
  const frag=document.createDocumentFragment();
  for(const row of r.rows){
    const tr=document.createElement('tr');
    const values=[row.description,names[row.kind],row.net==null?'—':fmt(row.net,row.kind==='count'?0:2),fmt(row.waste_pct,0),row.order==null?'—':fmt(row.order,row.kind==='count'?0:2),row.unit,row.pending?`รอตรวจ ${row.pending} จุด`:row.warning?'ต้องตรวจแก้':'เบื้องต้น'];
    values.forEach((v,i)=>{const td=document.createElement('td');td.textContent=v;if([2,3,4].includes(i))td.className='num';if(i===0){const small=document.createElement('small');small.textContent=row.sheets.join(' · ');td.append(small);}tr.append(td);});
    frag.append(tr);
  }
  if(!r.rows.length){const tr=document.createElement('tr');const td=document.createElement('td');td.colSpan=7;td.className='empty';td.textContent='ยังไม่มี Generated Takeoff — เปิดแบบ ตรวจสเกล แล้วเริ่มวัด; ตัวเลข BOQ ที่อยู่ใน PDF จะไม่ถูกนำมาใส่ตรงนี้อัตโนมัติ';tr.append(td);frag.append(tr);}
  $('#rows').replaceChildren(frag);
  for(const kind of Object.keys(names)){
    const rows=r.rows.filter(x=>x.kind===kind);
    $(`#${kind}-total`).textContent=rows.some(x=>x.net==null)?'ต้องตรวจ':fmt(rows.reduce((n,x)=>n+(x.net??0),0),kind==='count'?0:2);
  }
  $('#review-note').textContent=`${r.shape_count} เส้นวัด / จุด · ${r.pending} รายการยังรอตรวจ · generated takeoff เท่านั้น`;
  $('#csv').disabled=!r.rows.length;$('#json').disabled=!snapshot.takeoff;
}
window.addEventListener('message',e=>{
  if(e.origin!==location.origin||e.source!==frame.contentWindow||e.data?.workspace!==workspace)return;
  if(e.data.type==='ot-poc:report'){
    if(e.data.report?.schema!=='blender3d.takeoff-poc.v1'||!Array.isArray(e.data.report.rows))return;
    snapshot=e.data;lastReceived=Date.now();render();setStatus('เครื่องมือพร้อม · บันทึกในเบราว์เซอร์','ready');$('#engine-error').hidden=true;
  }else if(e.data.type==='ot-poc:ready'){setStatus('เครื่องมือพร้อม · บันทึกในเบราว์เซอร์','ready');request();}
  else if(e.data.type==='ot-poc:error'){setStatus('เปิดเครื่องมือไม่สำเร็จ','error');$('#engine-error').hidden=false;$('#error-text').textContent=e.data.message;}
});
$('#workspace').addEventListener('change',e=>{
  workspace=e.target.value==='demo'?'demo':'user';snapshot=null;lastReceived=0;
  $('#csv').disabled=true;$('#json').disabled=true;
  for(const kind of Object.keys(names))$(`#${kind}-total`).textContent='—';
  $('#rows').replaceChildren();$('#review-note').textContent='กำลังอ่านพื้นที่ทำงานที่เลือก…';
  $('#workspace-note').textContent=workspace==='demo'?'ตัวอย่างจริง 99 หน้า พร้อม BOQ อ้างอิงช่วงหน้า 72–95 — ใช้หน้าต้นเล่มทำ takeoff แล้วค่อยตรวจเทียบคำตอบ':'แบบของคุณแยกจากตัวอย่าง — ตั้ง/ตรวจสเกลแต่ละแผ่นก่อนวัด และสำรอง Project export ก่อนล้างข้อมูลเบราว์เซอร์';
  const url=`./engine/?workspace=${workspace}`;frame.src=url;$('#full-engine').href=url;
  $('#reference-boq').hidden=workspace!=='demo';
  setStatus('กำลังเปิดพื้นที่ทำงาน…','loading');$('#engine-error').hidden=true;tab('plan');
});
function download(content,name,type){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
$('#csv').onclick=()=>snapshot&&download(metricCsv(snapshot.report),`takeoff-${workspace}-preliminary.csv`,'text/csv;charset=utf-8');
$('#json').onclick=()=>snapshot&&download(JSON.stringify(snapshot.takeoff,null,2),`takeoff-${workspace}.json`,'application/json');
$('#refresh').onclick=request;
$('#retry').onclick=()=>{frame.src=`./engine/?workspace=${workspace}`;$('#engine-error').hidden=true;setStatus('กำลังลองใหม่…','loading');};
frame.addEventListener('load',request);
setInterval(()=>{if(!document.hidden)request();},4000);
setTimeout(()=>{if(!lastReceived){setStatus('เครื่องมือยังไม่ตอบกลับ — ลองเปิดเต็มจอ','error');$('#engine-error').hidden=false;$('#error-text').textContent='การโหลดไฟล์ตัวอย่างจริงอาจใช้เวลามากกว่า demo เดิม หากยังไม่เปิดให้ลองเต็มจอหรือ reload';}},60000);
