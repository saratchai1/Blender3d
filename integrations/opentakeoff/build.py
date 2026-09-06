#!/usr/bin/env python3
"""Build the pinned OpenTakeoff UI plus the Family4 Automatic BOQ benchmark."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PIN=json.loads((ROOT/'integrations/opentakeoff/upstream.json').read_text())
DEMO_SHA256='f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'
DEMO_SIZE=13_058_241

def run(*cmd:str,cwd:Path)->None: subprocess.run(cmd,cwd=cwd,check=True)
def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def main()->None:
    p=argparse.ArgumentParser(); p.add_argument('--upstream',type=Path,required=True); p.add_argument('--output',type=Path,default=ROOT/'.generated/pages/takeoff'); p.add_argument('--demo-pdf',type=Path,default=ROOT/'.generated/samples/family4.pdf'); p.add_argument('--skip-install',action='store_true'); a=p.parse_args()
    upstream=a.upstream.resolve(); web=upstream/'web'; out=a.output.resolve(); demo=a.demo_pdf.resolve()
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip()!=PIN['commit']: raise SystemExit('Pinned OpenTakeoff commit mismatch')
    if not (web/'package-lock.json').is_file(): raise SystemExit('A lockfile is required; do not resolve floating dependencies.')
    if upstream==ROOT or web==ROOT/'web' or out in (ROOT,upstream,web) or out==ROOT/'web': raise SystemExit('Refusing unsafe source/output path.')
    if not demo.is_file() or demo.stat().st_size!=DEMO_SIZE or sha256(demo)!=DEMO_SHA256: raise SystemExit('Verified Family4 benchmark PDF is missing or changed.')
    src=ROOT/'web/opentakeoff-poc'
    store=web/'src/lib/store.js'; text=store.read_text(); original='const DB_NAME = "opentakeoff";'; replacement='const DB_NAME = typeof location === "undefined" ? "opentakeoff" : (new URLSearchParams(location.search).get("workspace") === "demo" ? "blender3d-opentakeoff-poc-v2-demo" : "blender3d-opentakeoff-poc-v1-user");'
    if original in text: text=text.replace(original,replacement,1)
    elif replacement not in text: raise SystemExit('Store patch anchor drifted; inspect upstream before rebuilding.')
    store.write_text(text); shutil.copy2(src/'poc-main.jsx',web/'src/main.jsx'); shutil.copy2(src/'poc-report.mjs',web/'src/poc-report.mjs')
    for path in (web/'src').rglob('*'):
        if path.suffix not in {'.js','.jsx','.ts','.tsx'}: continue
        old=path.read_text(); new=re.sub(r'(["\'`])/demo/',r'\1./demo/',old)
        if new!=old: path.write_text(new)
    index=web/'index.html'; text=index.read_text(); text=re.sub(r'<title>.*?</title>','<title>OpenTakeoff — Blender3d POC engine</title>',text,flags=re.S); csp='<meta http-equiv="Content-Security-Policy" content="connect-src \'self\' blob:; object-src \'none\'; base-uri \'self\'; form-action \'none\'">'
    if csp not in text: text=text.replace('<head>','<head>\n'+csp,1)
    index.write_text(text)
    if not a.skip_install: run('npm','ci','--no-audit','--no-fund',cwd=web)
    run('npm','run','typecheck',cwd=web); run('npm','test',cwd=web); run('node','--test',str(src/'report.test.mjs'),cwd=web)
    env={**os.environ,'VITE_ONE_CLICK':'0','VITE_COMMAND_BOX':'0','VITE_CLOUD_SYNC':'0','VITE_GOOGLE_CLIENT_ID':'','VITE_DRIVE_ROOT_FOLDER_ID':''}; subprocess.run(['npm','run','build','--','--base=./'],cwd=web,env=env,check=True)
    out.mkdir(parents=True,exist_ok=True)
    for name in ('index.html','poc.css','poc.js','poc-report.mjs'): shutil.copy2(src/name,out/name)
    demo_dir=out/'demo'; demo_dir.mkdir(parents=True,exist_ok=True); shutil.copy2(demo,demo_dir/'family4.pdf')

    # AUTOMATIC BOQ: generation completes before the reference scorer reads any
    # official BOQ quantity. v8.19 publishes pipe rows only after the tank-side
    # CW valve branch is independently corroborated across SN-04 and SN-05, then
    # the horizontal, vertical, roof, non-additive and final release gates pass.
    auto=ROOT/'integrations/opentakeoff/auto_boq_v8_19.py'; profile=ROOT/'integrations/opentakeoff/profiles/family4.json'; roof_evidence=ROOT/'integrations/opentakeoff/profiles/family4_roof_level_evidence.json'; equipment_evidence=ROOT/'integrations/opentakeoff/profiles/family4_equipment_vertical_evidence.json'; reference=ROOT/'integrations/opentakeoff/benchmark_reference.json'; generated=out/'auto-boq.json'; benchmark=out/'auto-boq-benchmark.json'
    for test in ('test_equipment_valve_corroboration_v8.py','test_vertical_valve_leader_reconcile_v8.py','test_pipe_publish_v8.py','test_pipe_release_reconcile_v8.py','test_roof_terminal_reconcile_v8.py','test_vertical_direct_branch_v8.py','test_vertical_level_bounds_v8.py','test_vertical_schematic_v8.py','test_cross_view_system_consensus_v8.py','test_strict_pipe_tags_v8.py','test_auto_boq_v8.py'):
        run(sys.executable,str(ROOT/'integrations/opentakeoff'/test),cwd=ROOT/'integrations/opentakeoff')
    run(sys.executable,str(auto),'--pdf',str(demo),'--profile',str(profile),'--roof-evidence',str(roof_evidence),'--equipment-evidence',str(equipment_evidence),'--output',str(generated),cwd=ROOT)
    run(sys.executable,str(ROOT/'integrations/opentakeoff/test_auto_boq.py'),'--pdf',str(demo),'--profile',str(profile),'--reference',str(reference),cwd=ROOT)
    run(sys.executable,str(ROOT/'integrations/opentakeoff/score_auto_boq.py'),'--generated',str(generated),'--reference',str(reference),'--output',str(benchmark),cwd=ROOT)

    engine=out/'engine'
    if engine.exists(): shutil.rmtree(engine)
    shutil.copytree(web/'dist',engine)
    for name in ('LICENSE','NOTICE','THIRD-PARTY-NOTICES.md'):
        if (upstream/name).exists(): shutil.copy2(upstream/name,engine/name)
    (engine/'POC-NOTICE.txt').write_text('Modified downstream by Blender3d: local OpenTakeoff review canvas plus geometry-first Family4 Automatic BOQ benchmark. Automatic generation is fenced to drawing pages 1-71; official BOQ pages are scorer-only. Apache-2.0 upstream measurement engine.\n')
    (engine/'.well-known/mcp.json').unlink(missing_ok=True)
    score=json.loads(benchmark.read_text())
    generated_data=json.loads(generated.read_text())
    fd_diag=next((d for d in generated_data.get('diagnostics',[]) if d.get('detector')=='positioned_tag_diagnostic:SAN-FLOOR-DRAIN-2'),None)
    pipe_diag=next((d for d in generated_data.get('diagnostics',[]) if d.get('detector')=='sanitary_pipe_network_v8_19'),None)
    published_pipe_rows=[r for r in generated_data.get('rows',[]) if str(r.get('id','')).startswith('SAN-PIPE-')]
    corroboration=(pipe_diag or {}).get('equipment_valve_corroboration') or {}
    pipe_summary={
        'status':pipe_diag.get('status') if pipe_diag else None,
        'publication_status':((pipe_diag or {}).get('reconciliation') or {}).get('full_pipe_boq_publication_status'),
        'published_pipe_rows':len(published_pipe_rows),
        'published_pipe_total_m':round(sum(float(r.get('quantity') or 0.0) for r in published_pipe_rows),3),
        'pipe_ids':[r.get('id') for r in published_pipe_rows],
        'release_blockers':(((pipe_diag or {}).get('pipe_release_candidate') or {}).get('release_blocker_count')),
        'excluded_non_quantity_runs':(((pipe_diag or {}).get('pipe_release_candidate') or {}).get('excluded_non_quantity_run_count')),
        'valve_leader_promoted':(((pipe_diag or {}).get('vertical_level_bounded_reconciliation') or {}).get('valve_leader_promoted_count')),
        'equipment_valve_corroboration_status':corroboration.get('status'),
        'equipment_valve_source_pages':corroboration.get('source_pages'),
        'nearby_main_role':corroboration.get('nearby_main_role'),
    }
    (out/'build-info.json').write_text(json.dumps({**PIN,'built_at':datetime.now(timezone.utc).isoformat(),'source_commit':os.environ.get('GITHUB_SHA','local'),'upstream_tests':'passed','adapter_tests':'passed','automatic_boq':{'status':'passed','published_rows':len(generated_data.get('rows',[])),'audit_subset_detected_rows':score['detected_reference_rows'],'audit_subset_coverage_pct':score['coverage_pct'],'audit_subset_detected_accuracy_pct':score['detected_rows_accuracy_pct'],'audit_subset_mae_pct':score['mean_absolute_error_pct'],'known_withheld':{'SAN-FLOOR-DRAIN-2':fd_diag.get('detections') if fd_diag else None},'pipe_network':pipe_summary},'demo_pdf':{'name':'family4.pdf','bytes':DEMO_SIZE,'sha256':DEMO_SHA256,'source_page':'https://townsquare.dpt.go.th/arch/plan/399'},'limitations':['automatic coverage remains a validated subset of the overall building BOQ','floor drain is withheld: four explicit drawing tags found versus five BOQ reference; schedule row is not counted as a physical drain','Family4 sanitary pipe takeoff publishes eight validated system/diameter rows totaling 92.500 m after horizontal, vertical, roof, cross-sheet tank-valve and non-additive gates pass','new user PDFs do not yet run the Python detector in GitHub Pages','no cloud persistence','preliminary quantities require review']},indent=2))
    print('POC_BUILD_OK',out)
if __name__=='__main__': main()
