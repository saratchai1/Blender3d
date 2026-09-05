"""Validate and concatenate native Cycles chunks; never synthesize animation frames."""
from __future__ import annotations
import argparse,collections,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
items=[]
for path in a.input.glob('**/chunk-report.json'):
 d=json.loads(path.read_text());assert d['status']=='PASS';items.append((d['shot'],d['part'],d,path.parent/'chunk.mp4'))
items.sort(key=lambda x:(x[0],x[1]))
assert len(items)==18, f'Expected 18 chunks, found {len(items)}'
byshot=collections.defaultdict(list);sources=set()
for shot,part,d,clip in items:
 assert clip.is_file();sources.add(d['source_scene_sha256']);byshot[shot].extend(d['frames'])
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,r_frame_rate','-of','json',str(clip)]))['streams'][0]
 assert int(probe['nb_read_frames'])==32 and probe['r_frame_rate']=='24/1' and probe['width']==1280 and probe['height']==720,probe
assert len(sources)==1 and len(byshot)==6
for shot,frames in byshot.items():
 assert [f['frame'] for f in frames]==list(range(1,97)),shot
 assert len({tuple(f['camera_position']) for f in frames})==96,shot
 assert len({f['sha256'] for f in frames})==96,shot
lst=a.output/'clips.txt';lst.write_text(''.join("file '"+str(v[3].resolve())+"'\n" for v in items))
master=a.output/'SOLSTICE-14-Cycles-Master.mp4'
subprocess.run(['ffmpeg','-y','-v','warning','-f','concat','-safe','0','-i',str(lst),'-c','copy','-movflags','+faststart',str(master)],check=True)
film=a.output/'SOLSTICE-14-Architectural-Film.mp4'
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
filters=['fade=t=in:st=0:d=0.4','fade=t=out:st=23.5:d=0.5']
if Path(font).exists():
 filters.extend([f"drawtext=fontfile={font}:text='SOLSTICE 14':fontcolor=white@0.88:fontsize=18:x=30:y=24:shadowcolor=black@0.5:shadowx=1:shadowy=1",f"drawtext=fontfile={font}:text='ARCHITECTURE IN MOTION':fontcolor=white@0.76:fontsize=9:x=31:y=48:shadowcolor=black@0.5:shadowx=1:shadowy=1"])
 for i,title in enumerate(['01  /  SOUTHERN APPROACH','02  /  ARRIVAL','03  /  BRONZE AND GLASS','04  /  SKY GARDEN','05  /  ROOFTOP','06  /  EVENING']):
  filters.append(f"drawtext=fontfile={font}:text='{title}':fontcolor=white@0.90:fontsize=11:x=31:y=h-35:shadowcolor=black@0.6:shadowx=1:shadowy=1:enable='between(t,{i*4+.3},{i*4+2.6})'")
subprocess.run(['ffmpeg','-y','-v','warning','-i',str(master),'-vf',','.join(filters),'-c:v','libx264','-crf','17','-preset','slow','-pix_fmt','yuv420p','-movflags','+faststart','-an',str(film)],check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=codec_name,width,height,nb_read_frames,r_frame_rate:format=duration,size','-of','json',str(film)]))
assert int(probe['streams'][0]['nb_read_frames'])==576 and abs(float(probe['format']['duration'])-24)<.05,probe
subprocess.run(['ffmpeg','-v','error','-i',str(film),'-f','null','-'],check=True)
report={'status':'PASS','video':film.name,'sha256':hashlib.sha256(film.read_bytes()).hexdigest(),'master_sha256':hashlib.sha256(master.read_bytes()).hexdigest(),'engine':'Blender 4.5.3 Cycles CPU','source_scene_sha256':next(iter(sources)),'actual_rendered_frames':576,'actual_shots':6,'probe':probe,'chunk_reports':[{k:v for k,v in d.items() if k!='frames'} for _,_,d,_ in items],'frame_audit':dict(byshot),'postproduction':'Native Cycles renders only. Hard cuts, labels, start/end fades. No zoompan, no frame interpolation, no upscaling.','scope':'Concept visualization, not construction BIM. Landscape and lighting are presentation-only; original IFC/BOQ unchanged.','audio':'None'}
(a.output/'render-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ['frame_audit','chunk_reports']},indent=2))
