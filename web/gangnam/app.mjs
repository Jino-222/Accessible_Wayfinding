import {route,initialTracking,observe,routeStep} from './engine.mjs';
import {initCorridor} from './corridor.mjs';
import {initWalk} from './walk.mjs';
import {initExplorer} from './explorer.mjs';
const $=id=>document.getElementById(id);
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let station,observations,result,step=0,tracking=initialTracking(),counter=0,clock=0,recoveryToken=0;
let corridorController,walkController,explorerController;
const svg=(name,attrs={},text='')=>{const el=document.createElementNS('http://www.w3.org/2000/svg',name);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));if(text)el.textContent=text;return el;};
const node=id=>station.nodes.find(n=>n.id===id);
function sample(){clock+=1000;counter++;return {type:'observation',id:`synthetic-${counter}`,time:clock,accepted:true,position:[step*.2,0,0],floor:node(result.nodes[step])?.floor};}
function reset(){
  recoveryToken++;step=0;tracking=initialTracking();
  result=route(station,$('start').value,$('destination').value,{closed:[$('closure').value].filter(Boolean),requireKnownWidth:$('known-width').checked});
  if(result.status==='review') for(let i=0;i<3;i++)tracking=observe(tracking,sample());
  render();
}
function renderMap(){
  if(!station||!result)return;
  const map=$('route-map');map.replaceChildren();
  if(matchMedia('(max-width:650px)').matches){
    map.setAttribute('viewBox','0 0 360 420');
    if(!result.nodes.length){map.append(svg('text',{x:180,y:180,'text-anchor':'middle',fill:'#9a6010','font-size':16},'이 조건의 등록 경로 없음'));return;}
    result.nodes.forEach((id,i)=>{
      const n=node(id),y=40+i*75;
      if(i<result.nodes.length-1)map.append(svg('line',{x1:37,x2:37,y1:y,y2:y+75,stroke:'#10785e','stroke-width':4}));
      map.append(svg('circle',{cx:37,cy:y,r:9,fill:i===step?'#175b91':'#fff',stroke:'#10785e','stroke-width':3}));
      map.append(svg('text',{x:63,y:y-7,'font-size':11,fill:'#61717d'},`${n.floor} · ${String(i+1).padStart(2,'0')}`));
      map.append(svg('text',{x:63,y:y+14,'font-size':13,fill:'#172c3b'},n.label));
    });return;
  }
  map.setAttribute('viewBox','0 0 780 485');
  for(const [floor,y] of [['1F',65],['B1',180],['B2',425]]){
    map.append(svg('line',{x1:40,x2:750,y1:y,y2:y,stroke:'#edf1f3','stroke-width':1}));
    map.append(svg('text',{x:14,y:y+4,class:'floor-label'},floor));
  }
  for(const edge of station.edges){
    const a=node(edge.a),b=node(edge.b),selected=result.edges.includes(edge.id),closed=edge.facility&&edge.facility===$('closure').value;
    map.append(svg('path',{d:`M ${a.x} ${a.y} L ${b.x} ${b.y}`,class:`edge${selected?' selected':''}${closed?' closed':''}`}));
    if(edge.kind==='elevator')map.append(svg('text',{x:a.x+15,y:(a.y+b.y)/2+4,fill:closed?'#a03b30':'#61717d','font-size':12},closed?'중단 시험':'엘리베이터'));
  }
  for(const n of station.nodes){
    map.append(svg('circle',{cx:n.x,cy:n.y,r:result.nodes.includes(n.id)?8:6,fill:'#fff',stroke:result.nodes.includes(n.id)?'#10785e':'#b1c1c8','stroke-width':3}));
    map.append(svg('text',{x:n.x,y:n.y+(n.floor==='1F'?-20:30),'text-anchor':'middle',class:'map-label'},n.label));
  }
  if(result.nodes.length){const p=node(result.nodes[step]);map.append(svg('circle',{cx:p.x,cy:p.y,r:13,fill:tracking.status==='tracking'?'#175b91':'#9a6010',stroke:'#fff','stroke-width':3}));map.append(svg('text',{x:p.x,y:p.y+4,'text-anchor':'middle',fill:'#fff','font-size':11},tracking.status==='tracking'?'●':'?'));}
}
function render(){
  renderMap();const current=routeStep(station,result,step);const valid=!!current;
  $('lose').disabled=!valid; $('recover').disabled=!valid || tracking.status==='tracking';
  $('next').disabled=!valid || current.arrived || tracking.status!=='tracking';
  $('steps').replaceChildren();
  if(!valid){
    $('instruction').textContent=result.reason==='width_unknown'?'확인된 폭 정보가 없습니다':'등록된 연결로는 이동할 수 없습니다';
    $('instruction-detail').textContent=result.reason==='width_unknown'?'폭 확인 조건을 해제하면 미확인 구간을 검토용으로 표시합니다.':'선택한 시설 중단 조건에서 대체 연결을 확인하지 못했습니다. 출발점 또는 목적지를 바꿔보세요.';
    $('tracking-status').textContent='경로 없음 · 가상의 대안을 만들지 않음';return;
  }
  const labels={tracking:'관측 확인 3/3 · 안내 체험 가능',searching:`다시 확인 중 ${tracking.confirmations}/3`,lost:'위치 상실 · 다음 안내 중단',floor_change:'층 전환 · 도착 층에서 다시 확인'};
  $('tracking-status').textContent=`가상 관측 | ${labels[tracking.status]}`;
  $('instruction').textContent=tracking.status!=='tracking'?'위치를 다시 확인해 주세요':current.arrived?'선택한 경로의 마지막 구간':current.edge.kind==='elevator'?`${current.next.floor} 연결 엘리베이터`:`${current.next.label}로 이어지는 구간`;
  $('instruction-detail').textContent=tracking.status!=='tracking'?'복구 관측을 재생하면 서로 다른 관측 3개를 확인한 뒤 재개합니다.':current.arrived?'도식상 경로 체험을 마쳤습니다. 실제 현장 도착을 확인한 결과는 아닙니다.':`${current.node.label} → ${current.next.label}. 폭·경사와 현장 상태는 미확인입니다.`;
  $('next').textContent=current.edge?.kind==='elevator'?'층 이동 체험 →':'다음 구간 체험 →';
  result.nodes.forEach((id,i)=>{const li=document.createElement('li');if(i===step)li.className='current';li.innerHTML=`<span>${String(i+1).padStart(2,'0')}</span>${escape(node(id).label)}`;$('steps').append(li);});
}
function selectTab(value){
  const mode=value===true?'vision':value===false?'route':value;
  for(const id of ['route','vision','corridor','walk','explore']){$(id+'-panel').hidden=id!==mode;$(id+'-tab').classList.toggle('active',id===mode);$(id+'-tab').setAttribute('aria-pressed',String(id===mode));}
  if(mode!=='corridor')corridorController?.pause();
  if(mode!=='walk')walkController?.pause();
  explorerController?.setActive(mode==='explore');
}
function renderFrame(){
  const f=observations.frames[Number($('frame').value)];
  $('observation-image').style.visibility='hidden';
  $('observation-image').src=new URL(f.image,location.href).href;
  $('observation-image').alt=`강남역 B2 공개 원본 관측 ${f.sample_index}. 실제 경로의 현재 화면이 아님.`;
  const accepted=f.accepted&&f.pose;const position=accepted?f.pose.slice(0,3).map(r=>r[3]):null;
  $('pose-summary').innerHTML=`<h3>${accepted?'위치 후보를 계산했습니다':'위치 후보를 수용하지 않았습니다'}</h3><p>${accepted?`대응점 ${f.inliers}개 · 재투영 오차 ${f.reprojection_px.toFixed(2)} px`:'품질 기준을 통과한 위치가 없어 안내 좌표를 표시하지 않습니다.'}</p>`;
  $('pose-detail').textContent=`관측 ID: ${f.id} / 처리 시간: ${(f.elapsed_ms/1000).toFixed(2)}초 / 결과: ${f.reason}`;
  const map=$('pose-map');map.replaceChildren();
  const poses=observations.frames.filter(v=>v.accepted&&v.pose).map(v=>[v.pose[0][3],v.pose[1][3]]);
  const minX=Math.min(...poses.map(p=>p[0]))-10,maxX=Math.max(...poses.map(p=>p[0]))+10,minY=Math.min(...poses.map(p=>p[1]))-10,maxY=Math.max(...poses.map(p=>p[1]))+10;
  const x=v=>45+(v-minX)/(maxX-minX)*430,y=v=>235-(v-minY)/(maxY-minY)*195;
  for(let i=0;i<=4;i++){const xx=minX+(maxX-minX)*i/4;map.append(svg('line',{x1:x(xx),x2:x(xx),y1:25,y2:235,stroke:'#dbe4e7'}));map.append(svg('text',{x:x(xx),y:258,'text-anchor':'middle','font-size':10,fill:'#61717d'},xx.toFixed(0)));}
  for(let i=0;i<=3;i++){const yy=minY+(maxY-minY)*i/3;map.append(svg('line',{x1:45,x2:475,y1:y(yy),y2:y(yy),stroke:'#dbe4e7'}));map.append(svg('text',{x:39,y:y(yy)+3,'text-anchor':'end','font-size':10,fill:'#61717d'},yy.toFixed(0)));}
  map.append(svg('text',{x:48,y:18,'font-size':11,fill:'#61717d'},'추정 좌표 · m / 시설 도식과 미정합'));
  for(const p of poses)map.append(svg('circle',{cx:x(p[0]),cy:y(p[1]),r:3,fill:'#bac9cd'}));
  if(position){map.append(svg('circle',{cx:x(position[0]),cy:y(position[1]),r:7,fill:'#10785e',stroke:'#fff','stroke-width':2}));map.append(svg('text',{x:480,y:276,'text-anchor':'end','font-size':11,fill:'#172c3b'},`x ${position[0].toFixed(2)} / y ${position[1].toFixed(2)} / z ${position[2].toFixed(2)}`));}
  else map.append(svg('text',{x:260,y:145,'text-anchor':'middle','font-size':16,fill:'#9a6010'},'선택한 관측의 위치 없음'));
}
async function init(){
  const read=async path=>{const response=await fetch(new URL(path,location.href));if(!response.ok)throw Error(`HTTP ${response.status}`);return response.json();};
  [station,observations]=await Promise.all([read('data/station.json'),read('data/observations.json')]);
  for(const n of station.nodes.filter(n=>n.selectable&&n.floor!=='B2'))$('start').add(new Option(n.label,n.id));
  for(const n of station.nodes.filter(n=>n.floor==='B2'))$('destination').add(new Option(n.label,n.id));
  ['start','destination','profile','closure','known-width'].forEach(id=>$(id).addEventListener('change',reset));
  $('reset').onclick=reset;
  $('next').onclick=()=>{const current=routeStep(station,result,step);if(!current||current.arrived||tracking.status!=='tracking')return;recoveryToken++;step++;if(current.edge.kind==='elevator')tracking=observe(tracking,{type:'floor'});else tracking=observe(tracking,sample());render();};
  $('lose').onclick=()=>{recoveryToken++;tracking=observe(tracking,{type:'lost'});render();};
  $('recover').onclick=async()=>{const token=++recoveryToken;$('recover').disabled=true;for(let i=0;i<3;i++){await new Promise(r=>setTimeout(r,450));if(token!==recoveryToken)return;tracking=observe(tracking,sample());render();$('recover').disabled=true;}if(token===recoveryToken)render();};
  $('route-tab').onclick=()=>selectTab(false);$('vision-tab').onclick=()=>{selectTab(true);renderFrame();};
  $('corridor-tab').onclick=()=>selectTab('corridor');
  $('walk-tab').onclick=()=>selectTab('walk');
  $('explore-tab').onclick=()=>selectTab('explore');
  observations.frames.forEach((f,i)=>$('frame').add(new Option(`관측 ${f.sample_index} · ${f.accepted?'추정값 있음':'추정 실패'}`,i)));
  $('frame').onchange=renderFrame;
  window.addEventListener('resize',()=>renderMap());
  $('observation-image').onload=()=>{$('observation-image').style.visibility='visible';};
  $('observation-image').onerror=()=>{$('pose-summary').textContent='이미지 파일을 불러오지 못했습니다. 자료 경로 또는 네트워크를 확인해 주세요.';};
  corridorController=await initCorridor();
  walkController=await initWalk().catch(()=>{$('walk-state').textContent='이동 영상 자료를 불러오지 못했습니다';return null;});
  explorerController=await initExplorer();
  $('loading').hidden=true;selectTab('explore');reset();
}
init().catch(()=>{const el=$('loading');el.classList.add('error');el.textContent='필수 자료를 불러오지 못했습니다. 페이지를 새로 열거나 실행 경로를 확인해 주세요. 로컬 실행에는 HTTP 서버가 필요합니다.';});
