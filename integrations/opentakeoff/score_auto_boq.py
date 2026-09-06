#!/usr/bin/env python3
"""Score generated Automatic BOQ against a separate reference file.

Generation must finish before this scorer reads any ground-truth quantity or
reference-page range. Keep this module separate from auto_boq.py.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

SCHEMA='blender3d.auto_boq.benchmark.v1'

def score(generated: dict, reference: dict) -> dict:
    if generated.get('source_policy',{}).get('reference_used_for_generation') is not False:
        raise ValueError('generated file does not prove reference isolation')
    rows={r['id']:r for r in generated.get('rows',[])}
    comparisons=[]; detected=0; within5=0; abs_pct=[]
    for ref in reference.get('items',[]):
        row=rows.get(ref['id'])
        if row is None:
            comparisons.append({**ref,'detected':False,'status':'WITHHELD'})
            continue
        if row['unit'] != ref['unit']:
            raise ValueError(f"unit mismatch for {ref['id']}: {row['unit']} vs {ref['unit']}")
        detected += 1
        q=float(row['quantity']); truth=float(ref['quantity']); err=q-truth
        pct=(err/truth*100) if truth else None
        if pct is not None:
            abs_pct.append(abs(pct)); within5 += int(abs(pct)<=5)
        comparisons.append({
            'id':ref['id'],'unit':ref['unit'],'detected':True,
            'generated_quantity':q,'reference_quantity':truth,
            'error':round(err,3),'error_pct':round(pct,3) if pct is not None else None,
            'within_5pct':abs(pct)<=5 if pct is not None else None,
            'confidence':row.get('confidence'),'source_pages':row.get('source_pages',[]),'method':row.get('method')
        })
    total=len(reference.get('items',[]))
    return {
        'schema':SCHEMA,
        'scope':'AUDIT_SUBSET_ONLY_NOT_FULL_BOQ',
        'reference_page_range':reference.get('reference_page_range'),
        'reference_rows':total,
        'detected_reference_rows':detected,
        'coverage_pct':round(detected/total*100,2) if total else 0,
        'detected_rows_within_5pct':within5,
        'detected_rows_accuracy_pct':round(within5/detected*100,2) if detected else 0,
        'mean_absolute_error_pct':round(sum(abs_pct)/len(abs_pct),3) if abs_pct else None,
        'comparisons':comparisons,
        'warning':'Accuracy is only for this small audit subset. It is not full-project BOQ accuracy.'
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--generated',type=Path,required=True); ap.add_argument('--reference',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    result=score(json.loads(a.generated.read_text(encoding='utf-8')),json.loads(a.reference.read_text(encoding='utf-8')))
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('AUTO_BOQ_SCORE_OK',json.dumps({k:result[k] for k in ('reference_rows','detected_reference_rows','coverage_pct','detected_rows_accuracy_pct','mean_absolute_error_pct')}))
if __name__=='__main__': main()
