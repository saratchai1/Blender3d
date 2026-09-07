import assert from 'node:assert/strict';
import { groupPdfTextItems, parseSanitaryLines } from './browser-auto-boq.mjs';

const grouped = groupPdfTextItems([
  { str: 'Ø4"FCO', transform: [1,0,0,1,100,500] },
  { str: 'Ø2 1/2"CO', transform: [1,0,0,1,220,501] },
  { str: 'other', transform: [1,0,0,1,100,450] },
]);
assert.equal(grouped.length, 2);
assert.match(grouped[0].text, /FCO/);
assert.match(grouped[0].text, /CO/);

const parsed = parseSanitaryLines([
  {
    page: 57,
    lines: [
      { text: 'Ø4"FCO   Ø2 1/2"CO   Ø2 1/2"RFD   Ø2"AVC', x: 100, y: 500 },
      { text: 'Ø2"FD', x: 120, y: 450 },
      { text: 'Ø3/4"CW  Ø4"SW  Ø2"V', x: 130, y: 400 },
    ],
  },
  {
    page: 58,
    lines: [
      { text: 'Ø4"FCO', x: 140, y: 300 },
      { text: 'Ø2"FD', x: 150, y: 250 },
      { text: 'Ø1/2"CW', x: 160, y: 200 },
    ],
  },
]);

const by = new Map(parsed.rows.map(row => [row.id, row]));
assert.equal(by.get('SAN-FCO-4').quantity, 2);
assert.deepEqual(by.get('SAN-FCO-4').source_pages, [57,58]);
assert.equal(by.get('SAN-CO-2.5').quantity, 1);
assert.equal(by.get('SAN-RFD-2.5').quantity, 1);
assert.equal(by.get('SAN-AVC-2').quantity, 1);
assert.equal(parsed.floorDrainEvidence.length, 2);
assert.equal(parsed.pipeTags.length, 4);
assert.deepEqual(
  parsed.pipeTags.map(x => [x.system, x.dn]),
  [['CW',20],['SW',100],['V',50],['CW',15]],
);
assert.ok(!by.has('SAN-FLOOR-DRAIN-2'));

console.log('BROWSER_AUTO_BOQ_RUNTIME_TEST_PASS', {
  rows: parsed.rows.length,
  floorDrainWithheld: parsed.floorDrainEvidence.length,
  pipeTagsEvidenceOnly: parsed.pipeTags.length,
});
