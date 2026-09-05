/** Real 3D camera rails. Positions are metres in the source model's Y-up basis. */
export const SHOTS = Object.freeze([
  {name:'overview',label:'THE WHOLE PICTURE',title:'Space for<br><em>what’s next.</em>',subtitle:'แสง เงา และพื้นที่สีเขียว<br>ในมุมมองใหม่ของการทำงาน',positions:[[76,44,102],[64,46,96],[49,41,104]],target:[0,26,0],fov:37},
  {name:'arrival',label:'THE ARRIVAL',title:'A quieter<br><em>kind of arrival.</em>',subtitle:'จากพื้นที่สีเขียวสู่โถงต้อนรับ<br>ใต้หลังคาทางเข้าที่ลอยตัว',positions:[[-19,5.2,40],[-5,4.8,34],[12,5.1,34]],target:[0,3.6,12.5],fov:48},
  {name:'facade',label:'LIGHT & MATERIAL',title:'Designed<br><em>by the light.</em>',subtitle:'แสงเคลื่อนผ่านครีบสีบรอนซ์<br>สร้างจังหวะให้เปลือกอาคาร',positions:[[40,30,32],[32,38,28],[31,46,31]],target:[7,35.5,0],fov:47},
  {name:'garden',label:'THE SKY GARDEN',title:'Room<br><em>to breathe.</em>',subtitle:'ชานพักสีเขียวเหนือเมือง<br>สวนลอยฟ้าชั้น 5 และ 10',positions:[[-16,39.8,30],[-3,39.2,27],[13,40.3,29]],target:[0,38,8],fov:50},
  {name:'roof',label:'A DIFFERENT PERSPECTIVE',title:'Above<br><em>the everyday.</em>',subtitle:'อาคารที่เปิดรับโอกาสใหม่<br>และแนวคิดพลังงานจากดวงอาทิตย์',positions:[[39,79,49],[10,78,48],[-25,76,43]],target:[0,51.5,0],fov:44},
  {name:'bluehour',label:'AFTER THE SUN',title:'A warmer<br><em>side of work.</em>',subtitle:'เมื่อแสงเย็นค่อย ๆ เปลี่ยนเมือง<br>อาคารเผยบรรยากาศอีกด้าน',positions:[[-76,30,100],[-84,38,94],[-76,45,84]],target:[0,25,0],fov:38}
]);
export const SHOT_SECONDS=12;
export const DURATION=SHOTS.length*SHOT_SECONDS;
export function shotAt(seconds){return Math.min(SHOTS.length-1,Math.max(0,Math.floor(seconds/SHOT_SECONDS)));}
export function rail(positions,u){
  // Quadratic Bezier with continuous velocity within each deliberately cut shot.
  return positions[0].map((_,i)=>(1-u)*(1-u)*positions[0][i]+2*(1-u)*u*positions[1][i]+u*u*positions[2][i]);
}
