#!/usr/bin/env python3
"""Automatic quantity extraction from vector construction PDFs.

The extractor deliberately has no access to benchmark BOQ/reference pages or
reference quantities. A profile may describe drawing-page roles, scales and
legend template regions because those are inputs visible on the drawing set.
All evidence emitted by this module must point at allowed drawing pages.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import cv2
import fitz
import numpy as np

SCHEMA='blender3d.auto_boq.v1'

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def m_per_point(scale_ratio: float) -> float:
    return 0.0254*float(scale_ratio)/72.0

@dataclass(frozen=True)
class GuardedPdf:
    doc: fitz.Document
    max_source_page: int
    def page(self,page_no:int)->fitz.Page:
        if page_no<1 or page_no>self.max_source_page:
            raise ValueError(f'source-page guard: page {page_no} is outside drawing pages 1..{self.max_source_page}')
        return self.doc[page_no-1]

def iter_line_segments(page:fitz.Page)->Iterable[tuple[float,float,float,float,float]]:
    for drawing in page.get_drawings():
        for item in drawing.get('items',[]):
            if item[0]=='l':
                p1,p2=item[1],item[2]
                yield p1.x,p1.y,p2.x,p2.y,math.hypot(p2.x-p1.x,p2.y-p1.y)
            elif item[0]=='re':
                r=item[1]
                for x1,y1,x2,y2 in ((r.x0,r.y0,r.x1,r.y0),(r.x1,r.y0,r.x1,r.y1),(r.x1,r.y1,r.x0,r.y1),(r.x0,r.y1,r.x0,r.y0)):
                    yield x1,y1,x2,y2,math.hypot(x2-x1,y2-y1)

def detect_hatched_roof(page:fitz.Page,scale_ratio:float,slope_deg:float=0)->dict[str,Any]:
    W,H=page.rect.width,page.rect.height; hs=[]
    for x1,y1,x2,y2,length in iter_line_segments(page):
        if abs(y2-y1)>0.35: continue
        xa,xb=sorted((x1,x2)); y=(y1+y2)/2
        if not (0.15*W<xa<0.65*W and 0.25*H<y<0.82*H): continue
        if not (0.20*W<length<0.45*W): continue
        hs.append((xa,y,xb,y,length))
    if len(hs)<15: return {'status':'WITHHELD','reason':'no dense roof hatch band'}
    buckets={}
    for s in hs: buckets.setdefault((round(s[0]/3),round(s[2]/3)),[]).append(s)
    dense=max(buckets.values(),key=len)
    if len(dense)<12: return {'status':'WITHHELD','reason':'roof hatch span is not dominant'}
    x0=float(np.median([s[0] for s in dense])); x1=float(np.median([s[2] for s in dense])); ys=[s[1] for s in dense]; y0,y1=min(ys),max(ys)
    nearby=[s for s in hs if abs(s[0]-x0)<=8 and abs(s[2]-x1)<=8]
    if nearby:
        x0=min([x0]+[s[0] for s in nearby]); x1=max([x1]+[s[2] for s in nearby]); y0=min([y0]+[s[1] for s in nearby]); y1=max([y1]+[s[1] for s in nearby])
    wp,hp=x1-x0,y1-y0
    if wp<=0 or hp<=0: return {'status':'WITHHELD','reason':'invalid roof bounds'}
    mpp=m_per_point(scale_ratio); projected=wp*hp*mpp*mpp; factor=1/math.cos(math.radians(slope_deg)) if slope_deg else 1
    return {'status':'DETECTED','bounds_pt':[round(x0,3),round(y0,3),round(x1,3),round(y1,3)],'width_m':wp*mpp,'height_m':hp*mpp,'projected_area_m2':projected,'surface_area_m2':projected*factor,'perimeter_m':2*(wp+hp)*mpp,'slope_deg':slope_deg,'hatch_lines':len(dense),'confidence':min(0.98,0.80+min(len(dense),40)/250)}

def detect_swing_doors(page:fitz.Page,scale_ratio:float,mapped_widths_m:dict[str,str])->list[dict[str,Any]]:
    W,H=page.rect.width,page.rect.height; mpp=m_per_point(scale_ratio); mapped=[(float(k),v) for k,v in mapped_widths_m.items()]; out=[]
    for d in page.get_drawings():
        if len([it for it in d.get('items',[]) if it[0]=='c'])!=1: continue
        r=d['rect']; w,h=r.width,r.height
        if not (0.20*W<r.x0<0.62*W and 0.30*H<r.y0<0.78*H): continue
        if not (14<=w<=27 and 14<=h<=27 and abs(w-h)<=2.2): continue
        observed=((w+h)/2)*mpp
        if not mapped: continue
        nominal,type_id=min(mapped,key=lambda kv:abs(kv[0]-observed))
        if abs(observed-nominal)>0.04: continue
        out.append({'type':type_id,'nominal_width_m':nominal,'observed_width_m':observed,'bbox_pt':[r.x0,r.y0,r.x1,r.y1],'confidence':max(0.65,0.98-abs(observed-nominal)/0.08)})
    return out

def render_gray(page:fitz.Page,scale:float)->np.ndarray:
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),colorspace=fitz.csGRAY,alpha=False,annots=False)
    return np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width)

def tight_dark_crop(a:np.ndarray,threshold:int=200,pad:int=2)->np.ndarray:
    ys,xs=np.where(a<threshold)
    if not len(xs): raise ValueError('template region contains no dark pixels')
    return a[max(0,int(ys.min())-pad):min(a.shape[0],int(ys.max())+pad+1),max(0,int(xs.min())-pad):min(a.shape[1],int(xs.max())+pad+1)]

def template_sweep(template_page:fitz.Page,rect:list[float],target_pages:list[tuple[int,fitz.Page]],roi:list[float],threshold:float,render_scale:float=1.2,rotate_90:bool=False)->list[dict[str,Any]]:
    ref=render_gray(template_page,render_scale); x0,y0,x1,y1=[int(round(v*render_scale)) for v in rect]; tpl=tight_dark_crop(ref[y0:y1,x0:x1]); templates=[(0,tpl)]
    if rotate_90: templates.append((90,cv2.rotate(tpl,cv2.ROTATE_90_CLOCKWISE)))
    hits=[]
    for page_no,page in target_pages:
        arr=render_gray(page,render_scale); rx0,ry0,rx1,ry1=[int(round(v*render_scale)) for v in roi]; crop=255-arr[ry0:ry1,rx0:rx1]; raw=[]
        for rotation,t in templates:
            ti=255-t
            if crop.shape[0]<ti.shape[0] or crop.shape[1]<ti.shape[1]: continue
            res=cv2.matchTemplate(crop,ti,cv2.TM_CCOEFF_NORMED); ys,xs=np.where(res>=threshold)
            for yy,xx in zip(ys,xs): raw.append((float(res[yy,xx]),xx+rx0+ti.shape[1]/2,yy+ry0+ti.shape[0]/2,rotation,max(ti.shape)))
        merged=[]
        for score,x,y,rotation,size in sorted(raw,reverse=True):
            if all((x-h['x_px'])**2+(y-h['y_px'])**2>=(max(size,h['size_px'])*0.72)**2 for h in merged): merged.append({'score':score,'x_px':x,'y_px':y,'rotation':rotation,'size_px':size})
        for h in merged: hits.append({'page':page_no,'x_norm':h['x_px']/arr.shape[1],'y_norm':h['y_px']/arr.shape[0],'match_score':h['score'],'rotation':h['rotation']})
    return hits

def row(i,d,c,u,q,conf,method,pages,evidence):
    return {'id':i,'description':d,'category':c,'unit':u,'quantity':round(float(q),3),'confidence':round(float(conf),3),'method':method,'source_pages':sorted(set(pages)),'review':'REVIEW_REQUIRED','evidence':evidence}

def extract(pdf_path:Path,profile_path:Path)->dict[str,Any]:
    profile=json.loads(profile_path.read_text(encoding='utf-8')); max_page=int(profile['source_page_max']); doc=fitz.open(pdf_path)
    if doc.page_count<=max_page: raise ValueError('benchmark/source fence is inconsistent with document page count')
    g=GuardedPdf(doc,max_page); rows=[]; diagnostics=[]
    cfg=profile.get('roof')
    if cfg:
        p=int(cfg['page']); rr=detect_hatched_roof(g.page(p),float(cfg['scale_ratio']),float(cfg.get('slope_deg',0))); diagnostics.append({'detector':'roof_hatch_band','page':p,**rr})
        if rr.get('status')=='DETECTED':
            rows.append(row('ARCH-ROOF-METAL','หลังคาเหล็กรีดลอน','Architecture','m²',rr['surface_area_m2'],rr['confidence'],'vector:hatch-band + slope',[p],{'bounds_pt':rr['bounds_pt'],'projected_area_m2':round(rr['projected_area_m2'],3),'slope_deg':rr['slope_deg'],'hatch_lines':rr['hatch_lines']}))
            rows.append(row('ARCH-FASCIA','เชิงชาย / ขอบหลังคา','Architecture','m',rr['perimeter_m'],min(rr['confidence'],0.96),'vector:roof-outline perimeter',[p],{'bounds_pt':rr['bounds_pt']}))
    cfg=profile.get('doors')
    if cfg:
        all_d=[]
        for p in cfg['pages']:
            ds=detect_swing_doors(g.page(int(p)),float(cfg['scale_ratio']),cfg['type_by_nominal_width_m'])
            for d in ds: d['page']=int(p)
            all_d+=ds
        by={}
        for d in all_d: by.setdefault(d['type'],[]).append(d)
        for type_id,ds in sorted(by.items()):
            rows.append(row(f'ARCH-DOOR-{type_id}',f'ประตู {type_id}','Architecture','ea',len(ds),float(np.median([d['confidence'] for d in ds])),'vector:door-swing radius',[d['page'] for d in ds],{'detections':[{'page':d['page'],'nominal_width_m':d['nominal_width_m'],'observed_width_m':round(d['observed_width_m'],3),'bbox_pt':[round(v,2) for v in d['bbox_pt']]} for d in ds]}))
        diagnostics.append({'detector':'door_swing','pages':cfg['pages'],'detections':len(all_d),'by_type':{k:len(v) for k,v in by.items()}})
    cfg=profile.get('electrical')
    if cfg:
        lp=int(cfg['legend_page']); legend=g.page(lp); targets=[(int(p),g.page(int(p))) for p in cfg['lighting_pages']]
        for det in cfg.get('symbol_templates',[]):
            hits=template_sweep(legend,det['template_rect_pt'],targets,det['target_roi_pt'],float(det['threshold']),float(cfg.get('render_scale',1.2)),bool(det.get('rotate_90',False))); med=float(np.median([h['match_score'] for h in hits])) if hits else 0
            if hits: rows.append(row(det['id'],det['description'],'Electrical','ea',len(hits),med,'raster:legend-template sweep',[lp]+[h['page'] for h in hits],{'legend_page':lp,'detections':hits,'threshold':det['threshold'],'template':det.get('template_name',det['id'])}))
            diagnostics.append({'detector':f"electrical_template:{det['id']}",'legend_page':lp,'target_pages':cfg['lighting_pages'],'detections':len(hits),'median_score':med,'status':'DETECTED' if hits else 'WITHHELD'})
    for r in rows:
        if any(p>max_page for p in r['source_pages']): raise AssertionError(f"reference leakage: {r['id']} cites a source page after {max_page}")
    coverage={
      'supported_detectors':['roof/fascia vector hatch band','0.70/0.80 m swing-door counts','electrical legend-template sweeps'],
      'withheld_detectors':[
        {'name':'windows','status':'WITHHELD','reason':'type/count mapping not yet reliable on this CAD-font set'},
        {'name':'sanitary fixtures','status':'WITHHELD','reason':'fixture labels/symbols need a validated plan-view fingerprint library'},
        {'name':'switch/socket','status':'WITHHELD','reason':'generic dot/line symbols produce unsafe false positives without corroboration'},
        {'name':'floor finishes','status':'WITHHELD','reason':'finish-code text extraction is unreliable on legacy Thai CAD fonts'},
        {'name':'wall area','status':'WITHHELD','reason':'requires opening deductions and wall-height evidence before publication'},
        {'name':'sanitary piping','status':'WITHHELD','reason':'line-role classification and fitting/branch rules are not validated yet'},
        {'name':'structure','status':'WITHHELD','reason':'structural member classification is not validated yet'}],
      'note':'Unsupported items are withheld rather than fabricated.'}
    result={'schema':SCHEMA,'document':{'name':pdf_path.name,'sha256':sha256_file(pdf_path),'pages':doc.page_count},'source_policy':{'drawing_pages':[1,max_page],'reference_pages_forbidden':list(range(max_page+1,doc.page_count+1)),'reference_used_for_generation':False},'profile':{'id':profile.get('id','unknown'),'version':profile.get('version',1)},'status':'AUTOMATIC_PRELIMINARY_REVIEW_REQUIRED','rows':rows,'coverage':coverage,'diagnostics':diagnostics}; doc.close(); return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pdf',type=Path,required=True); ap.add_argument('--profile',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args(); result=extract(a.pdf,a.profile); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); print('AUTO_BOQ_OK',json.dumps({'rows':len(result['rows']),'ids':[r['id'] for r in result['rows']]}))
if __name__=='__main__': main()
