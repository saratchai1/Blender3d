/** Solstice 14. One metre per unit; X east, Y up, Z south. No dependencies. */
export const SPEC = Object.freeze({
  name: 'SOLSTICE 14', version: '1.0.0', units: 'metres', storeys: 14,
  grossArea: 10000, typicalWidth: 34, typicalDepth: 20,
  latitude: 13.7563, longitude: 100.5018, timezone: 7,
  site: { width: 68, depth: 58, assumed: true },
  pv: { panels: 96, wattsPerPanel: 450, width: 1.13, length: 1.9 },
  disclaimer: 'Concept only. Areas include covered terraces; not statutory GFA, usable office area or a permit design. Energy performance is not simulated.'
});
export const FLOORS = Array.from({ length: 14 }, (_, i) => {
  const level = i + 1, width = level <= 2 ? 40 : level <= 12 ? 34 : 30;
  const depth = level <= 2 ? 25 : 20, height = level === 1 ? 5 : level === 2 ? 4.5 : 3.8;
  const y = level === 1 ? 0 : level === 2 ? 5 : 9.5 + (level - 3) * 3.8;
  const terrace = [5, 10].includes(level) ? 72 : 0;
  const use = level === 1 ? 'Lobby · café · arrival' : level === 2 ? 'Conference · co-working' : terrace ? 'Office · sky garden' : level >= 13 ? 'Executive · meeting suites' : 'Flexible office';
  return { level, width, depth, height, y, area: width * depth, terrace, enclosed: width * depth - terrace, use };
});
export const HEIGHT = FLOORS.at(-1).y + FLOORS.at(-1).height;
export const MATERIALS = {
  stone: { color: [0.79, 0.77, 0.71], kind: 0 },
  ivory: { color: [0.91, 0.9, 0.85], kind: 0 },
  glass: { color: [0.22, 0.43, 0.45], kind: 1 },
  glassLight: { color: [0.32, 0.51, 0.52], kind: 1 },
  bronze: { color: [0.67, 0.50, 0.30], kind: 2 },
  dark: { color: [0.16, 0.21, 0.22], kind: 2 },
  wood: { color: [0.55, 0.36, 0.21], kind: 0 },
  leaf: { color: [0.23, 0.39, 0.24], kind: 3 },
  leafLight: { color: [0.37, 0.49, 0.27], kind: 3 },
  lawn: { color: [0.48, 0.55, 0.38], kind: 0 },
  water: { color: [0.28, 0.47, 0.48], kind: 1 },
  road: { color: [0.43, 0.45, 0.43], kind: 0 },
  solar: { color: [0.09, 0.18, 0.26], kind: 2 },
  light: { color: [1.0, 0.79, 0.43], kind: 4 },
  interior: { color: [0.76, 0.62, 0.43], kind: 0 }
};
// Layer IDs: 0 site, 1 structure, 2 glazing, 3 solar fins, 4 landscape, 5 furniture, 6 core, 7 roof/PV.
export function matrix(position, size, ry = 0, rx = 0) {
  const c = Math.cos(ry), s = Math.sin(ry), a = Math.cos(rx), b = Math.sin(rx);
  return [c*size[0],0,-s*size[0],0,s*b*size[1],a*size[1],c*b*size[1],0,s*a*size[2],-b*size[2],c*a*size[2],0,...position,1];
}
export function makeScene({ finDepth = 0.95 } = {}) {
  if (!Number.isFinite(finDepth) || finDepth < 0.3 || finDepth > 1.8) throw new Error('Fin depth must be 0.3–1.8 m');
  const objects = [];
  let seed = 231;
  const random = () => ((seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296);
  function add(shape, name, p, s, material, floor = 0, layer = 1, ry = 0, rx = 0) {
    objects.push({ shape, name, matrix: matrix(p, s, ry, rx), material, floor, layer });
  }
  const box = (name,p,s,m,f=0,l=1,ry=0,rx=0) => add('box',name,p,s,m,f,l,ry,rx);
  const ball = (name,p,s,m,f=0,l=4) => add('sphere',name,p,s,m,f,l);
  const cyl = (name,p,s,m,f=0,l=4) => add('cylinder',name,p,s,m,f,l);
  function tree(x,y,z,scale=1,f=0) {
    const h = (2.6 + random() * 0.7) * scale;
    cyl('Tree trunk',[x,y+h*0.45,z],[0.18*scale,h*0.9,0.18*scale],'wood',f);
    ball('Tree canopy',[x,y+h,z],[1.65*scale,1.9*scale,1.65*scale],'leaf',f);
    ball('Tree canopy light',[x+0.6*scale,y+h+0.35*scale,z+0.25*scale],[1.2*scale,1.35*scale,1.3*scale],'leafLight',f);
  }
  function planter(x,y,z,w,d,f=0) {
    box('Stone planter',[x,y+0.32,z],[w,0.64,d],'stone',f,4);
    box('Planting bed',[x,y+0.67,z],[w-0.16,0.08,d-0.16],'lawn',f,4);
    for(let t=-w/2+0.6;t<w/2;t+=0.75) ball('Shrub',[x+t,y+0.98,z],[0.58,0.48,d*0.55],'leaf',f);
  }
  function desk(x,y,z,f,ry=0) {
    box('Desk top',[x,y+0.78,z],[1.6,0.09,0.75],'ivory',f,5,ry);
    box('Desk base',[x,y+0.39,z],[0.65,0.76,0.42],'dark',f,5,ry);
    box('Task chair',[x,y+0.49,z+0.72],[0.55,0.12,0.53],'interior',f,5,ry);
    box('Chair back',[x,y+0.8,z+0.95],[0.55,0.6,0.1],'interior',f,5,ry);
  }
  box('Site plinth',[0,-0.65,0],[68,1,58],'stone',0,0);
  box('Paved plaza',[0,-0.11,0],[66,0.12,56],'ivory',0,0);
  box('Street',[0,-0.16,34],[125,0.12,10],'road',0,0);
  for(let x=-60;x<61;x+=7)box('Road marking',[x,-0.086,34],[3,0.015,0.14],'ivory',0,0);
  for(let x=-28;x<=28;x+=4) box('Plaza joint',[x,-0.035,0],[0.025,0.01,56],'stone',0,0);
  for(let z=-24;z<=24;z+=4) box('Plaza joint',[0,-0.034,z],[66,0.01,0.025],'stone',0,0);
  box('Reflecting pool surround',[-25,0.04,5],[7,0.2,21],'stone',0,0);
  box('Reflecting pool',[-25,0.155,5],[6.5,0.03,20.5],'water',0,0);
  box('West garden',[-26,0.02,-19],[11,0.16,12],'lawn',0,4);
  box('East garden',[26,0.02,-5],[9,0.16,37],'lawn',0,4);
  box('North garden',[0,0.02,-23],[44,0.16,8],'lawn',0,4);
  [[-28,-20],[-22,-21],[-29,-13],[25,-20],[29,-12],[25,-3],[29,6],[25,13],[-16,-23],[-5,-24],[7,-23],[18,-23],[-28,20],[28,22]].forEach(([x,z],i)=>tree(x,0.1,z,1.1+(i%3)*0.2));
  for(const x of [-13,13]) { planter(x,0,22,9,2.5); box('Plaza bench',[x,0.5,19.5],[5,0.25,0.85],'wood',0,0); }
  for(let i=0;i<9;i++) {
    const x=-17+i*4.2,z=17.8+(i%3)*1.3;
    cyl('Visitor',[x,0.84,z],[0.29,1.16,0.29],i%2?'dark':'stone',0,0);
    ball('Visitor head',[x,1.58,z],[0.17,0.19,0.17],'wood',0,0);
  }
  for(const x of [-12,12,24]) {
    box('Electric car body',[x,0.65,27],[4.6,0.9,1.9],x<0?'dark':'stone',0,0);
    box('Electric car cabin',[x,1.23,27],[2.6,0.6,1.68],'glass',0,0);
    for(const a of [-1.4,1.4])for(const b of [-0.86,0.86])ball('Car wheel',[x+a,0.36,27+b],[0.36,0.36,0.18],'dark',0,0);
  }
  // Fourteen individually selectable slabs. Terraces remain within the stated rectangular floor plates.
  for(const f of FLOORS) {
    const {level:n,width:w,depth:d,height:h,y}=f, garden = f.terrace>0;
    box(`L${n} floor plate`,[0,y+0.16,0],[w,0.32,d],'ivory',n,1);
    box(`L${n} soffit edge south`,[0,y+0.10,d/2+0.08],[w+0.28,0.13,0.32],'stone',n,1);
    box(`L${n} soffit edge north`,[0,y+0.10,-d/2-0.08],[w+0.28,0.13,0.32],'stone',n,1);
    box(`L${n} west edge`,[-w/2-0.08,y+0.10,0],[0.32,0.13,d+0.28],'stone',n,1);
    box(`L${n} east edge`,[w/2+0.08,y+0.10,0],[0.32,0.13,d+0.28],'stone',n,1);
    // Concept core: two stairs and a lift bank; dimensions do not constitute a code check.
    box(`L${n} lift bank`,[0,y+h/2,-2.5],[5.2,h-0.32,4.8],'stone',n,6);
    for(const x of [-6,6]) {
      box(`L${n} stair enclosure`,[x,y+h/2,-4.8],[3.3,h-0.32,5],'ivory',n,6);
      for(let j=0;j<10;j++)box(`L${n} stair tread`,[x,y+0.35+j*0.16,-6.5+j*0.3],[2.2,0.16,0.32],'stone',n,5);
    }
    for(const x of [-w/2+1.1,w/2-1.1])for(const z of [-d/2+1.1,0,d/2-1.1])
      box(`L${n} perimeter column`,[x,y+h/2,z],[0.42,h-0.32,0.42],'stone',n,1);
    const step= n<=2 ? 2 : 1.7;
    for(const sign of [-1,1]) {
      const segments = garden && sign===1 ? [[-w/2,-9],[9,w/2]] : [[-w/2,w/2]];
      for(const [start,end] of segments) {
        const count=Math.ceil((end-start)/step),bay=(end-start)/count;
        for(let i=0;i<count;i++) {
          const x=start+bay*(i+0.5),z=sign*d/2;
          box(`L${n} curtain glazing`,[x,y+0.37+(h-0.62)/2,z],[bay-0.075,h-0.62,0.13],i%4===0?'glassLight':'glass',n,2);
          box(`L${n} curtain mullion`,[x-bay/2,y+h/2,z+sign*0.11],[0.065,h-0.32,0.12],'dark',n,2);
          if(n>2) {
            box(`L${n} insulated spandrel`,[x,y+h-0.57,z+sign*0.10],[bay-0.05,0.85,0.18],'dark',n,2);
            const angle=(0.13*Math.sin(i*0.52+n*0.43)+0.12)*sign;
            box(`L${n} bronze solar fin`,[x-bay/2,y+h/2,z+sign*(finDepth/2+0.18)],[0.105,h-0.45,finDepth],'bronze',n,3,angle);
          }
        }
      }
    }
    if(garden) {
      for(let x=-8;x<=8;x+=2) {
        box(`L${n} garden inner glazing`,[x,y+h/2,6],[1.94,h-0.5,0.13],'glass',n,2);
        box(`L${n} garden inner mullion`,[x-1,y+h/2,6],[0.065,h-0.32,0.18],'dark',n,2);
      }
      for(const x of [-9,9])box(`L${n} garden glazing return`,[x,y+h/2,8],[0.13,h-0.5,4],'glass',n,2);
    }
    for(let j=0;j<Math.floor(d/1.35);j++) {
      const bay=d/Math.floor(d/1.35),z=-d/2+bay*(j+0.5);
      for(const sign of [-1,1]) {
        box(`L${n} end glazing`,[sign*w/2,y+h/2,z],[0.13,h-0.5,bay-0.055],j%3?'glass':'glassLight',n,2);
        if(n>2)box(`L${n} east west fin`,[sign*(w/2+finDepth/2+0.16),y+h/2,z],[finDepth,h-0.48,0.105],'bronze',n,3,-sign*0.35);
      }
    }
    if(n>2) {
      for(const x of [-12.5,12.5])box(`L${n} meeting room partition`,[x,y+1.7,-3],[.10,2.8,7],'glassLight',n,5);
      for(const sign of [-1,1])box(`L${n} horizontal shade`,[0,y+h-0.1,sign*(d/2+0.34)],[w+1,0.14,0.88],'ivory',n,3);
      for(const x of [-10,-5,5,10])for(const z of [-0.2,4.6])if(!(garden && z>4 && Math.abs(x)<9))desk(x,y+0.33,z,n);
    } else {
      for(const x of [-13,13])box(`L${n} reception table`,[x,y+0.8,3.5],[3.8,0.85,1.3],'wood',n,5);
      for(const x of [-12,-6,6,12])desk(x,y+0.33,-6,n);
    }
    if(garden) {
      box(`L${n} garden deck`,[0,y+0.37,8],[18,0.09,4],'wood',n,4);
      planter(-4.8,y+0.4,9,7.2,1.6,n);planter(4.8,y+0.4,9,7.2,1.6,n);
      for(const x of [-6,0,6])tree(x,y+0.5,8,0.65,n);
      box(`L${n} terrace guardrail`,[0,y+1.0,10],[18,0.04,0.05],'bronze',n,4);
      for(const x of [-8,-4,0,4,8])box('Guardrail upright',[x,y+0.68,10],[0.05,0.65,0.05],'bronze',n,4);
    }
  }
  // Roof is attached to L14, not a fifteenth occupied storey.
  box('Roof slab',[0,HEIGHT+0.16,0],[30,0.32,20],'ivory',14,7);
  for(const sign of [-1,1])box('Roof parapet',[0,HEIGHT+0.72,sign*9.85],[30,1.1,0.22],'stone',14,7);
  for(const sign of [-1,1])box('Roof parapet',[sign*14.85,HEIGHT+0.72,0],[0.22,1.1,20],'stone',14,7);
  box('Screened roof plant',[-10,HEIGHT+1.7,0],[6.5,3,8],'dark',14,7);
  for(let z=-4.4;z<4.5;z+=0.48)box('Plant screen louvre',[-13.4,HEIGHT+1.7,z],[0.18,3.2,0.09],'bronze',14,7);
  for(let x=-13.4;x<-6.2;x+=0.48)box('Plant screen louvre',[x,HEIGHT+1.7,4.35],[0.10,3.2,0.20],'bronze',14,7);
  for(let row=0;row<8;row++)for(let col=0;col<12;col++) {
    const x=-3+col*1.28,z=-7.8+row*2.04;
    box('PV module 450 W target',[x,HEIGHT+1.12,z],[1.13,0.075,1.9],'solar',14,7,0,0.17);
    box('PV mounting rail',[x,HEIGHT+0.76,z],[0.055,0.65,1.7],'dark',14,7);
    for(const s of [-0.28,0,0.28])box('PV cell string',[x+s,HEIGHT+1.166,z],[0.009,0.008,1.86],'glassLight',14,7,0,0.17);
  }
  for(const x of [-18.5,18.5])box('Podium terrace roof',[x,9.5+0.16,0],[3,0.32,25],'ivory',3,1);
  for(const z of [-11.25,11.25])box('Podium terrace roof',[0,9.5+0.16,z],[34,0.32,2.5],'ivory',3,1);
  for(const x of [-16,16])box('Upper setback roof',[x,FLOORS[12].y+0.16,0],[2,0.32,20],'ivory',13,1);
  // Podium roof terraces occupy uncounted exterior roof surfaces, not additional storeys.
  for(const x of [-18.3,18.3]) {
    planter(x,9.6,0,1.7,20,3);
    for(const z of [-7,0,7])tree(x,10.25,z,0.66,3);
  }
  box('Entrance floating canopy',[0,4.0,15.3],[14,0.25,6.2],'ivory',1,1);
  for(const x of [-6.5,6.5])cyl('Entrance canopy column',[x,2,17.3],[0.18,4,0.18],'bronze',1,1);
  for(let x=-6;x<=6;x+=0.4)box('Canopy timber soffit',[x,3.84,15.3],[0.13,0.10,5.9],'wood',1,1);
  box('Entry light line',[0,3.85,18.3],[13,0.05,0.06],'light',1,1);
  return { spec: SPEC, floors: FLOORS, height: HEIGHT, materials: MATERIALS, objects };
}
/** Unit meshes used identically by the WebGL renderer and the GLB exporter. */
export function geometry(shape) {
  const positions=[], normals=[], indices=[];
  const vertex=(p,n)=>{positions.push(...p);normals.push(...n);return positions.length/3-1;};
  if(shape==='box') {
    const faces=[[[1,0,0],[0,1,0],[0,0,1]],[[-1,0,0],[0,1,0],[0,0,-1]],[[0,1,0],[0,0,1],[1,0,0]],[[0,-1,0],[0,0,-1],[1,0,0]],[[0,0,1],[1,0,0],[0,1,0]],[[0,0,-1],[-1,0,0],[0,1,0]]];
    for(const [n,u,v] of faces){const b=positions.length/3;for(const [a,c] of [[-1,-1],[1,-1],[1,1],[-1,1]])vertex(n.map((t,k)=>(t+a*u[k]+c*v[k])/2),n);indices.push(b,b+1,b+2,b,b+2,b+3);}
  } else if(shape==='sphere') {
    const rows=10,cols=14;
    for(let j=0;j<=rows;j++){const a=Math.PI*j/rows;for(let i=0;i<=cols;i++){const b=2*Math.PI*i/cols,n=[Math.sin(a)*Math.cos(b),Math.cos(a),Math.sin(a)*Math.sin(b)];vertex(n,n);}}
    for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){const a=j*(cols+1)+i,b=a+cols+1;indices.push(a,a+1,b,b,a+1,b+1);}
  } else if(shape==='cylinder') {
    const seg=12;
    for(let i=0;i<=seg;i++){const a=i*Math.PI*2/seg,n=[Math.cos(a),0,Math.sin(a)];vertex([n[0]*0.5,-0.5,n[2]*0.5],n);vertex([n[0]*0.5,0.5,n[2]*0.5],n);}
    for(let i=0;i<seg;i++){let a=i*2;indices.push(a,a+1,a+2,a+1,a+3,a+2);}
    for(const sign of [-1,1]){const mid=vertex([0,sign*0.5,0],[0,sign,0]);for(let i=0;i<=seg;i++){const a=i*Math.PI*2/seg;vertex([Math.cos(a)*0.5,sign*0.5,Math.sin(a)*0.5],[0,sign,0]);}for(let i=0;i<seg;i++){const a=mid+1+i;indices.push(mid,...(sign>0?[a+1,a]:[a,a+1]));}}
  } else throw new Error(`Unknown shape: ${shape}`);
  return {positions:new Float32Array(positions),normals:new Float32Array(normals),indices:new Uint16Array(indices)};
}
/** Approximate geometric sun position, not a daylight or annual energy simulation. */
export function sunPosition(hour, day=264) {
  const rad=Math.PI/180,lat=SPEC.latitude*rad,b=2*Math.PI*(day-81)/364;
  const eot=9.87*Math.sin(2*b)-7.53*Math.cos(b)-1.5*Math.sin(b);
  const solarHour=hour+(4*(SPEC.longitude-15*SPEC.timezone)+eot)/60;
  const decl=23.45*rad*Math.sin(2*Math.PI*(284+day)/365),ha=(solarHour-12)*15*rad;
  const east=-Math.cos(decl)*Math.sin(ha),up=Math.sin(lat)*Math.sin(decl)+Math.cos(lat)*Math.cos(decl)*Math.cos(ha);
  const south=Math.sin(lat)*Math.cos(decl)*Math.cos(ha)-Math.cos(lat)*Math.sin(decl);
  return {direction:[east,up,south],altitude:Math.asin(up)/rad,solarHour};
}
