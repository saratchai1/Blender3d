"""Join eight actual four-frame renders into the missing garden chunk."""
from __future__ import annotations
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--slices',type=Path,required=True);p.add_argument('--chunks',type=Path,required=True);a=p.parse_args()
items=[]
for path in a.slices.glob('**/slice-report.json'):
 d=json.loads(path.read_text());assert d['status']=='PASS';items.append((d['slice'],d,path.parent/'slice.mp4'))
items.sort(key=lambda x:x[0])
assert [i for i,_,_ in items]==list(range(8)),f'Expected eight unique recovery slices: {[i for i,_,_ in items]}'
frames=[];sources=set()
for i,d,clip in items:
 assert d['shot']=='04_garden' and d['part']==2 and len(d['frames'])==4
 assert [f['frame'] for f in d['frames']]==list(range(65+i*4,69+i*4))
 sources.add(d['source_scene_sha256']);frames.extend(d['frames'])
 assert clip.is_file()
 stream=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,r_frame_rate','-of','json',str(clip)]))['streams'][0]
 assert int(stream['nb_read_frames'])==4 and stream['r_frame_rate']=='24/1' and stream['width']==1280 and stream['height']==720,stream
assert len(sources)==1 and [f['frame'] for f in frames]==list(range(65,97))
assert len({tuple(f['camera_position']) for f in frames})==32
assert len({f['sha256'] for f in frames})==32
out=a.chunks/'film-chunk-04_garden-2'
if out.exists():raise RuntimeError('Refusing to overwrite an existing camera chunk')
out.mkdir(parents=True)
listing=out/'slices.txt';listing.write_text(''.join("file '"+str(clip.resolve())+"'\n" for _,_,clip in items))
subprocess.run(['ffmpeg','-y','-v','warning','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(out/'chunk.mp4')],check=True)
report={k:v for k,v in items[0][1].items() if k not in ['frames','slice','render_seconds']}
report.update(status='PASS',frames=frames,render_seconds=sum(d['render_seconds'] for _,d,_ in items),recovery='Eight native four-frame Cycles renders; all original settings retained; no frame synthesis')
(out/'chunk-report.json').write_text(json.dumps(report,indent=2))
print('RECOVERED_32_NATIVE_FRAMES '+str(out))
