#!/usr/bin/env python3
from __future__ import annotations

import leader_association_v8 as leader


def seg(a, b, *, layer='', index=0):
    return {
        'a': a,
        'b': b,
        'length_pt': ((b[0]-a[0])**2 + (b[1]-a[1])**2) ** 0.5,
        'layer': layer,
        'index': index,
    }


def main() -> None:
    # Text box at x=0..20. A two-segment L leader reaches the lower CW pipe while
    # another CW pipe is actually closer to the text center. Leader evidence wins.
    segments = [
        seg((24, 10), (40, 10), index=0),
        seg((40, 10), (40, 30), index=1),
        seg((36, 30), (80, 30), layer='CW', index=2),
        seg((30, 0), (80, 0), layer='CW', index=3),
    ]
    components = {2: 10, 3: 11}
    result = leader.find_leader_target(
        tag_bbox_pt=[0, 0, 22, 20],
        segments=segments,
        component_by_segment=components,
        expected_layer='CW',
        source_snap_pt=3.0,
        target_snap_pt=4.5,
    )
    assert result['status'] == 'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER', result
    assert result['target_segment_index'] == 2, result
    assert result['component_id'] == 10, result
    assert result['leader_segment_indexes'] == [0, 1], result

    # If one leader terminates equally close to two distinct pipe components, do
    # not guess which physical run the annotation means.
    segments = [
        seg((24, 10), (45, 10), index=0),
        seg((45, 5), (80, 5), layer='CW', index=1),
        seg((45, 15), (80, 15), layer='CW', index=2),
    ]
    result = leader.find_leader_target(
        tag_bbox_pt=[0, 0, 22, 20],
        segments=segments,
        component_by_segment={1: 20, 2: 21},
        expected_layer='CW',
        source_snap_pt=3.0,
        target_snap_pt=5.1,
        ambiguity_margin_pt=1.0,
    )
    assert result['status'] == 'WITHHELD_AMBIGUOUS_LEADER_TARGETS', result

    # An unrelated long annotation line is excluded from the leader graph.
    segments = [
        seg((22, 10), (200, 10), index=0),
        seg((195, 10), (230, 10), layer='CW', index=1),
    ]
    result = leader.find_leader_target(
        tag_bbox_pt=[0, 0, 20, 20],
        segments=segments,
        component_by_segment={1: 30},
        expected_layer='CW',
        max_leader_segment_pt=80.0,
    )
    assert result['status'] == 'WITHHELD_NO_LEADER_AT_TAG', result

    print('LEADER_ASSOCIATION_V8_TEST_PASS', {
        'leader': 'explicit path wins',
        'ambiguity': 'withheld',
        'long_annotation': 'excluded',
    })


if __name__ == '__main__':
    main()
