import {test} from 'node:test';
import assert from 'node:assert/strict';
import {toMetricReport,metricCsv,csvCell} from './poc-report.mjs';
const payload={project_name:'POC',conditions:[{id:'c',finish_tag:'=bad',multiplier:1,waste_pct:10}],shapes:[
 {id:'a',condition_id:'c',sheet_id:'test.pdf',measure_role:'floor_area',origin:{reviewed:false}},
 {id:'l',condition_id:'c',sheet_id:'test.pdf',measure_role:'linear'},
 {id:'p',condition_id:'c',sheet_id:'test.pdf',measure_role:'count'}]};
const fakeTotals=(conditions,shapes)=>conditions.map(c=>({id:c.id,finish_tag:c.finish_tag,shape_count:shapes.length,waste_pct:10,multiplier:1,
 floor_sf:100,floor_sf_net:110,wall_sf:10,wall_sf_net:11,lf:20,lf_net:22,ea:2}));
test('Uses canonical engine outputs, exact SI conversions, and separates unlike roles',()=>{
 const r=toMetricReport(payload,fakeTotals);assert.equal(r.rows.length,3);
 assert.equal(r.rows[0].net,100*.09290304);assert.equal(r.rows[0].order,110*.09290304);
 assert.equal(r.rows[1].net,20*.3048);assert.equal(r.rows[1].unit,'m');
 assert.equal(r.rows[2].order,2);assert.equal(r.rows[2].waste_pct,0);
 assert.deepEqual(r.rows[0].shapes,['a']);assert.equal(r.rows[0].pending,1);
 assert.equal(r.status,'PRELIMINARY_NOT_FOR_PROCUREMENT');
});
test('Does not combine IFC quantities or price anything',()=>{
 const r=toMetricReport({...payload,ifc_quantity:999999},fakeTotals);
 assert.equal(r.rows[0].net,100*.09290304);assert.equal(r.rows[0].source,'2D_OPEN_TAKEOFF');
 assert.equal('cost' in r.rows[0],false);
});
test('CSV preserves source IDs and protects spreadsheet formula injection',()=>{
 assert.equal(csvCell('=1+2'),'"\'=1+2"');assert.equal(csvCell('a"b'),'"a""b"');
 const csv=metricCsv(toMetricReport(payload,fakeTotals));assert.ok(csv.startsWith('\ufeff'));
 assert.ok(csv.includes('PENDING_REVIEW'));assert.ok(csv.includes('test.pdf'));assert.ok(csv.includes("'=bad"));
});
test('Invalid, negative and nonfinite totals are withheld',()=>{
 const invalid=()=>[{id:'c',shape_count:1,floor_sf:-1,floor_sf_net:NaN}];
 const row=toMetricReport(payload,invalid).rows[0];assert.equal(row.net,null);assert.equal(row.review,'INVALID_QUANTITY');
});
test('Empty workspace is not filled with invented sample quantities',()=>{
 const r=toMetricReport({},()=>[]);assert.equal(r.rows.length,0);assert.equal(r.shape_count,0);
});
