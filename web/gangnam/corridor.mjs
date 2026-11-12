import {initialTracking,observe} from './engine.mjs';
import {corridorPath,corridorPlan,corridorObservation,projectToPath} from './corridor-engine.mjs';

export async function initCorridor(){
  const $=id=>document.getElementById('corridor-'+id);
  const read=async file=>{const r=await fetch(new URL(file,location.href));if(!r.ok)throw Error(file);return r.json();};
  const [map,records]=await Promise.all([read('data/corridor.json'),read('data/corridor-observations.json')]);
  const path=corridorPath(map);let stream=records.streams[0],index=0;
  let state=initialTracking(),plan,lost=false,timer=null,imageSerial=0;
  const add=(name,attrs,text)=>{const el=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);if(text)el.textContent=text;$('map').append(el);return el;};
  const pause=()=>{clearInterval(timer);timer=null;$('play').textContent='기록 재생';};
  for(const n of map.nodes){$('start').add(new Option(n.label,n.id));$('end').add(new Option(n.label,n.id));}
  $('start').value='corridor-a';$('end').value='elevator-approach';
  records.streams.forEach(s=>$('case').add(new Option(`${s.name} · ${s.frames.length}장`,s.id)));
  $('case').value=stream.id;
  function updatePlan(){plan=corridorPlan(map,$('start').value,$('end').value,{closed:$('closed').checked,strictWidth:$('width').checked});render(false);}
  function redraw(observation){
    $('map').replaceChildren();const xs=path.map(p=>p[0]),ys=path.map(p=>p[1]);
    const xmin=Math.min(...xs)-5,xmax=Math.max(...xs)+5,ymin=Math.min(...ys)-9,ymax=Math.max(...ys)+9;
    const scale=Math.min(430/(xmax-xmin),195/(ymax-ymin));
    const x=v=>260+(v-(xmin+xmax)/2)*scale,y=v=>145-(v-(ymin+ymax)/2)*scale;
    add('polyline',{points:path.map(p=>`${x(p[0])},${y(p[1])}`).join(' '),fill:'none',stroke:'#c4d2d7','stroke-width':8});
    if(plan.status==='review'){
      const lo=Math.min(plan.from,plan.to),hi=Math.max(plan.from,plan.to);
      const chosen=path.filter(p=>{const v=projectToPath(p,path).along;return v>=lo-0.01&&v<=hi+0.01;});
      add('polyline',{points:chosen.map(p=>`${x(p[0])},${y(p[1])}`).join(' '),fill:'none',stroke:'#10785e','stroke-width':6});
    }
    map.nodes.forEach((n,i)=>{const px=x(n.position[0]),py=y(n.position[1]);add('circle',{cx:px,cy:py,r:7,fill:'#fff',stroke:'#10785e','stroke-width':3});add('text',{x:px,y:py+(i===1?-22:30),'text-anchor':'middle','font-size':12,fill:'#172c3b'},i===1?'엘리베이터 앞':i===0?'관측 A':'관측 B');});
    if(!lost&&observation.accepted){const p=observation.position;add('circle',{cx:x(p[0]),cy:y(p[1]),r:8,fill:state.status==='tracking'?'#175b91':'#a56b19',stroke:'#fff','stroke-width':2});}
    else if(observation.position&&observation.projection?.distance>3)add('text',{x:260,y:28,'text-anchor':'middle','font-size':12,fill:'#9a6010'},'추정 위치가 등록된 동선 밖에 있음');
    add('line',{x1:40,x2:40+5*scale,y1:258,y2:258,stroke:'#61717d','stroke-width':2});
    add('text',{x:40,y:278,'font-size':10,fill:'#61717d'},'5 m · 지도 좌표 기준');
  }
  function render(image=true){
    const frame=stream.frames[index],observation=corridorObservation(frame,path);
    $('frame').max=stream.frames.length-1;$('frame').value=index;
    $('count').textContent=`${index+1} / ${stream.frames.length}`;
    $('next').disabled=index===stream.frames.length-1;
    const near=examples();$('approach').disabled=near.near<0;
    $('approach').title=near.near<0?'이 영상에는 연속 확인 후 접근 지점 2 m 이내인 관측이 없습니다.':'';
    $('lost').disabled=lost;$('resume').disabled=!lost;
    if(image){
      const serial=++imageSerial,photo=$('image');photo.style.visibility='hidden';
      $('caption').textContent=`관측 ${index+1} · 원본 사진 불러오는 중`;
      photo.onload=()=>{if(serial!==imageSerial)return;photo.style.visibility='visible';$('caption').textContent=`관측 ${index+1} · ${frame.id.split('/').at(-1)}`;};
      photo.onerror=()=>{if(serial!==imageSerial)return;pause();$('caption').textContent='사진을 불러오지 못했습니다. 다음 관측을 선택하거나 페이지를 다시 열어 주세요.';};
      photo.src=new URL(frame.image,location.href).href;
      photo.alt=`강남역 B2 공개 시험 관측 ${index+1}. 저장된 추정값을 계산한 실제 입력 이미지.`;
    }
    redraw(observation);
    if(plan.status==='unavailable'){
      $('instruction').textContent=plan.reason==='unknown_width'?'통행 폭을 확인할 수 없습니다':'엘리베이터 접근을 중단했습니다';
      $('status').textContent=plan.reason==='unknown_width'?'공개 자료에 폭 정보가 없어 이 조건의 경로를 표시하지 않습니다.':'시험 조건: 이 구간에 등록된 다른 엘리베이터가 없습니다.';
      $('distance').textContent='';return;
    }
    if(plan.status==='same'){$('instruction').textContent='서로 다른 두 지점을 골라 주세요';$('status').textContent='출발점과 목적지가 같습니다.';$('distance').textContent='';return;}
    $('distance').textContent=`선택 경로: 기록 동선 기준 약 ${plan.length.toFixed(0)} m · 현재 통행 가능 여부 미확인`;
    if(lost){$('instruction').textContent='위치를 잃어 안내를 멈췄습니다';$('status').textContent='시험용 위치 상실 주입 중 · 관측 재개 후 다음 영상부터 다시 검사';return;}
    if(state.status!=='tracking'){
      $('instruction').textContent='현재 위치를 다시 확인하는 중';
      $('status').textContent=!frame.accepted?'영상의 위치 후보가 품질 기준을 통과하지 못함':observation.projection?.distance>3?'추정 위치가 등록된 동선에서 3 m 이상 벗어남':`연속 확인 ${state.confirmations}/3 · 다음 안내 보류`;
      return;
    }
    const current=observation.projection;
    const lo=Math.min(plan.from,plan.to),hi=Math.max(plan.from,plan.to);
    if(current.along<lo-2||current.along>hi+2){$('instruction').textContent='선택 경로와 다른 구간의 관측입니다';$('status').textContent='기록 영상의 촬영 동선은 고정되어 있습니다. 출발점·목적지 또는 촬영 순서를 바꿔보세요.';return;}
    const remaining=Math.abs(current.along-plan.to);
    $('instruction').textContent=remaining<=2?'접근 지점 부근으로 추정됩니다':`${plan.end.label} 방향으로 이어지는 구간`;
    $('status').textContent=`연속 관측 3/3 · 기록 동선을 따라 약 ${remaining.toFixed(0)} m 남음 · 실제 도착 확인 아님`;
  }
  function apply(frame){const event=corridorObservation(frame,path);state=observe(state,lost?{...event,accepted:false}:event);}
  function seek(value){pause();lost=false;index=value;state=initialTracking();for(let i=0;i<=index;i++)apply(stream.frames[i]);render();}
  function next(){if(index>=stream.frames.length-1){pause();return;}index++;apply(stream.frames[index]);render();if(index===stream.frames.length-1)pause();}
  function examples(){
    let s=initialTracking(),first=-1,near=-1,best=Infinity;
    const target=projectToPath(map.nodes.find(n=>n.id==='elevator-approach').position,path).along;
    stream.frames.forEach((f,i)=>{const e=corridorObservation(f,path);s=observe(s,e);if(s.status==='tracking'){if(first<0)first=i;const d=Math.abs(e.projection.along-target);if(d<best){best=d;near=i;}}});
    return {first,near:best<=2?near:-1};
  }
  for(const id of ['start','end','closed','width'])$(id).onchange=updatePlan;
  $('case').onchange=()=>{stream=records.streams.find(s=>s.id===$('case').value);seek(0);};
  $('frame').oninput=()=>seek(Number($('frame').value));
  $('next').onclick=()=>{pause();next();};
  $('play').onclick=()=>{if(timer){pause();return;}if(index===stream.frames.length-1)seek(0);$('play').textContent='일시 정지';timer=setInterval(next,1800);};
  $('lost').onclick=()=>{lost=true;state=observe(state,{type:'lost'});render(false);};
  $('resume').onclick=()=>{lost=false;state=observe(state,{type:'lost'});render(false);};
  $('example').onclick=()=>seek(Math.max(0,examples().first));
  $('approach').onclick=()=>seek(Math.max(0,examples().near));
  $('failure').onclick=()=>seek(Math.max(0,stream.frames.findIndex(f=>!f.accepted)));
  plan=corridorPlan(map,$('start').value,$('end').value);seek(Math.max(0,examples().first));
  return {pause};
}
