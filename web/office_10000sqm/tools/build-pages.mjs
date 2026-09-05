/** Build a GitHub Pages artifact from public website files only. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const dest = path.resolve(process.argv[2] || path.join(root, '.generated/pages'));
if (dest === root || root.startsWith(dest + path.sep)) throw new Error('Unsafe output directory');
fs.mkdirSync(dest, { recursive: true });
const office = path.join(dest, 'office_10000sqm');
fs.mkdirSync(path.join(office, 'assets'), { recursive: true });
const source = path.join(root, 'web/office_10000sqm');
const files = ['index.html','style.css','model.mjs','renderer.mjs','export.mjs','app.mjs','presentation.html','presentation.css','presentation.mjs','assets/solstice-14.glb','assets/solstice-14-office.ifc'];
const filmPath = path.join(source, 'film/SOLSTICE-14-Architectural-Film.mp4');
if (fs.existsSync(filmPath)) {
  const audit = JSON.parse(fs.readFileSync(path.join(source, 'film/render-report.json'), 'utf8'));
  const digest = createHash('sha256').update(fs.readFileSync(filmPath)).digest('hex');
  if (audit.status !== 'PASS' || audit.sha256 !== digest || audit.actual_rendered_frames !== 576) {
    throw new Error('Offline film has no matching passed 576-frame render audit');
  }
  files.push('film/index.html', 'film/SOLSTICE-14-Architectural-Film.mp4', 'film/render-report.json');
}
const hashes = {};
for (const file of files) {
  const data = fs.readFileSync(path.join(source, file));
  if (!data.length) throw new Error(`Missing/empty website asset: ${file}`);
  fs.mkdirSync(path.dirname(path.join(office, file)), { recursive: true });
  fs.copyFileSync(path.join(source, file), path.join(office, file));
  hashes[file] = createHash('sha256').update(data).digest('hex');
}
fs.writeFileSync(path.join(dest, 'index.html'), '<!doctype html><html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SOLSTICE 14</title><meta http-equiv="refresh" content="0;url=./office_10000sqm/presentation.html"></head><body><p><a href="./office_10000sqm/presentation.html">เปิด SOLSTICE 14 — Interactive 3D Presentation</a></p></body></html>');
fs.writeFileSync(path.join(dest, '.nojekyll'), '');
fs.writeFileSync(path.join(dest, 'build.json'), JSON.stringify({ sourceCommit: process.env.GITHUB_SHA || 'local-review', assetSha256: hashes }, null, 2));
console.log(JSON.stringify({ output: dest, websiteFiles: files.length, assets: hashes }, null, 2));
