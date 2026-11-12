export function corridorPath(map){return [...map.edges[0].polyline,...map.edges[1].polyline.slice(1)];}
export function projectToPath(position,path){
  if(!Array.isArray(position)||position.length<2||!position.every(Number.isFinite))return null;
  let best=null,offset=0;
  for(let i=0;i<path.length-1;i++){
    const a=path[i],b=path[i+1],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
    if(!length)continue;
    const t=Math.max(0,Math.min(1,((position[0]-a[0])*dx+(position[1]-a[1])*dy)/(length*length)));
    const point=[a[0]+t*dx,a[1]+t*dy],distance=Math.hypot(position[0]-point[0],position[1]-point[1]);
    if(!best||distance<best.distance)best={point,distance,along:offset+t*length,segment:i};
    offset+=length;
  }
  return best;
}
export function corridorPlan(map,start,end,{closed=false,strictWidth=false}={}){
  const a=map.nodes.find(n=>n.id===start),b=map.nodes.find(n=>n.id===end);
  if(!a||!b)return {status:'invalid'};
  if(start===end)return {status:'same'};
  if(strictWidth)return {status:'unavailable',reason:'unknown_width'};
  if(closed&&end==='elevator-approach')return {status:'unavailable',reason:'closed_destination'};
  const path=corridorPath(map),from=projectToPath(a.position,path),to=projectToPath(b.position,path);
  return {status:'review',from:from.along,to:to.along,length:Math.abs(from.along-to.along),start:a,end:b};
}
export function corridorObservation(frame,path){
  const position=frame.pose?.slice(0,3).map(r=>r[3]);
  const projected=position?projectToPath(position,path):null;
  return {type:'observation',id:frame.id,time:frame.timestamp/1000,position:position??null,floor:'B2',
    accepted:!!frame.accepted&&!!projected&&projected.distance<=3,projection:projected};
}
