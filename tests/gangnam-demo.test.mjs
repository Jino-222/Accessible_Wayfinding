import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {route,observe,initialTracking,routeStep} from '../web/gangnam/engine.mjs';
const station=JSON.parse(fs.readFileSync(new URL('../web/gangnam/data/station.json',import.meta.url),'utf8'));
for(const start of ['exit1','exit10','hall1','hall10'])for(const end of ['platformY','platformG']){
  test(`published topology ${start} -> ${end}`,()=>{
    const result=route(station,start,end);assert.equal(result.status,'review');
    assert.equal(result.nodes.at(-1),end);assert.equal(result.distance_m,null);
    assert.ok(result.unknowns.length);assert.ok(result.edges.every(id=>!station.edges.find(e=>e.id===id).stairs));
    assert.equal(routeStep(station,result,result.nodes.length-1).arrived,true);
    assert.equal(route(station,start,end,{requireKnownWidth:true}).status,'unavailable');
    const internal=end==='platformY'?'internalY':'internalG';
    assert.equal(route(station,start,end,{closed:[internal]}).status,'unavailable');
  });
}
test('no invented reverse, alternative exit, or unregistered destination',()=>{
  assert.equal(route(station,'platformY','exit1').status,'unavailable');
  assert.equal(route(station,'exit1','platformY',{closed:['external1']}).status,'unavailable');
  assert.equal(route(station,'exit1','unknown').status,'invalid');
  assert.equal(route(station,'exit10','platformY',{closed:['external1']}).status,'review');
});
const sample=(id,time,changes={})=>({type:'observation',id,time,accepted:true,position:[1,2,0],floor:'B1',...changes});
test('loss immediately clears pose; three distinct observations restore tracking',()=>{
  let s=initialTracking();for(let i=1;i<=3;i++)s=observe(s,sample(String(i),i*1000));
  assert.equal(s.status,'tracking');s=observe(s,{type:'lost'});assert.equal(s.last,null);assert.equal(s.status,'lost');
  s=observe(s,sample('4',4000));assert.equal(s.status,'searching');assert.equal(s.confirmations,1);
  const duplicate=observe(s,sample('4',5000));assert.equal(duplicate.confirmations,1);
  const stale=observe(s,sample('5',3000));assert.equal(stale.confirmations,1);
  s=observe(s,sample('5',5000));s=observe(s,sample('6',6000));assert.equal(s.status,'tracking');
});
test('floor change, discontinuity and invalid estimates interrupt confirmation',()=>{
  let s=observe(initialTracking(),sample('1',1000));s=observe(s,sample('2',2000,{position:[100,200,0]}));
  assert.equal(s.confirmations,1);assert.equal(s.reason,'inconsistent_observation');
  s=observe(s,{type:'floor'});assert.equal(s.last,null);assert.equal(s.status,'floor_change');
  s=observe(s,sample('3',3000,{accepted:false}));assert.equal(s.status,'lost');
  s=observe(s,sample('4',4000,{position:[NaN,0,0]}));assert.equal(s.status,'lost');
  s=observe(s,sample('5',5000));s=observe(s,sample('6',6000,{floor:'B2'}));assert.equal(s.confirmations,1);
  s=observe(s,sample('7',30000,{floor:'B2'}));assert.equal(s.confirmations,1);
});
test('public observation inputs contain estimates and no evaluation truth or local paths',()=>{
  const raw=fs.readFileSync(new URL('../web/gangnam/data/observations.json',import.meta.url),'utf8');
  assert.ok(!/ground_truth|truth_pose|C:\\|C:\//i.test(raw));
  const data=JSON.parse(raw);assert.equal(data.navigation_binding,null);assert.equal(data.frames.length,12);
  assert.ok(data.frames.some(f=>!f.accepted));assert.ok(data.frames.some(f=>f.accepted));
});
