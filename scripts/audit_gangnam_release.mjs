import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const web=path.join(root,'web/gangnam');
const read=n=>JSON.parse(fs.readFileSync(path.join(web,'data',n),'utf8'));
const rights=read('asset-rights.json');
assert.equal(rights.assets.length,82);
for(const asset of rights.assets){
  const file=path.resolve(web,asset.file);assert.ok(file.startsWith(web+path.sep));
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),asset.sha256);
  assert.equal(asset.modified,false);
}
for(const name of ['observations.json','corridor-observations.json']){
  const text=fs.readFileSync(path.join(web,'data',name),'utf8');
  assert.ok(!/C:[\\/]|Users[\\/]|position_error_m|orientation_error_deg|reference_pose|ground_truth_pose/i.test(text));
}
const ids=new Set();
const records=read('corridor-observations.json');
for(const stream of records.streams){
  assert.equal(stream.accuracy,null);let previous=-Infinity;
  for(const f of stream.frames){assert.ok(!ids.has(f.id));ids.add(f.id);assert.ok(f.timestamp>previous);previous=f.timestamp;assert.ok(fs.existsSync(path.join(web,f.image)));}
}
assert.equal(ids.size,67);
const html=fs.readFileSync(path.join(web,'index.html'),'utf8');
for(const [,href] of html.matchAll(/(?:href|src)="(\.\/[^"#]+)"/g))assert.ok(fs.existsSync(path.join(web,href)),'Missing '+href);
assert.ok(!/https?:\/\//.test(fs.readFileSync(path.join(web,'style.css'),'utf8')),'Styles must not require a remote CDN');
const walkDir=path.join(web,'assets/walk');
const walkManifest=JSON.parse(fs.readFileSync(path.join(walkDir,'manifest.json'),'utf8'));
for(const [name,hash] of Object.entries(walkManifest.files)){
  const p=path.resolve(walkDir,name);assert.ok(p.startsWith(walkDir+path.sep));
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),hash);
}
const walkResults=JSON.parse(fs.readFileSync(path.join(walkDir,'results.json'),'utf8'));
const walkTimeline=JSON.parse(fs.readFileSync(path.join(walkDir,'timeline.json'),'utf8'));
assert.ok(walkResults.representative_duration_s>=60&&walkResults.representative_duration_s<=90);
for(const r of walkResults.runs){
  const frames=walkTimeline[r.id];assert.ok(Math.abs(frames.length/15-r.duration_s)<.001);
  for(const frame of frames){
    assert.ok(!frame.visible||(!frame.blackout&&frame.state==='guiding'));
    assert.ok(!frame.observation||frame.observation.time_s<=frame.time_s+.001);
  }
  assert.equal(r.final_state,r.id==='closed'?'blocked':'arrived');
}
let explorerAssets=0;
for(const folder of ['vendor/three','assets/explorer']){
  const dir=path.join(web,folder),manifest=JSON.parse(fs.readFileSync(path.join(dir,'manifest.json'),'utf8'));
  for(const [name,hash] of Object.entries(manifest.files)){
    const p=path.resolve(dir,name);assert.ok(p.startsWith(dir+path.sep));
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),hash);explorerAssets++;
  }
}
const explorer=read('explorer-scene.json');
assert.equal(explorer.path.length,13);assert.ok(Math.abs(explorer.length-walkResults.length_m)<1e-5);
assert.match(explorer.tracking,/Synthetic pose observations/);
for(const p of explorer.path)assert.ok(Number.isFinite(p.x)&&Number.isFinite(p.z));
for(const p of ['explorer.mjs','explorer-engine.mjs','explorer-scene.mjs'])assert.ok(fs.existsSync(path.join(web,p)));
console.log(JSON.stringify({status:'passed',unchanged_images:rights.assets.length,public_test_observations:ids.size,public_test_accuracy:null,synthetic_walk_frames:Object.values(walkTimeline).reduce((a,b)=>a+b.length,0),walk_media_hashes:Object.keys(walkManifest.files).length,explorer_assets:explorerAssets,required_local_assets:true}));
