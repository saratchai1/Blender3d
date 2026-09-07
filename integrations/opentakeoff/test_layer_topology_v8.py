#!/usr/bin/env python3
from __future__ import annotations

import layer_topology_v8 as topo


def seg(a,b,layer,width=0.5,color=(1,0,0),dash='solid'):
    return {
        'a':a,'b':b,
        'length_pt':((b[0]-a[0])**2+(b[1]-a[1])**2)**0.5,
        'layer':layer,'width_pt':width,'color':color,'dash':dash,
    }


def main() -> None:
    segments = [
        seg((0,0),(100,0),'CW',0.3),
        seg((100,0),(200,0),'CW',0.8,color=(0,0,1)),  # style change: still same network
        seg((50,-50),(50,50),'CW',0.3),               # X interior/interior: separate
        seg((150,0),(150,80),'CW',0.2,dash='[2 2]'),  # T endpoint on trunk: connected
        seg((200,0),(260,0),'WASTE',0.8),              # touching but different layer: separate
    ]
    components, by_segment = topo.layer_components(segments, snap_pt=0.2)
    assert len(components) == 3, components
    assert by_segment[0] == by_segment[1] == by_segment[3], by_segment
    assert by_segment[2] != by_segment[0], by_segment
    assert by_segment[4] != by_segment[1], by_segment
    trunk = components[by_segment[0]]
    assert trunk['segment_count'] == 3, trunk
    assert trunk['style']['style_variant_count'] == 3, trunk
    assert trunk['style']['topology_basis'] == 'SEMANTIC_LAYER_GEOMETRY_ONLY'
    print('LAYER_TOPOLOGY_V8_TEST_PASS', {'components':len(components),'trunk_segments':trunk['segment_count']})


if __name__ == '__main__':
    main()
