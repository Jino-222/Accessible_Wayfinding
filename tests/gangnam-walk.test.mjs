import test from 'node:test';
import assert from 'node:assert/strict';
import {frameAt} from '../web/gangnam/walk.mjs';

test('playback never shows future observation at a time between frames',()=>{
  const frames=[{time_s:0,state:'confirming'},{time_s:.5,state:'guiding'},{time_s:1,state:'position_uncertain'}];
  assert.equal(frameAt(frames,.49).state,'confirming');
  assert.equal(frameAt(frames,.5).state,'guiding');
  assert.equal(frameAt(frames,3).state,'position_uncertain');
});
test('empty and invalid video times do not fabricate a result',()=>{
  assert.equal(frameAt([],0),null);assert.equal(frameAt([{time_s:0}],NaN),null);
});
