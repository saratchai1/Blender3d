"""Create a transparent concept quantity schedule from the JSON design spec.
Teaching estimate only; not a tender/construction BOQ.
"""
from __future__ import annotations
import argparse,csv,json,math
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument("--spec",type=Path,required=True);p.add_argument("--output",type=Path,default=Path("dist/boq.csv"));a=p.parse_args()
    s=json.loads(a.spec.read_text(encoding="utf-8"));n=int(s["storeys"]);h=float(s["floor_height_m"]);w=float(s["footprint"]["width_m"]);d=float(s["footprint"]["depth_m"]);t=float(s["slab_thickness_m"]);sp=float(s["facade"]["fin_spacing_m"])
    pvc=int(s["pv"]["rows"])*int(s["pv"]["columns"]);slab=w*d*n;facade=2*(w+d)*max(h-.55,0)*n;fins=(2*math.ceil(w/sp)+2*math.ceil(d/sp))*n
    rows=[("Floor slabs","m2",slab,"Footprint area x storeys"),("Floor slab concrete","m3",slab*t,"Concept slab thickness"),("Curtain glazing","m2",facade,"Gross facade approximation before openings"),("Facade fins","ea",fins,"Nominal fin spacing"),("PV modules","ea",pvc,"Rows x columns from spec"),("PV DC nameplate","kWp",pvc*float(s["pv"]["panel_watt"])/1000,"Assumed module rating")]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("w",newline="",encoding="utf-8-sig") as f:
        wr=csv.writer(f);wr.writerow(["Work Category","Unit","Quantity","Basis","Status"])
        for name,unit,q,basis in rows:wr.writerow([name,unit,round(q,3),basis,"Concept / teaching only"])
    print(a.output)
if __name__=="__main__":main()
