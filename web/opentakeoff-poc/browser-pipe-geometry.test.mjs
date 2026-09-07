import assert from 'node:assert/strict';
import test from 'node:test';
import {
  aggregatePipeAssignments,
  assignPipeDiameters,
  associatePipeTagsToSegments,
  buildPipeComponents,
  extractLayeredPipeSegmentsFromOpList,
  matchPipeLayerSystem,
  parseScaleEvidence,
} from './browser-pipe-geometry.mjs';

const OPS = {
  save: 1, restore: 2, transform: 3,
  beginMarkedContent: 4, beginMarkedContentProps: 5, endMarkedContent: 6,
  constructPath: 7, moveTo: 8, lineTo: 9, curveTo: 10, curveTo2: 11, curveTo3: 12, closePath: 13, rectangle: 14,
  clip: 15, eoClip: 16, endPath: 17, fill: 18, eoFill: 19,
  stroke: 20, closeStroke: 21, fillStroke: 22, eoFillStroke: 23, closeFillStroke: 24, closeEOFillStroke: 25,
  paintFormXObjectBegin: 26, paintFormXObjectEnd: 27,
};

function seg(index, a, b, system = 'CW', layer = 'cw') {
  return { index, a, b, system, layer_id: layer, layer_name: layer, length_pt: Math.hypot(b[0] - a[0], b[1] - a[1]) };
}

test('layer recognition is plumbing-context gated, not a generic one-letter guess', () => {
  assert.equal(matchPipeLayerSystem('P-CW', new Set(['CW'])), 'CW');
  assert.equal(matchPipeLayerSystem('SANITARY-WASTE', new Set(['W'])), 'W');
  assert.equal(matchPipeLayerSystem('V', new Set(['V'])), 'V');
  assert.equal(matchPipeLayerSystem('V', new Set(['CW'])), null);
  assert.equal(matchPipeLayerSystem('A-WALL', new Set(['W'])), null);
});

test('scale evidence releases only one explicit ratio', () => {
  const one = parseScaleEvidence([{ text: 'SCALE 1:100', x: 10, y: 10 }]);
  assert.equal(one.status, 'PASS_UNIQUE_EXPLICIT_SCALE');
  assert.equal(one.unique_ratio, 100);
  const exact = parseScaleEvidence([{ text: '1:50', x: 0, y: 0 }]);
  assert.equal(exact.unique_ratio, 50);
  const ambiguous = parseScaleEvidence([{ text: 'SCALE 1:50' }, { text: 'SCALE 1:100' }]);
  assert.equal(ambiguous.status, 'WITHHELD_AMBIGUOUS_SCALE');
  assert.equal(ambiguous.unique_ratio, null);
});

test('PDF operator extraction keeps only stroked geometry on recognized OCG pipe layers', () => {
  const opList = {
    fnArray: [OPS.beginMarkedContentProps, OPS.constructPath, OPS.stroke, OPS.endMarkedContent, OPS.beginMarkedContentProps, OPS.constructPath, OPS.stroke, OPS.endMarkedContent],
    argsArray: [
      ['OC', { id: 'gCW' }],
      [[OPS.moveTo, OPS.lineTo, OPS.lineTo], [0, 0, 100, 0, 100, 50]],
      [], [],
      ['OC', { id: 'gWall' }],
      [[OPS.moveTo, OPS.lineTo], [0, 20, 100, 20]],
      [], [],
    ],
  };
  const out = extractLayeredPipeSegmentsFromOpList({
    opList,
    viewportTransform: [1, 0, 0, 1, 0, 0],
    OPS,
    groups: { gCW: { name: 'P-CW' }, gWall: { name: 'A-WALL' } },
    pageTagSystems: new Set(['CW']),
  });
  assert.equal(out.semantic_layers.length, 1);
  assert.equal(out.segments.length, 2);
  assert.deepEqual(out.segments.map(s => Math.round(s.length_pt)), [100, 50]);
});

test('topology connects endpoint/T junctions but never interior/interior X crossings', () => {
  const t = [seg(0, [0, 5], [10, 5]), seg(1, [5, 5], [5, 10])];
  const tc = buildPipeComponents(t, 0.01);
  assert.equal(tc.components.length, 1);
  const x = [seg(0, [0, 0], [10, 10]), seg(1, [0, 10], [10, 0])];
  const xc = buildPipeComponents(x, 0.01);
  assert.equal(xc.components.length, 2);
});

test('unique explicit tag propagates only through its connected component and converts scale exactly', () => {
  const segments = [seg(0, [0, 0], [100, 0]), seg(1, [100, 0], [100, 50]), seg(2, [300, 0], [350, 0])];
  const built = buildPipeComponents(segments, 0.1);
  assert.equal(built.components.length, 2);
  const associations = associatePipeTagsToSegments([
    { system: 'CW', diameter_in: '1/2', dn: 15, position_pt: [10, 2] },
  ], segments, [1, 0, 0, 1, 0, 0], { maxDistancePt: 10, minMarginPt: 3 });
  assert.equal(associations.accepted.length, 1);
  const assignments = assignPipeDiameters(segments, built.components, built.adjacency, associations.accepted);
  assert.deepEqual(assignments.map(a => a.status), ['EXPLICIT_TAG_SEED', 'COMPONENT_SINGLE_CLASS_PROPAGATION', 'WITHHELD_NO_DIAMETER_EVIDENCE']);
  const agg = aggregatePipeAssignments(segments, assignments, 100);
  assert.equal(agg.coverage.assigned_fraction, 0.75);
  assert.equal(agg.rows.length, 1);
  assert.equal(agg.rows[0].diameter_key, 'DN15');
  assert.equal(agg.rows[0].length_m_candidate, 5.292);
});

test('different diameter seeds inside one component propagate by network distance and ties fail closed', () => {
  const segments = [seg(0, [0, 0], [10, 0]), seg(1, [10, 0], [20, 0]), seg(2, [20, 0], [30, 0])];
  const built = buildPipeComponents(segments, 0.01);
  const tags = [
    { system: 'CW', diameter_in: '1/2', dn: 15, component_id: 0, nearest_segment: 0 },
    { system: 'CW', diameter_in: '3/4', dn: 20, component_id: 0, nearest_segment: 2 },
  ];
  const assignments = assignPipeDiameters(segments, built.components, built.adjacency, tags, 0.01);
  assert.equal(assignments[0].classes[0].diameter_key, 'DN15');
  assert.equal(assignments[2].classes[0].diameter_key, 'DN20');
  assert.equal(assignments[1].status, 'WITHHELD_DIAMETER_TIE');
});
