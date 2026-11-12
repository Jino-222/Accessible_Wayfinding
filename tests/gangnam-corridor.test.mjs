import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {corridorPath,corridorPlan,corridorObservation,projectToPath} from '../web/gangnam/corridor-engine.mjs';
import {initialTracking,observe} from '../web/gangnam/engine.mjs';
const read=name=>JSON.parse(fs.readFileSync(new URL('../web/gangnam/data/'+name,import.meta.url),'utf8'));
const map=read('corridor.json'),records=read('corridor-observations.json'),path=corridorPath(map);
test('observed path projection preserves distance and rejects far estimates',()=>{
  const point=projectToPath(map.nodes[1].position,path);assert.ok(point.distance<1e-8);
  const far=corridorObservation({id:'far',timestamp:1000,accepted:true,pose:[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]},path);
  assert.equal(far.accepted,false);assert.ok(far.projection.distance>100);
  assert.equal(projectToPath([NaN,1,2],path),null);
});
test('all observed checkpoint pairs and width/closure conditions',()=>{
  for(const a of map.nodes)for(const b of map.nodes){
    const r=corridorPlan(map,a.id,b.id);assert.equal(r.status,a.id===b.id?'same':'review');
    if(a.id!==b.id){assert.ok(r.length>0);assert.equal(corridorPlan(map,a.id,b.id,{strictWidth:true}).status,'unavailable');}
  }
  assert.equal(corridorPlan(map,'corridor-a','elevator-approach',{closed:true}).status,'unavailable');
  assert.equal(corridorPlan(map,'corridor-a','corridor-b',{closed:true}).status,'review');
});
test('public test replay has no truth-based accuracy and can regain an observed position',()=>{
  let accepted=0,tracking=0;
  for(const stream of records.streams){
    assert.equal(stream.accuracy,null);let state=initialTracking();
    for(const frame of stream.frames){const event=corridorObservation(frame,path);if(event.accepted)accepted++;state=observe(state,event);if(state.status==='tracking')tracking++;}
  }
  assert.equal(records.streams.reduce((s,v)=>s+v.frames.length,0),67);
  assert.ok(accepted>0);assert.ok(tracking>0);
});
