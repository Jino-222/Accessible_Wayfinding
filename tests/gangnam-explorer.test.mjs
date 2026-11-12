import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {Explorer,projectPath} from '../web/gangnam/explorer-engine.mjs';
const config=JSON.parse(fs.readFileSync(new URL('../web/gangnam/data/explorer-scene.json',import.meta.url),'utf8'));
const advance=(m,seconds,controls={})=>{for(let t=0;t<seconds;t+=.05)m.tick(.05,controls);};
const ready=()=>{const m=new Explorer(config);m.start();advance(m,1.4);assert.equal(m.view().status,'guiding');return m;};

test('movement stays paused until started; new observations are required',()=>{
  const m=new Explorer(config);m.move(2);assert.equal(m.pose.z,0);m.start();
  advance(m,.5);assert.equal(m.view().confirmations,1);assert.equal(m.view().arrowVisible,false);
  advance(m,.9);assert.equal(m.view().status,'guiding');assert.ok(Math.abs(m.view().remaining-22.06)<.05);
});
test('image loss immediately removes old guidance and restores at the moved location',()=>{
  const m=ready();m.setMasked(true);assert.equal(m.view().status,'lost');assert.equal(m.view().remaining,null);assert.equal(m.view().observation,null);assert.equal(m.view().arrowVisible,false);
  m.move(5);advance(m,1.5);assert.equal(m.view().confirmations,0);
  m.setMasked(false);advance(m,.9);assert.equal(m.view().arrowVisible,false);
  advance(m,.5);assert.equal(m.view().status,'guiding');assert.ok(m.view().remaining<18);
});
test('closure hides guidance even at the destination and reopening reconfirms',()=>{
  const m=ready();m.setClosed(true);m.move(config.length);advance(m,1.4);
  assert.equal(m.view().status,'blocked');assert.equal(m.view().arrowVisible,false);assert.equal(m.view().remaining,null);
  m.setClosed(false);assert.equal(m.view().status,'confirming');advance(m,1.4);assert.equal(m.view().status,'arrived');
});
test('restoring images cannot override a closed elevator',()=>{
  const m=ready();m.setMasked(true);m.setClosed(true);m.setMasked(false);advance(m,1.4);
  assert.equal(m.view().status,'blocked');assert.equal(m.view().arrowVisible,false);
});
test('reopening an elevator cannot override missing observations',()=>{
  const m=ready();m.setClosed(true);m.setMasked(true);m.setClosed(false);advance(m,2);
  assert.equal(m.view().status,'lost');assert.equal(m.view().arrowVisible,false);
});
test('arriving requires a fresh confirmed pose, not movement alone',()=>{
  const m=ready();m.move(config.length);assert.equal(m.view().status,'guiding');advance(m,.5);
  assert.equal(m.view().status,'arrived');assert.equal(m.view().arrowVisible,false);
  m.move(-2);advance(m,.5);assert.equal(m.view().status,'guiding');
});
test('pause and tab suspension clear guidance and require confirmation on return',()=>{
  const m=ready();m.pause();const before={...m.pose};m.move(10);advance(m,10,{forward:1});
  assert.deepEqual(m.pose,before);assert.equal(m.view().status,'paused');assert.equal(m.view().arrowVisible,false);
  m.start();assert.equal(m.view().status,'confirming');advance(m,1.4);assert.equal(m.view().status,'guiding');
});
test('turning changes the guidance bearing and the movement direction',()=>{
  const m=ready();m.move(0,0,Math.PI/2);m.move(1);advance(m,.5);
  assert.ok(m.pose.x>.99);assert.ok(Math.abs(m.pose.z)<.01);assert.ok(m.view().direction< -Math.PI/3);
});
test('walls, corridor ends and delayed frames limit movement',()=>{
  const m=ready();m.move(100,100);assert.ok(m.pose.x<=config.halfWidth-.65);assert.ok(m.pose.z<=m.length+.35);
  m.move(-100,-100);assert.ok(m.pose.x>=-config.halfWidth+.65);assert.ok(m.pose.z>=-1.1);
  const before=m.travelled;m.tick(100,{forward:1});assert.ok(m.travelled-before<=1.65*.08+.0001);
});
test('duplicate, stale and future observations cannot restore tracking',()=>{
  const m=ready(),last=m.lastId,time=m.lastTime;m.setMasked(true);m.setMasked(false);
  assert.equal(m.observe({id:last,time,pose:m.pose}),false);
  assert.equal(m.observe({id:last+100,time:m.time+5,pose:m.pose}),false);
  assert.equal(m.observe({id:last+100,time:m.time-5,pose:m.pose}),false);
  assert.equal(m.view().arrowVisible,false);
});
test('reset clears faults, movements and session observations',()=>{
  const m=ready();m.move(10);m.setClosed(true);m.setMasked(true);m.reset();
  assert.equal(m.view().status,'ready');assert.equal(m.view().masked,false);assert.equal(m.view().closed,false);assert.equal(m.pose.z,0);assert.equal(m.travelled,0);
});
test('exported evidence identifies synthetic observations and retains both fault events',()=>{
  const m=ready();m.setMasked(true);m.setMasked(false);m.setClosed(true);const r=m.report();
  assert.match(r.tracking,/synthetic/);assert.ok(r.events.some(e=>e.message.includes('끊김')));assert.ok(r.events.some(e=>e.message.includes('접근 중단')));assert.equal(r.finalState,'blocked');assert.equal(r.accuracy,undefined);
});
test('browser path length matches the published Unity protocol',()=>{
  const r=JSON.parse(fs.readFileSync(new URL('../web/gangnam/assets/walk/results.json',import.meta.url),'utf8'));
  assert.ok(Math.abs(projectPath(config.path,config.path[0]).length-r.length_m)<1e-6);
});
