"""Build an offline Cycles film from the unchanged SOLSTICE semantic model.
Run with Blender 4.5: blender -b -t 4 --python build_film.py -- --scene office.scene.json --output film --proof
The source building is preserved; vegetation/context/materials are presentation-only.
No image-to-video, still-image pans, external textures, or runtime services are used.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, math, random, sys, time
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

P = argparse.ArgumentParser()
P.add_argument('--scene', type=Path, required=True)
P.add_argument('--output', type=Path, required=True)
P.add_argument('--proof', action='store_true')
A = P.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
A.output.mkdir(parents=True, exist_ok=True)
source = json.loads(A.scene.read_text())
assert len(source['floors']) == 14
assert sum(f['area'] for f in source['floors']) == 10000
bpy.ops.wm.read_factory_settings(use_empty=True)
s = bpy.context.scene
s.unit_settings.system = 'METRIC'
s.render.engine = 'CYCLES'
s.cycles.device = 'CPU'
s.cycles.samples = 32
s.cycles.use_denoising = True
s.cycles.denoiser = 'OPENIMAGEDENOISE'
s.cycles.use_adaptive_sampling = True
s.cycles.adaptive_threshold = 0.06
s.cycles.max_bounces = 7
s.cycles.diffuse_bounces = 2
s.cycles.glossy_bounces = 4
s.cycles.transmission_bounces = 6
s.cycles.transparent_max_bounces = 6
s.cycles.caustics_reflective = False
s.cycles.caustics_refractive = False
s.cycles.sample_clamp_indirect = 3.0
s.cycles.use_animated_seed = False
s.cycles.seed = 14
s.render.use_persistent_data = True
s.render.resolution_x = 1280
s.render.resolution_y = 720
s.render.resolution_percentage = 100
s.render.fps = 24
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGB'
s.render.image_settings.compression = 15
s.render.film_transparent = False
s.view_settings.view_transform = 'AgX'
s.view_settings.look = 'AgX - Medium High Contrast'
s.view_settings.exposure = 0.15
s.render.use_motion_blur = False
s['design_status'] = 'Concept architecture; not for construction'
s['source_scene_sha256'] = hashlib.sha256(A.scene.read_bytes()).hexdigest()
s['render_basis'] = 'Actual 3D Cycles frame sequence; source geometry with presentation-only landscape/material refinements'


def rgb(hexvalue):
    h=hexvalue.lstrip('#')
    c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(x/12.92 if x<=0.04045 else ((x+0.055)/1.055)**2.4 for x in c)+(1,)


def material(name, color, rough=.5, metal=0, trans=0, coat=0, noise=False):
    m=bpy.data.materials.new(name);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=rgb(color)
    bs.inputs['Roughness'].default_value=rough
    bs.inputs['Metallic'].default_value=metal
    bs.inputs['Transmission Weight'].default_value=trans
    bs.inputs['Coat Weight'].default_value=coat
    bs.inputs['Coat Roughness'].default_value=.16
    bs.inputs['IOR'].default_value=1.48
    if noise:
        nodes=m.node_tree.nodes;links=m.node_tree.links
        geo=nodes.new('ShaderNodeNewGeometry')
        n=nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=95
        n.inputs['Detail'].default_value=2
        b=nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.22;b.inputs['Distance'].default_value=.008
        links.new(geo.outputs['Position'],n.inputs['Vector']);links.new(n.outputs['Fac'],b.inputs['Height']);links.new(b.outputs['Normal'],bs.inputs['Normal'])
    return m

mats={
 'ivory':material('Warm mineral white','#DDDDD1',.58,noise=True),
 'stone':material('Honed limestone','#ACA799',.62,noise=True),
 'glass':material('Low-E visual glass','#9FBAB4',.08,trans=.65,coat=.3),
 'glassLight':material('Clear architectural glass','#C4D7D0',.065,trans=.78,coat=.25),
 'bronze':material('Satin anodised bronze','#98724B',.26,.78,coat=.22),
 'dark':material('Graphite metal','#2B3332',.32,.55),
 'wood':material('Oiled dark teak','#865D3D',.42,noise=True),
 'lawn':material('Groundcover','#42542F',.9,noise=True),
 'road':material('Asphalt','#323637',.86,noise=True),
 'solar':material('Photovoltaic cells','#182F3D',.19,.48,coat=.7),
 'interior':material('Interior neutral oak','#9F815E',.6),
 'leaf':material('Leaves','#42603A',.55),
 'leafLight':material('Leaves light','#6C8144',.55),
 'water':material('Reflecting water','#759D98',.035,trans=.5,coat=.4),
 'light':material('Warm linear light','#FFE8B9',.4)
}
bs=mats['light'].node_tree.nodes.get('Principled BSDF')
bs.inputs['Emission Color'].default_value=rgb('#FFD391');bs.inputs['Emission Strength'].default_value=3.5
bs=mats['water'].node_tree.nodes.get('Principled BSDF');bs.inputs['IOR'].default_value=1.333
n=mats['water'].node_tree.nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=5.5;n.inputs['Detail'].default_value=2
b=mats['water'].node_tree.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.25;b.inputs['Distance'].default_value=.006
geo=mats['water'].node_tree.nodes.new('ShaderNodeNewGeometry')
mats['water'].node_tree.links.new(geo.outputs['Position'],n.inputs['Vector']);mats['water'].node_tree.links.new(n.outputs['Fac'],b.inputs['Height']);mats['water'].node_tree.links.new(b.outputs['Normal'],bs.inputs['Normal'])

BOX_V=[(-.5,-.5,-.5),(.5,-.5,-.5),(.5,.5,-.5),(-.5,.5,-.5),(-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5)]
BOX_F=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

def primitive(shape):
    if shape=='box':return BOX_V,BOX_F
    vs=[];fs=[]
    if shape=='cylinder':
        seg=16
        for y in [-.5,.5]:
            for j in range(seg):
                a=j*2*math.pi/seg;vs.append((.5*math.cos(a),y,.5*math.sin(a)))
        for j in range(seg):fs.append((j,(j+1)%seg,(j+1)%seg+seg,j+seg))
        fs.extend([tuple(range(seg-1,-1,-1)),tuple(range(seg,seg*2))])
        # Local cylinder winding is corrected below by geometric normal orientation.
        fs=[tuple(reversed(f)) for f in fs]
    else:
        rows,cols=10,16
        for j in range(rows+1):
            a=math.pi*j/rows
            for i in range(cols):
                b=i*math.pi*2/cols;vs.append((math.sin(a)*math.cos(b),math.cos(a),math.sin(a)*math.sin(b)))
        for j in range(rows):
            for i in range(cols):
                a=j*cols+i;b=j*cols+(i+1)%cols;c=a+cols;d=b+cols
                fs.append((a,b,d,c))
    return vs,fs

GEOM={shape:primitive(shape) for shape in ['box','sphere','cylinder']}
groups=collections.defaultdict(lambda:[[],[]])
retained=[];replaced=[]
for ob in source['objects']:
    name=ob['name'];ln=name.lower();mat=ob['material']
    if any(k in ln for k in ['tree trunk','tree canopy','shrub','visitor','electric car','car wheel']):
        replaced.append(name);continue
    if name=='Paved plaza':mat='stone'
    g=groups[mat];base=len(g[0]);M=ob['matrix'];vs,faces=GEOM[ob['shape']]
    for x,y,z in vs:
        xx=M[0]*x+M[4]*y+M[8]*z+M[12]
        yy=M[1]*x+M[5]*y+M[9]*z+M[13]
        zz=M[2]*x+M[6]*y+M[10]*z+M[14]
        g[0].append((xx,-zz,yy))
    g[1].extend(tuple(base+i for i in f) for f in faces);retained.append(name)


def mesh(name,vs,fs,mat):
    me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);me.materials.append(mat);return o

for key,(vs,fs) in groups.items():
    o=mesh('Source / '+key,vs,fs,mats[key]);o['source_instances']=sum(1 for a in source['objects'] if a['material']==key)
    if key in ['ivory','bronze','dark','wood','stone']:
        mod=o.modifiers.new('Fine edge highlights','BEVEL');mod.width=.016 if key!='stone' else .024;mod.segments=2
        mod.affect='EDGES';mod.limit_method='ANGLE'
        mod=o.modifiers.new('Architectural corner normals','WEIGHTED_NORMAL');mod.keep_sharp=True


def box(name,loc,size,mat,bevel=0):
    vs=[tuple(loc[k]+p[k]*size[k] for k in range(3)) for p in BOX_V]
    ob=mesh(name,vs,BOX_F,mat)
    if bevel:
        m=ob.modifiers.new('Edge radius','BEVEL');m.width=bevel;m.segments=3
        ob.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return ob

box('Context / continuous ground',(0,0,-.24),(1100,1100,.1),material('Context ground','#838677',.92,noise=True))
box('Context / road extension',(0,-34,-.15),(1000,10,.06),mats['road'])
box('Context / far sidewalk',(0,-41,-.13),(1000,4,.12),mats['stone'])
# Set-back context; none intrudes into the project site or any camera rail.
ctx=material('Distant urban masonry','#A2ADA9',.68)
ctxglass=material('Distant windows','#657A7A',.26,.3)
rr=random.Random(901)
for i in range(18):
    x=-240+i*28;y=100+rr.random()*65;h=rr.uniform(18,65);w=rr.uniform(15,24);d=rr.uniform(15,30)
    box('Context skyline',(x,y,h/2),(w,d,h),ctx)
    for z in range(3,int(h)-1,4):box('Context glazed band',(x,y-d/2-.012,z),(w-.7,.06,1.7),ctxglass)

# Procedural botanical assets: actual curved leaf geometry, shared between trees.
leafmats=[]
for color in ['#30472B','#435F32','#526D39','#668044','#3B592D','#74864A']:
    m=material('Botanical leaf '+color,color,.56)
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Subsurface Weight'].default_value=.065
    leafmats.append(m)
bark=material('Bark','#554535',.88,noise=True)

def botanical(seed):
    r=random.Random(seed);bv=[];bf=[];lv=[];lf=[];lm=[]
    def branch(a,b,ra,rb):
        axis=(Vector(b)-Vector(a)).normalized();u=axis.cross(Vector((0,1,0)))
        if u.length<.01:u=axis.cross(Vector((1,0,0)))
        u.normalize();v=axis.cross(u);base=len(bv);N=7
        for pos,rad in [(a,ra),(b,rb)]:
            for j in range(N):bv.append(tuple(Vector(pos)+rad*(u*math.cos(j*2*math.pi/N)+v*math.sin(j*2*math.pi/N))))
        for j in range(N):bf.append((base+j,base+(j+1)%N,base+N+(j+1)%N,base+N+j))
    branch((0,0,0),(.14,-.1,4.4),.16,.052)
    tips=[]
    for j in range(24):
        a=j*2.399+r.uniform(-.2,.2);z=r.uniform(2.6,4.3);rad=r.uniform(1.25,2.35)
        start=(.09,0,z);end=(math.cos(a)*rad,math.sin(a)*rad,r.uniform(4.8,6.1))
        branch(start,end,.055,.013)
        for k in range(3):
            v=Vector(end)+Vector((r.uniform(-.75,.75),r.uniform(-.75,.75),r.uniform(-.1,.6)))
            branch(end,v,.016,.004);tips.append(v)
    for tip in tips:
        for j in range(45):
            a=r.random()*2*math.pi;z=r.uniform(-1,1);rad=r.random()**(1/3)*.64
            pos=tip+Vector((math.cos(a)*math.sqrt(1-z*z)*rad,math.sin(a)*math.sqrt(1-z*z)*rad,z*rad*.75))
            direction=Vector((r.uniform(-1,1),r.uniform(-1,1),r.uniform(.25,1)))
            rot=direction.to_track_quat('Z','Y');length=r.uniform(.10,.18);width=length*.43;base=len(lv)
            for p in [(-length,0,0),(-length*.35,-width,0),(length*.45,-width*.8,0),(length,0,0),(length*.45,width*.8,0),(-length*.35,width,0),(0,0,length*.16)]:
                lv.append(tuple(pos+rot@Vector(p)))
            color=r.randrange(len(leafmats))
            for i in range(6):lf.append((base+i,base+(i+1)%6,base+6));lm.append(color)
    bo=bpy.data.meshes.new('Botanical branches '+str(seed));bo.from_pydata(bv,[],bf);bo.materials.append(bark)
    le=bpy.data.meshes.new('Botanical crown '+str(seed));le.from_pydata(lv,[],lf)
    for m in leafmats:le.materials.append(m)
    for p,c in zip(le.polygons,lm):p.material_index=c;p.use_smooth=True
    for p in bo.polygons:p.use_smooth=True
    return bo,le

assets=[botanical(14+i) for i in range(3)]
placements=[]
for i,ob in enumerate(a for a in source['objects'] if a['name']=='Tree trunk'):
    m=ob['matrix'];height=m[5]/.9;root=(m[12],-m[14],m[13]-height*.45)
    scale=height/3.15*(1 if ob['floor']==0 else .34)
    placements.append((root,scale,i))
for i in range(18):placements.append(((45+(i%2)*8,-20+(i//2)*12,0),1.2+(i%3)*.13,i))
for i in range(12):placements.append(((-47-(i%2)*9,-18+(i//2)*17,0),1.1+(i%4)*.10,i+18))
for root,scale,i in placements:
    for part,me in enumerate(assets[i%3]):
        o=bpy.data.objects.new('Presentation tree / '+('branches' if part==0 else 'foliage'),me);s.collection.objects.link(o)
        o.location=root;o.scale=(scale,scale,scale);o.rotation_euler.z=(i*1.78)%(2*math.pi)
        o['presentation_only']=True
# Low planting remains inside the original planting beds.
for i,ob in enumerate(a for a in source['objects'] if a['name']=='Shrub'):
    m=ob['matrix'];o=bpy.data.objects.new('Presentation shrub',assets[i%3][1]);s.collection.objects.link(o)
    o.location=(m[12],-m[14],m[13]-.45);o.scale=(.16,.16,.13);o.rotation_euler.z=i*2.4

# Visual warm interiors, not additions to the concept BIM quantities.
interior_light=material('Interior warm luminosity','#DEC6A2',.68)
bs=interior_light.node_tree.nodes.get('Principled BSDF');bs.inputs['Emission Color'].default_value=rgb('#FFD6A0');bs.inputs['Emission Strength'].default_value=.12
for f in source['floors']:
    for x in [-12,-7,-2,3,8,13]:
        if f['terrace'] and abs(x)<9:continue
        box('Presentation interior lighting',(x,-f['depth']/2+2.0,f['y']+f['height']-.6),(3.5,2.6,.035),interior_light)

# Warm-lit entry sign. Its letters are real geometry, not a screen overlay.
text=bpy.data.curves.new('Arrival sign','FONT');text.body='S O L S T I C E   1 4';text.size=.28;text.extrude=.006;text.align_x='CENTER'
sign=bpy.data.objects.new('Arrival sign',text);s.collection.objects.link(sign);sign.location=(0,-18.425,4.04);sign.rotation_euler=(math.pi/2,0,0);text.materials.append(mats['bronze'])

world=bpy.data.worlds.new('Physical architectural sky');world.use_nodes=True;s.world=world
nodes=world.node_tree.nodes;nodes.clear();out=nodes.new('ShaderNodeOutputWorld');bg=nodes.new('ShaderNodeBackground');sky=nodes.new('ShaderNodeTexSky')
sky.sky_type='NISHITA';sky.sun_disc=False;sky.sun_elevation=math.radians(32);sky.sun_rotation=math.radians(225);sky.altitude=.1;sky.air_density=1.0;sky.dust_density=1.1;bg.inputs['Strength'].default_value=.24
world.node_tree.links.new(sky.outputs['Color'],bg.inputs['Color']);world.node_tree.links.new(bg.outputs['Background'],out.inputs['Surface'])
light=bpy.data.lights.new('Late afternoon sun','SUN');light.energy=3.0;light.angle=math.radians(2)
sun=bpy.data.objects.new('Late afternoon sun',light);s.collection.objects.link(sun);sun.rotation_euler=Vector((40,65,-80)).to_track_quat('-Z','Y').to_euler();light.color=(1,.87,.71)

FPS=24;FRAMES=96
SHOTS=[
 {'name':'01_hero','start':(76,-110,43),'end':(59,-105,39),'target0':(0,0,28),'target1':(0,0,27),'lens':42},
 {'name':'02_arrival','start':(-29,-45,5.5),'end':(-19,-36,4.7),'target0':(0,-10,5),'target1':(0,-12,4.7),'lens':31},
 {'name':'03_facade','start':(34,-35,24),'end':(29,-34,32),'target0':(9,-6,27),'target1':(8,-6,32),'lens':43},
 {'name':'04_garden','start':(13,-30,38.2),'end':(-1,-25,38.5),'target0':(0,-7.7,37.8),'target1':(-1,-7.7,37.9),'lens':34},
 {'name':'05_roof','start':(38,-40,78),'end':(25,-40,74),'target0':(1,0,52),'target1':(0,0,51),'lens':42},
 {'name':'06_dusk','start':(-72,-99,39),'end':(-89,-100,44),'target0':(0,0,27),'target1':(0,0,27),'lens':42,'dusk':True}
]


def setup_shot(shot):
    s.frame_start=1;s.frame_end=FRAMES
    camera_data=bpy.data.cameras.new('Film camera '+shot['name']);cam=bpy.data.objects.new(camera_data.name,camera_data);s.collection.objects.link(cam);s.camera=cam
    camera_data.lens=shot['lens'];camera_data.sensor_width=36;camera_data.clip_end=1500
    camera_data.dof.use_dof=True;camera_data.dof.aperture_fstop=8 if shot['name'] in ['01_hero','05_roof','06_dusk'] else 6.3
    for fr in range(1,FRAMES+1):
        u=(fr-1)/(FRAMES-1)
        # Every frame has a distinct 3D location and look target. No fixed-frame interpolation.
        cam.location=Vector(shot['start']).lerp(Vector(shot['end']),u)
        target=Vector(shot['target0']).lerp(Vector(shot['target1']),u)
        cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
        camera_data.dof.focus_distance=(target-cam.location).length
        cam.keyframe_insert('location',frame=fr);cam.keyframe_insert('rotation_euler',frame=fr);camera_data.keyframe_insert('dof.focus_distance',frame=fr)
    dusk=shot.get('dusk',False)
    sky.sun_elevation=math.radians(2 if dusk else 32);sky.sun_rotation=math.radians(225)
    bg.inputs['Strength'].default_value=.17 if dusk else .24
    light.energy=.18 if dusk else 3.0;light.color=(1,.57,.30) if dusk else (1,.87,.71)
    s.view_settings.exposure=.55 if dusk else .15
    interior_light.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=4.0 if dusk else .12
    mats['light'].node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=8 if dusk else 3.5
    s.frame_set(1)
    s.render.filepath='//frames/'+shot['name']+'/frame_'
    s['shot']=shot['name'];s['fps']=FPS;s['native_frames']=FRAMES
    s['camera_start']=list(shot['start']);s['camera_end']=list(shot['end'])
    return cam

report={'source_sha256':s['source_scene_sha256'],'building_storeys':14,'concept_area_m2':10000,'source_objects':len(source['objects']),'retained_source_instances':len(retained),'replaced_entourage_parts':len(replaced),'render_engine':'CYCLES','blender_version':bpy.app.version_string,'fps':FPS,'frames_per_shot':FRAMES,'width':1280,'height':720,'shots':SHOTS,'proofs':[],'presentation_only':'Refined materials, trees, background context, lighting and sign do not change IFC or BOQ.'}
for shot in SHOTS:
    cam=setup_shot(shot)
    s.render.resolution_percentage=100;s.cycles.samples=32
    path=A.output/(shot['name']+'.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(path.resolve()),compress=True)
    if A.proof:
        s.frame_set(48);s.render.resolution_percentage=75;s.cycles.samples=16
        s.render.filepath=str((A.output/(shot['name']+'.png')).resolve())
        start=time.monotonic();bpy.ops.render.render(write_still=True)
        report['proofs'].append({'shot':shot['name'],'seconds':time.monotonic()-start,'resolution':[960,540],'samples':16})
        (A.output/'lookdev-report.json').write_text(json.dumps(report,indent=2))
    bpy.data.objects.remove(cam,do_unlink=True)
(A.output/'lookdev-report.json').write_text(json.dumps(report,indent=2))
print('FILM_SCENE_READY '+json.dumps(report))
