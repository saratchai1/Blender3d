#!/usr/bin/env python3
"""Build a pinned OpenTakeoff derivative; never modify the main Blender pipelines."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = json.loads((ROOT / 'integrations/opentakeoff/upstream.json').read_text())
DEMO_SHA256 = 'f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'
DEMO_SIZE = 13_058_241

def run(*cmd: str, cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--upstream', type=Path, required=True, help='A disposable checkout of the exact upstream commit.')
    parser.add_argument('--output', type=Path, default=ROOT/'.generated/pages/takeoff')
    parser.add_argument('--demo-pdf', type=Path, default=ROOT/'.generated/samples/family4.pdf')
    parser.add_argument('--skip-install', action='store_true')
    args=parser.parse_args()
    upstream=args.upstream.resolve(); web=upstream/'web'; out=args.output.resolve(); demo_pdf=args.demo_pdf.resolve()
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip()
    if sha != PIN['commit']:
        raise SystemExit(f'Upstream mismatch: expected {PIN["commit"]}, got {sha}')
    if not (web/'package-lock.json').is_file():
        raise SystemExit('A lockfile is required; do not resolve floating dependencies.')
    if upstream == ROOT or web == ROOT/'web':
        raise SystemExit('Refusing to patch the project repository as upstream.')
    if out in (ROOT, upstream, web) or out == ROOT/'web':
        raise SystemExit('Refusing to use a source directory as the build output.')
    if not demo_pdf.is_file() or demo_pdf.stat().st_size != DEMO_SIZE or sha256(demo_pdf) != DEMO_SHA256:
        raise SystemExit('Verified Family 4 benchmark PDF is missing or does not match the pinned bytes. Run integrations/opentakeoff/fetch_sample.py first.')
    src=ROOT/'web/opentakeoff-poc'
    # Namespace browser workspaces. Bump ONLY the demo DB to v2 so existing user
    # work stays intact while browsers stop reopening the old synthetic fixture.
    store=web/'src/lib/store.js'
    text=store.read_text()
    original='const DB_NAME = "opentakeoff";'
    replacement='const DB_NAME = typeof location === "undefined" ? "opentakeoff" : (new URLSearchParams(location.search).get("workspace") === "demo" ? "blender3d-opentakeoff-poc-v2-demo" : "blender3d-opentakeoff-poc-v1-user");'
    if original in text: text=text.replace(original,replacement,1)
    elif replacement not in text: raise SystemExit('Store patch anchor drifted; inspect upstream before rebuilding.')
    store.write_text(text)
    # The full upstream canvas is used; only its mounting shell is replaced.
    shutil.copy2(src/'poc-main.jsx',web/'src/main.jsx')
    shutil.copy2(src/'poc-report.mjs',web/'src/poc-report.mjs')
    # Keep runtime demo fetches under /takeoff/engine on project GitHub Pages.
    for path in (web/'src').rglob('*'):
        if path.suffix not in {'.js','.jsx','.ts','.tsx'}: continue
        old=path.read_text();new=re.sub(r'(["\'`])/demo/',r'\1./demo/',old)
        if new != old: path.write_text(new)
    index=web/'index.html'; text=index.read_text()
    text=re.sub(r'<title>.*?</title>','<title>OpenTakeoff — Blender3d POC engine</title>',text,flags=re.S)
    csp='<meta http-equiv="Content-Security-Policy" content="connect-src \'self\' blob:; object-src \'none\'; base-uri \'self\'; form-action \'none\'">'
    if csp not in text: text=text.replace('<head>','<head>\n'+csp,1)
    index.write_text(text)
    if not args.skip_install: run('npm','ci','--no-audit','--no-fund',cwd=web)
    run('npm','run','typecheck',cwd=web)
    run('npm','test',cwd=web)
    run('node','--test',str(src/'report.test.mjs'),cwd=web)
    env={**os.environ,'VITE_ONE_CLICK':'0','VITE_COMMAND_BOX':'0','VITE_CLOUD_SYNC':'0','VITE_GOOGLE_CLIENT_ID':'','VITE_DRIVE_ROOT_FOLDER_ID':''}
    subprocess.run(['npm','run','build','--','--base=./'],cwd=web,env=env,check=True)
    out.mkdir(parents=True,exist_ok=True)
    for name in ('index.html','poc.css','poc.js','poc-report.mjs'): shutil.copy2(src/name,out/name)
    demo_dir=out/'demo';demo_dir.mkdir(parents=True,exist_ok=True);shutil.copy2(demo_pdf,demo_dir/'family4.pdf')
    engine=out/'engine'
    if engine.exists(): shutil.rmtree(engine)
    shutil.copytree(web/'dist',engine)
    for name in ('LICENSE','NOTICE','THIRD-PARTY-NOTICES.md'):
        if (upstream/name).exists(): shutil.copy2(upstream/name,engine/name)
    (engine/'POC-NOTICE.txt').write_text('Modified downstream by Blender3d: local-only entry point; isolated real Thai benchmark/user storage; read-only metric BOQ adapter; same-origin verified public Family 4 sample. Measurement/totals engine from Kentucky-ai/opentakeoff, Apache-2.0.\n')
    (engine/'.well-known/mcp.json').unlink(missing_ok=True)
    (out/'build-info.json').write_text(json.dumps({**PIN,'built_at':datetime.now(timezone.utc).isoformat(),'source_commit':os.environ.get('GITHUB_SHA','local'),'upstream_tests':'passed','adapter_tests':'passed','demo_pdf':{'name':'family4.pdf','bytes':DEMO_SIZE,'sha256':DEMO_SHA256,'source_page':'https://townsquare.dpt.go.th/arch/plan/399'},'limitations':['generated BOQ requires takeoff measurements','no AI or MCP endpoint','no cloud persistence','preliminary quantities only']},indent=2))
    print(f'POC_BUILD_OK {out}',flush=True)

if __name__=='__main__': main()
