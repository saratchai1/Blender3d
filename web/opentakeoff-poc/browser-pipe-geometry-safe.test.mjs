import assert from 'node:assert/strict';
import test from 'node:test';
import { buildPipeComponents } from './browser-pipe-geometry.mjs';
import {
  normalizePipeDiameterIn,
  normalizePipeTagDiameter,
  sanitizeExtractedPipeGeometry,
} from './browser-pipe-geometry-safe.mjs';

test('hidden OCG pipe geometry is excluded from both measured segments and semantic layers', () => {
  const safe = sanitizeExtractedPipeGeometry({
    semantic_layers: [
      { id: 'visible', name: 'P-CW', system: 'CW', visible: true },
      { id: 'hidden', name: 'P-CW', system: 'CW', visible: false },
    ],
    segments: [
      { index: 0, layer_id: 'visible', layer_name: 'P-CW', system: 'CW', a: [0, 0], b: [10, 0], length_pt: 10, curved: false },
      { index: 1, layer_id: 'hidden', layer_name: 'P-CW', system: 'CW', a: [0, 2], b: [20, 2], length_pt: 20, curved: false },
    ],
    unsupported: { curved_segments: 0, work_cap_exceeded: false },
  });
  assert.equal(safe.semantic_layers.length, 1);
  assert.equal(safe.segments.length, 1);
  assert.equal(safe.segments[0].source_layer_id, 'visible');
  assert.equal(safe.unsupported.hidden_segments_excluded, 1);
  assert.equal(safe.unsupported.hidden_length_pt_excluded, 20);
});

test('curved CAD figures never contribute to measured pipe denominator but remain explicit evidence', () => {
  const safe = sanitizeExtractedPipeGeometry({
    semantic_layers: [{ id: 'cw', name: 'P-CW', system: 'CW', visible: true }],
    segments: [
      { index: 0, layer_id: 'cw', layer_name: 'P-CW', system: 'CW', a: [0, 0], b: [10, 0], length_pt: 10, curved: false },
      { index: 1, layer_id: 'cw', layer_name: 'P-CW', system: 'CW', a: [10, 0], b: [15, 5], length_pt: 7.071, curved: true },
    ],
    unsupported: { curved_segments: 1, work_cap_exceeded: false },
  });
  assert.equal(safe.segments.length, 1);
  assert.equal(safe.segments[0].length_pt, 10);
  assert.equal(safe.unsupported.curved_segments_source, 1);
  assert.equal(safe.unsupported.curved_length_pt_source, 7.071);
});

test('duplicate OCG ids with the same system and canonical CAD layer name share one topology key', () => {
  const safe = sanitizeExtractedPipeGeometry({
    semantic_layers: [
      { id: 'a', name: 'P-CW', system: 'CW', visible: true },
      { id: 'b', name: 'P_CW', system: 'CW', visible: true },
    ],
    segments: [
      { index: 0, layer_id: 'a', layer_name: 'P-CW', system: 'CW', a: [0, 0], b: [10, 0], length_pt: 10, curved: false },
      { index: 1, layer_id: 'b', layer_name: 'P_CW', system: 'CW', a: [10, 0], b: [20, 0], length_pt: 10, curved: false },
    ],
    unsupported: { curved_segments: 0, work_cap_exceeded: false },
  });
  assert.equal(safe.segments[0].layer_id, safe.segments[1].layer_id);
  const built = buildPipeComponents(safe.segments, 0.01);
  assert.equal(built.components.length, 1);
  assert.deepEqual(built.components[0].segment_indexes, [0, 1]);
});

test('compact mixed fractions normalize before DN inference and null DN never becomes zero', () => {
  assert.equal(normalizePipeDiameterIn('21/2'), '2 1/2');
  assert.equal(normalizePipeDiameterIn('11/2'), '1 1/2');
  assert.equal(normalizePipeDiameterIn('3/4'), '3/4');
  const rl = normalizePipeTagDiameter({ system: 'RL', diameter_in: '21/2', dn: null });
  assert.equal(rl.diameter_in, '2 1/2');
  assert.equal(rl.dn, 65);
  const unknown = normalizePipeTagDiameter({ system: 'CW', diameter_in: '7/8', dn: null });
  assert.equal(unknown.dn, null);
});
