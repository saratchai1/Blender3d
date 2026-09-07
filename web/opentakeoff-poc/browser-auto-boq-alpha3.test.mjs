import assert from 'node:assert/strict';
import test from 'node:test';
import { extractRawPositionedPipeTags } from './browser-auto-boq-alpha3.mjs';

function item(str, x, y, width = Math.max(1, String(str).length * 4)) {
  return { str, transform: [1, 0, 0, 1, x, y], width };
}

test('raw positioned tags anchor to the matched text, not the first text item on the baseline', () => {
  const tags = extractRawPositionedPipeTags([
    item('ROOM 101', 20, 500, 35),
    item('Ø2"W', 220, 500, 22),
  ], 58);
  assert.equal(tags.length, 1);
  assert.equal(tags[0].system, 'W');
  assert.equal(tags[0].dn, 50);
  assert.deepEqual(tags[0].position_pt, [220, 500]);
});

test('compact mixed fraction normalizes and RFD+RL contributes explicit RL DN65 evidence', () => {
  const tags = extractRawPositionedPipeTags([
    item('Ø21/2"', 557.8, 410, 28),
    item('RFD+RL', 588, 410, 32),
  ], 59);
  assert.equal(tags.length, 1);
  assert.equal(tags[0].system, 'RL');
  assert.equal(tags[0].diameter_in, '2 1/2');
  assert.equal(tags[0].dn, 65);
  assert.deepEqual(tags[0].position_pt, [557.8, 410]);
  assert.equal(tags[0].tag_source, 'RAW_POSITIONED_COMPOUND_RFD_PLUS_RL');
});

test('split diameter/system items on one nearby baseline still parse with the diameter anchor', () => {
  const tags = extractRawPositionedPipeTags([
    item('Ø3/4"', 300, 240, 26),
    item('CW', 329, 240, 12),
  ], 58);
  assert.equal(tags.length, 1);
  assert.equal(tags[0].system, 'CW');
  assert.equal(tags[0].dn, 20);
  assert.deepEqual(tags[0].position_pt, [300, 240]);
});

test('far-apart same-baseline text is not concatenated into a phantom pipe tag', () => {
  const tags = extractRawPositionedPipeTags([
    item('Ø3/4"', 30, 120, 26),
    item('CW', 400, 120, 12),
  ], 58);
  assert.equal(tags.length, 0);
});
