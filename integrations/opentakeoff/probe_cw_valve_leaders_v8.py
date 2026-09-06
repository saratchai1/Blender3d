#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz

import auto_boq as base
import auto_boq_v8 as v8
import layer_topology_v8 as topology
import leader_association_v8 as leader
import pipe_reconcile_v8 as diameter

VALVE_NAMES = ('BALL VALVE', 'FLOAT VALVE')
DIA_RX = re.compile(r'(?:Ø|∅)\s*(\d+(?:\s*/\s*\d+|\.\d+)?)')


def _line_records(page: fitz.Page) -> list[dict[str, Any]]:
    groups: dict[tuple[int,int], list[Any]] = {}
    for word in page.get_text('words') or []:
        key = (int(word[5]) if len(word)>5 else 0, int(word[6]) if len(word)>6 else 0)
        groups.setdefault(key, []).append(word)
    rows=[]
    for words in groups.values():
        words.sort(key=lambda w:(float(w[0]),float(w[1])))
        text=' '.join(str(w[4]) for w in words)
        upper=text.upper()
        name=next((n for n in VALVE_NAMES if n in upper),None)
        if not name:
            continue
        m=DIA_RX.search(upper)
        normalized=None
        if m:
            try:
                normalized=diameter.normalize_diameter(f'{m.group(1)}"')
            except ValueError:
                normalized=None
        bbox=[
            min(float(w[0]) for w in words), min(float(w[1]) for w in words),
            max(float(w[2]) for w in words), max(float(w[3]) for w in words),
        ]
        rows.append({'name':name,'text':text,'bbox_pt':bbox,'diameter':normalized})
    return rows


def probe(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    profile=json.loads(profile_path.read_text(encoding='utf-8'))
    cfg=profile.get('sanitary_pipe_network',{})
    doc=fitz.open(pdf_path)
    guarded=base.GuardedPdf(doc,int(profile['source_page_max']))
    page=guarded.page(57)
    segments=v8.line_segments(
        page,None,
        float(cfg.get('min_segment_pt',3.0)),
        float(cfg.get('max_stroke_width_pt',3.0)),
    )
    components,component_by_segment=topology.layer_components(
        segments,float(cfg.get('endpoint_snap_pt',1.5)),
    )
    del components
    rows=[]
    for callout in _line_records(page):
        resolved=leader.find_leader_target(
            tag_bbox_pt=list(map(float,callout['bbox_pt'])),
            segments=segments,
            component_by_segment=component_by_segment,
            expected_layer='CW',
        )
        target=None
        if resolved.get('target_segment_index') is not None:
            idx=int(resolved['target_segment_index'])
            seg=segments[idx]
            target={
                'segment_index':idx,
                'component_id':component_by_segment.get(idx),
                'layer':seg.get('layer'),
                'a':[round(float(seg['a'][0]),3),round(float(seg['a'][1]),3)],
                'b':[round(float(seg['b'][0]),3),round(float(seg['b'][1]),3)],
                'length_pt':round(float(seg.get('length_pt',0.0)),3),
            }
        rows.append({**callout,'leader':resolved,'target_segment':target})
    doc.close()
    return {
        'status':'DIAGNOSTIC_ONLY_NO_QUANTITY_CHANGE',
        'source_page':57,
        'source_page_max':int(profile['source_page_max']),
        'expected_layer':'CW',
        'callouts':rows,
        'callout_count':len(rows),
        'associated_count':sum(1 for r in rows if (r['leader'] or {}).get('status')=='ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER'),
        'publication_policy':'EVIDENCE_ONLY_NO_PIPE_LENGTH_ADDITION',
    }


def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--pdf',type=Path,required=True); ap.add_argument('--profile',type=Path,required=True); ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); result=probe(args.pdf,args.profile); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CW_VALVE_LEADER_PROBE_OK',json.dumps({'callouts':result['callout_count'],'associated':result['associated_count'],'output':str(args.output)},ensure_ascii=False))


if __name__=='__main__':main()
