import assert from 'node:assert/strict';
import { classifyDrawingPage, groupPdfTextItems, parseSanitaryLines } from './browser-auto-boq.mjs';

const grouped = groupPdfTextItems([
  { str: 'WC.', transform: [1,0,0,1,100,500] },
  { str: 'LAV.', transform: [1,0,0,1,140,500] },
  { str: 'FD.', transform: [1,0,0,1,180,500] },
  { str: 'other', transform: [1,0,0,1,100,450] },
]);
assert.equal(grouped.length, 2);
assert.match(grouped[0].text, /WC\. LAV\. FD\./);

const schematicLines = [
  { text: 'A-3 1:50 SN-04', x: 100, y: 700 },
  { text: '+3.75 +0.60 +0.00', x: 100, y: 680 },
  { text: 'Ø3/4"CW', x: 100, y: 620 },
  { text: 'Ø2"V', x: 100, y: 600 },
  { text: 'Ø2"AVC', x: 120, y: 560 },
  { text: 'Ø2"AVC', x: 240, y: 560 },
];
const primaryLines = [
  { text: 'A-3 1:100 SN-06', x: 100, y: 700 },
  { text: 'Ø2 1/2"RFD', x: 200, y: 520 },
  { text: 'Ø2 1/2"RFD+RL', x: 320, y: 520 },
];
const detailLines = [
  { text: 'A-3 1:50 SN-07', x: 100, y: 700 },
  { text: '1 : 50', x: 200, y: 680 },
  { text: '1 : 50', x: 300, y: 680 },
  { text: 'WC. WC1. LAV. UR. SH. C. SINK. FD.', x: 100, y: 400 },
  { text: 'FCO FCO CO', x: 100, y: 360 },
  { text: 'Ø2"AVC', x: 120, y: 320 },
  { text: 'Ø2"AVC', x: 240, y: 320 },
  { text: 'Ø2"FD', x: 300, y: 300 },
];

assert.equal(classifyDrawingPage(schematicLines).role, 'vertical_schematic');
assert.equal(classifyDrawingPage(primaryLines).role, 'primary_plan');
assert.equal(classifyDrawingPage(detailLines).role, 'detail_plan');
assert.equal(classifyDrawingPage([{ text: 'FCO CO', x: 0, y: 0 }]).role, 'unknown');

const parsed = parseSanitaryLines([
  { page: 57, lines: schematicLines },
  { page: 59, lines: primaryLines },
  {
    page: 60,
    lines: detailLines,
    items: [
      { text: 'FCO', x: 110, y: 360 },
      { text: 'FCO', x: 180, y: 360 },
      { text: 'CO', x: 250, y: 360 },
    ],
  },
  {
    page: 78,
    lines: [{ text: 'FCO CO', x: 100, y: 500 }],
    items: [{ text: 'FCO', x: 100, y: 500 }, { text: 'CO', x: 180, y: 500 }],
  },
]);

const by = new Map(parsed.rows.map(row => [row.id, row]));
assert.equal(parsed.rows.length, 4);
assert.equal(by.get('SAN-AVC-2').quantity, 2);
assert.deepEqual(by.get('SAN-AVC-2').source_pages, [60]);
assert.equal(by.get('SAN-RFD-2.5').quantity, 2);
assert.deepEqual(by.get('SAN-RFD-2.5').source_pages, [59]);
assert.equal(by.get('SAN-FCO-UNSIZED').quantity, 2);
assert.deepEqual(by.get('SAN-FCO-UNSIZED').source_pages, [60]);
assert.equal(by.get('SAN-FCO-UNSIZED').evidence.size_status, 'WITHHELD_NO_EXPLICIT_SIZE');
assert.equal(by.get('SAN-CO-UNSIZED').quantity, 1);
assert.deepEqual(by.get('SAN-CO-UNSIZED').source_pages, [60]);
assert.equal(by.get('SAN-CO-UNSIZED').evidence.size_status, 'WITHHELD_NO_EXPLICIT_SIZE');
assert.ok(!by.has('SAN-FCO-4'));
assert.ok(!by.has('SAN-CO-2.5'));
assert.ok(!by.has('SAN-FLOOR-DRAIN-2'));

assert.equal(parsed.crossViewSuppressed.length, 2);
assert.ok(parsed.crossViewSuppressed.every(x => x.id === 'SAN-AVC-2' && x.page === 57));
assert.ok(parsed.crossViewSuppressed.every(x => x.suppressed_reason === 'NON_ADDITIVE_CROSS_VIEW_DETAIL_PRECEDENCE'));
assert.equal(parsed.withheldStandalone.length, 2);
assert.ok(parsed.withheldStandalone.every(x => x.page === 78));
assert.equal(parsed.floorDrainEvidence.length, 1);
assert.equal(parsed.pipeTags.length, 2);
assert.deepEqual(parsed.pipeTags.map(x => [x.system, x.dn]), [['CW',20],['V',50]]);

const roles = new Map(parsed.pageRoles.map(x => [x.page, x.role]));
assert.equal(roles.get(57), 'vertical_schematic');
assert.equal(roles.get(59), 'primary_plan');
assert.equal(roles.get(60), 'detail_plan');
assert.equal(roles.get(78), 'unknown');

console.log('BROWSER_AUTO_BOQ_RUNTIME_TEST_PASS', {
  rows: parsed.rows.length,
  avcReleased: by.get('SAN-AVC-2').quantity,
  avcCrossViewSuppressed: parsed.crossViewSuppressed.length,
  fcoUnsized: by.get('SAN-FCO-UNSIZED').quantity,
  coUnsized: by.get('SAN-CO-UNSIZED').quantity,
  unknownStandaloneWithheld: parsed.withheldStandalone.length,
});
