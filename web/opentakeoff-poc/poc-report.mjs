/** Downstream adapter: upstream totals are canonical; do not infer metric units from key names. */
export function toMetricReport(payload, conditionTotals) {
  const conditions=Array.isArray(payload?.conditions)?payload.conditions:[];
  const shapes=Array.isArray(payload?.shapes)?payload.shapes:[];
  const groups=[
    {kind:'floor',roles:['floor_area','deduct'],raw:'floor_sf',order:'floor_sf_net',unit:'m²',factor:0.09290304},
    {kind:'wall',roles:['surface_area'],raw:'wall_sf',order:'wall_sf_net',unit:'m²',factor:0.09290304},
    {kind:'linear',roles:['linear'],raw:'lf',order:'lf_net',unit:'m',factor:0.3048},
    {kind:'count',roles:['count'],raw:'ea',order:'ea',unit:'ea',factor:1},
  ];
  const rows=[];
  for(const g of groups){
    const subset=shapes.filter(s=>g.roles.includes(s.measure_role));
    for(const total of conditionTotals(conditions,subset)){
      if(!total.shape_count)continue;
      const measured=subset.filter(s=>s.condition_id===total.id);
      const net=Number(total[g.raw])*g.factor;
      const order=Number(total[g.order])*g.factor;
      const pending=measured.filter(s=>s.origin?.reviewed===false).length;
      const invalid=!Number.isFinite(net)||!Number.isFinite(order)||net<0||order<0;
      rows.push({id:`${total.id}:${g.kind}`,condition_id:total.id,description:total.finish_tag,kind:g.kind,
        unit:g.unit,net:invalid?null:net,order:invalid?null:order,waste_pct:g.kind==='count'?0:total.waste_pct,
        multiplier:total.multiplier,shapes:measured.map(s=>s.id),sheets:[...new Set(measured.map(s=>s.sheet_id))],
        pending,review:invalid?'INVALID_QUANTITY':pending?'PENDING_REVIEW':'NOT_CERTIFIED',source:'2D_OPEN_TAKEOFF',
        warning:invalid?'Invalid or negative quantity: review drawing and deductions.':null});
    }
  }
  return {schema:'blender3d.takeoff-poc.v1',project:payload?.project_name||'My takeoff',
    generated_at:new Date().toISOString(),status:'PRELIMINARY_NOT_FOR_PROCUREMENT',units:'metric',rows,
    shape_count:shapes.length,pending:shapes.filter(s=>s.origin?.reviewed===false).length,
    warning:'No IFC reconciliation. No certified BOQ. Waste and any entered unit rates require review.',
    note:'Native engine quantities are stored in ft/SF. SI conversion uses exact 0.3048 m/ft; upstream 2-decimal rounding may cause <0.01 m² differences.'};
}
export function csvCell(value){
  let s=String(value??'');
  if(/^[\s]*[=+@-]/.test(s)) s="'"+s; // spreadsheet formula injection protection
  return '"'+s.replaceAll('"','""')+'"';
}
export function metricCsv(report){
  const headers=['Description','Kind','Net quantity','Waste %','Order quantity','Unit','Source','Review','Sheet','Shape IDs'];
  const rows=report.rows.map(r=>[r.description,r.kind,r.net==null?'':r.net.toFixed(3),r.waste_pct,r.order==null?'':r.order.toFixed(3),r.unit,r.source,r.review,r.sheets.join('; '),r.shapes.join('; ')]);
  return '\ufeff'+[headers,...rows].map(r=>r.map(csvCell).join(',')).join('\r\n');
}
