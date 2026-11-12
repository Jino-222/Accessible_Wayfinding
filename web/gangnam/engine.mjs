export function route(station, start, destination, {closed=[], requireKnownWidth=false, minWidth=.9}={}) {
  const ids=new Set(station.nodes.map(n=>n.id));
  if(!ids.has(start)||!ids.has(destination)) return {status:'invalid',nodes:[],edges:[]};
  if(start===destination) return {status:'same',nodes:[start],edges:[]};
  const queue=[[start,[],[start]]],seen=new Set([start]);
  while(queue.length) {
    const [id,edges,nodes]=queue.shift();
    for(const e of station.edges.filter(e=>e.a===id)) {
      if(e.stairs || closed.includes(e.facility)) continue;
      if(requireKnownWidth && (e.width_m===null || e.width_m<minWidth)) continue;
      if(e.width_m!==null && e.width_m<minWidth) continue;
      if(seen.has(e.b)) continue;
      const next={status:'review',nodes:[...nodes,e.b],edges:[...edges,e.id],
        unknowns:['통행 폭·경사','현재 엘리베이터 운행 상태','현장 동선'],distance_m:null};
      if(e.b===destination) return next;
      seen.add(e.b);queue.push([e.b,next.edges,next.nodes]);
    }
  }
  return {status:'unavailable',nodes:[],edges:[],reason:requireKnownWidth?'width_unknown':'no_registered_route'};
}

export function initialTracking() {
  return {status:'searching',confirmations:0,last:null,seen:[],lastTime:-Infinity,reason:'first_observation'};
}

export function observe(state, event) {
  if(event.type==='lost') return {...state,status:'lost',confirmations:0,last:null,reason:'tracking_lost'};
  if(event.type==='floor') return {...state,status:'floor_change',confirmations:0,last:null,reason:'floor_change'};
  if(event.type!=='observation') return state;
  if(!event.id || state.seen.includes(event.id) || !Number.isFinite(event.time) || event.time<=state.lastTime) {
    return {...state,reason:'duplicate_or_old'};
  }
  const next={...state,seen:[...state.seen,event.id],lastTime:event.time};
  const point=event.position;
  if(!event.accepted || !Array.isArray(point) || point.length!==3 || !point.every(Number.isFinite))
    return {...next,status:'lost',confirmations:0,last:null,reason:'no_valid_pose'};
  if(state.last) {
    const delta=Math.hypot(...point.map((v,i)=>v-state.last.position[i]));
    const dt=(event.time-state.last.time)/1000;
    if(event.floor!==state.last.floor || dt>10 || delta>Math.max(1.5,2*dt))
      return {...next,status:'searching',confirmations:1,last:event,reason:'inconsistent_observation'};
  }
  const confirmations=Math.min(3,state.confirmations+1);
  return {...next,status:confirmations===3?'tracking':'searching',confirmations,last:event,
    reason:confirmations===3?'three_consistent_observations':'confirming'};
}

export function routeStep(station, result, index) {
  if(result.status!=='review') return null;
  const node=station.nodes.find(n=>n.id===result.nodes[index]);
  const edge=station.edges.find(e=>e.id===result.edges[index]);
  const next=station.nodes.find(n=>n.id===result.nodes[index+1]);
  return {node,edge,next,arrived:!next};
}
