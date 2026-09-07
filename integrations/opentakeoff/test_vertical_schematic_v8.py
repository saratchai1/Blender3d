#!/usr/bin/env python3
from __future__ import annotations

import vertical_schematic_v8 as vertical


def main() -> None:
    markers = [
        {'elevation_m': 3.75, 'y_rotated_pt': 100.0},
        {'elevation_m': 0.60, 'y_rotated_pt': 415.0},
        {'elevation_m': 0.00, 'y_rotated_pt': 475.0},
    ]
    axis = vertical.fit_elevation_axis(markers)
    assert axis['status'] == 'CALIBRATED_FROM_EXPLICIT_LEVEL_MARKERS', axis
    assert axis['r2'] > 0.999, axis
    assert abs(vertical.elevation_at(axis, 100.0) - 3.75) < 1e-6, axis
    assert abs(vertical.elevation_at(axis, 475.0) - 0.0) < 1e-6, axis

    original_lines = vertical.v8.line_segments
    original_rotated = vertical._rotated_point
    try:
        # Coordinates are already in visible/rotated space for this synthetic case.
        vertical._rotated_point = lambda page, point: (float(point[0]), float(point[1]))
        vertical.v8.line_segments = lambda *args, **kwargs: [
            {'a': (10.0, 100.0), 'b': (10.0, 180.0), 'length_pt': 80.0, 'layer': 'V'},
            {'a': (10.0, 190.0), 'b': (10.0, 300.0), 'length_pt': 110.0, 'layer': 'V'},
            {'a': (10.0, 312.0), 'b': (10.0, 415.0), 'length_pt': 103.0, 'layer': 'V'},
            # Separate class/column must not merge with V.
            {'a': (30.0, 100.0), 'b': (30.0, 415.0), 'length_pt': 315.0, 'layer': 'SOIL'},
            # Horizontal branch must not contribute to vertical span.
            {'a': (10.0, 200.0), 'b': (40.0, 200.0), 'length_pt': 30.0, 'layer': 'V'},
        ]
        analysis = {'diameter_assignments': [
            {'segment_index': 0, 'status': 'EXPLICIT_TAG_SEED', 'classes': [{'system':'V','diameter_key':'DN50','dn':50}]},
            {'segment_index': 1, 'status': 'NETWORK_NEAREST_TAG_PROPAGATION', 'classes': [{'system':'V','diameter_key':'DN50','dn':50}]},
            {'segment_index': 2, 'status': 'NETWORK_NEAREST_TAG_PROPAGATION', 'classes': [{'system':'V','diameter_key':'DN50','dn':50}]},
            {'segment_index': 3, 'status': 'EXPLICIT_TAG_SEED', 'classes': [{'system':'S','diameter_key':'DN100','dn':100}]},
            {'segment_index': 4, 'status': 'EXPLICIT_TAG_SEED', 'classes': [{'system':'V','diameter_key':'DN50','dn':50}]},
        ]}
        runs = vertical.reconstruct_vertical_runs(
            None, analysis,
            min_segment_pt=3.0,
            max_stroke_width_pt=3.0,
            axis=axis,
            max_dash_gap_pt=25.0,
        )
        vrun = next(r for r in runs if r['system']=='V')
        srun = next(r for r in runs if r['system']=='S')
        assert vrun['segment_count'] == 3, runs
        assert vrun['segment_indexes'] == [0,1,2], runs
        assert abs(vrun['vertical_span_m'] - 3.15) < 1e-6, vrun
        assert abs(srun['vertical_span_m'] - 3.15) < 1e-6, srun
        print('VERTICAL_SCHEMATIC_V8_TEST_PASS', {'V_span_m':vrun['vertical_span_m'],'S_span_m':srun['vertical_span_m']})
    finally:
        vertical.v8.line_segments = original_lines
        vertical._rotated_point = original_rotated


if __name__ == '__main__':
    main()
