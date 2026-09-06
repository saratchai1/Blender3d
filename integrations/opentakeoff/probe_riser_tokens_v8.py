#!/usr/bin/env python3
"""Diagnostic-only English token inventory for cross-view riser reconciliation.

Reads source drawing pages only. The goal is to discover stable printed identifiers
(e.g. stack/riser codes) shared by SN-04 schematic and SN-05/SN-06 plans. It never
reads BOQ/reference pages and never changes quantity output.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import fitz

import auto_boq as base

TOKEN_RX = re.compile(r"^[A-Z][A-Z0-9._+/-]{0,11}$")
STOP = {
    'SCALE','PLAN','DETAIL','SECTION','ROOM','TOILET','GROUND','FLOOR','ROOF','UP','DOWN','DN',
    'DIA','PVC','PIPE','TYP','TYP.','NO','NO.','REF','NOTE','NOTES','PASS','BYPASS','VALVE','BALL',
}


def clean_token(text: str) -> str:
    return str(text or '').strip().upper().replace('“','"').replace('”','"')


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--pdf',type=Path,required=True)
    ap.add_argument('--profile',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    profile=json.loads(args.profile.read_text(encoding='utf-8'))
    specs=profile.get('sanitary_pipe_network',{}).get('page_specs',[])
    doc=fitz.open(args.pdf)
    guarded=base.GuardedPdf(doc,int(profile['source_page_max']))
    pages=[]
    shared_index: dict[str,list[dict[str,Any]]] = defaultdict(list)
    for spec in specs:
        page_no=int(spec['page']); page=guarded.page(page_no)
        W,H=float(page.rect.width),float(page.rect.height)
        tokens=[]
        for word in page.get_text('words') or []:
            x0,y0,x1,y1,text=word[:5]
            token=clean_token(text)
            if not token or token in STOP or not TOKEN_RX.fullmatch(token):
                continue
            # Keep drawing body; suppress right/bottom title-block noise.
            cx=(float(x0)+float(x1))/2; cy=(float(y0)+float(y1))/2
            if cx > W*0.88 or cy > H*0.94:
                continue
            row={
                'text':token,
                'bbox_pt':[round(float(x0),2),round(float(y0),2),round(float(x1),2),round(float(y1),2)],
                'center_norm':[round(cx/W,5),round(cy/H,5)],
            }
            tokens.append(row)
            shared_index[token].append({'sheet':spec.get('sheet'),'page':page_no,**row})
        counts=Counter(row['text'] for row in tokens)
        pages.append({
            'page':page_no,'sheet':spec.get('sheet'),'view_role':spec.get('view_role'),
            'token_count':len(tokens),'unique_tokens':sorted(counts),
            'token_counts':dict(sorted(counts.items())),
            'tokens':tokens,
        })
    doc.close()
    shared=[]
    for token,occ in shared_index.items():
        sheets=sorted({str(row['sheet']) for row in occ})
        if len(sheets)>=2:
            shared.append({'token':token,'sheets':sheets,'occurrences':occ})
    shared.sort(key=lambda row:(-len(row['sheets']),row['token']))
    result={
        'status':'DIAGNOSTIC_ONLY_NO_QUANTITY_CHANGE',
        'source_pages':[int(s['page']) for s in specs],
        'shared_tokens':shared,
        'pages':pages,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('AUTO_BOQ_RISER_TOKEN_PROBE_OK',json.dumps({
        'shared_token_count':len(shared),
        'shared_tokens':[row['token'] for row in shared[:40]],
        'page_unique_counts':{p['sheet']:len(p['unique_tokens']) for p in pages},
    },ensure_ascii=False))


if __name__=='__main__':
    main()
