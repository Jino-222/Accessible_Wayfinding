import {Explorer} from './explorer-engine.mjs';
const $=id=>document.getElementById(id);
const labels={ready:'엘리베이터 앞까지 이동',paused:'이동을 잠시 멈췄습니다',confirming:'위치를 다시 확인하는 중',guiding:'엘리베이터 방향으로 이동',lost:'위치 인식이 끊겼습니다',blocked:'엘리베이터 접근 중단',arrived:'가상 엘리베이터 앞 도착'};
const descriptions={ready:'이동 시작을 누르세요. 화면 버튼이나 방향키로 직접 움직일 수 있습니다.',paused:'계속 이동을 누르면 새 관측 3개를 확인한 뒤 안내를 재개합니다.',confirming:'서로 다른 모의 관측 3개를 기다립니다. 아직 방향과 거리를 표시하지 않습니다.',guiding:'바닥의 화살표를 따라 이동하세요. 화면을 드래그하면 시선을 돌릴 수 있습니다.',lost:'방향과 남은 거리를 숨겼습니다. 관측을 복구하면 현재 이동한 지점에서 다시 확인합니다.',blocked:'등록된 대체 경로가 없어 안내를 중단했습니다. 접근 재개 후 위치를 다시 확인합니다.',arrived:'등록된 가상 접근 지점에 도착했습니다. 실제 시설 도착이나 탑승 가능 여부를 판정한 결과는 아닙니다.'};
const keyActions={ArrowUp:'forward',KeyW:'forward',ArrowDown:'back',KeyS:'back',ArrowLeft:'turnLeft',KeyQ:'turnLeft',ArrowRight:'turnRight',KeyE:'turnRight',KeyA:'left',KeyD:'right'};

export async function initExplorer(){
  const canvas=$('explore-canvas');let scene,model,active=false,raf=0,last=0,lastUI=0,held=null,heldSince=0,drag=null;
  const keys=new Set();let logSignature='',failed=false;
  $('explore-fallback').onclick=()=>$('walk-tab').click();
  try{
    const response=await fetch(new URL('data/explorer-scene.json',location.href));if(!response.ok)throw Error('Scene unavailable');
    const config=await response.json();model=new Explorer(config);
    const {createScene}=await import('./explorer-scene.mjs');scene=createScene(canvas,config);
  }catch{
    $('explore-error').hidden=false;$('explore-shade').hidden=true;$('explore-state').textContent='3D 화면 준비 실패';
    $('explore-description').textContent='실행 영상은 3D 기능 없이도 재생할 수 있습니다.';return null;
  }
  function clearInput(){keys.clear();held=null;drag=null;}
  function step(action,amount=.6){
    if(action==='forward')model.move(amount,0,0);if(action==='back')model.move(-amount,0,0);
    if(action==='left')model.move(0,-amount,0);if(action==='right')model.move(0,amount,0);
    if(action==='turnLeft')model.move(0,0,-Math.PI/12);if(action==='turnRight')model.move(0,0,Math.PI/12);
    paint();
  }
  function map(view){
    const el=$('explore-map'),x=z=>22+z/model.length*174,y=x=>44-x*9;
    const path=model.path.map((p,i)=>`${i?'L':'M'}${x(p.z).toFixed(1)},${y(p.x).toFixed(1)}`).join(' ');
    const p=view.observation,marker=p?`<g transform="translate(${x(p.z).toFixed(1)},${y(p.x).toFixed(1)}) rotate(${-p.yaw*180/Math.PI})"><circle r="8" fill="#fff"/><path d="M7 0 L-5 -4 L-3 0 L-5 4Z" fill="#204f83"/></g>`:'';
    el.innerHTML=`<rect x="12" y="13" width="195" height="60" rx="3" fill="#f2f4ef" stroke="#c5cec5"/><path d="${path}" stroke="${view.arrowVisible?'#10785e':'#b4c1b7'}" stroke-width="3" fill="none" stroke-dasharray="4 3"/><circle cx="22" cy="44" r="3" fill="#889c90"/><rect x="190" y="33" width="12" height="22" rx="2" fill="${view.closed?'#9d5841':'#254d40'}"/>${marker}`;
  }
  function ui(view){
    const heading=$('explore-state');if(heading.textContent!==labels[view.status])heading.textContent=labels[view.status];heading.dataset.state=view.status;
    $('explore-description').textContent=descriptions[view.status];
    $('explore-distance').textContent=view.remaining==null?'—':view.status==='arrived'?'접근 완료':`${view.remaining.toFixed(1)} m`;
    $('explore-count').textContent=`${view.confirmations} / 3`;
    $('explore-start').disabled=view.running||failed;$('explore-start').textContent=view.running?'이동 중':view.started?'계속 이동':'이동 시작';
    $('explore-pause').disabled=!view.running;$('explore-reset').disabled=false;
    for(const el of document.querySelectorAll('[data-explore-move]'))el.disabled=!view.running;
    $('explore-mask').disabled=$('explore-close').disabled=!view.started||failed;
    $('explore-mask').textContent=view.masked?'위치 인식 복구':'위치 인식 끊기';$('explore-mask').setAttribute('aria-pressed',String(view.masked));
    $('explore-close').textContent=view.closed?'엘리베이터 접근 재개':'엘리베이터 접근 중단';$('explore-close').setAttribute('aria-pressed',String(view.closed));
    $('explore-running').textContent=view.running?'직접 조작 중':view.started?'일시정지':'출발 대기';
    const shade=$('explore-shade');shade.hidden=!(['ready','paused'].includes(view.status)||view.masked);
    shade.classList.toggle('masked',view.masked);
    $('explore-shade-title').textContent=view.masked?'위치 관측을 받지 못했습니다':view.status==='paused'?'이동 일시정지':'엘리베이터로 가는 길';
    $('explore-shade-detail').textContent=view.masked?'화살표와 거리를 숨겼습니다. 관측을 복구해 다시 확인하세요.':view.status==='paused'?'계속 이동을 누르면 다시 위치를 확인합니다.':'이동 시작을 누른 뒤 화면 버튼이나 키보드로 조작하세요.';
    $('explore-unmask').hidden=!view.masked;
    $('explore-hud').hidden=!view.arrowVisible;
    if(view.arrowVisible){
      const angle=view.direction*180/Math.PI;$('explore-bearing').style.transform=`rotate(${angle}deg)`;
      $('explore-hud-text').textContent=Math.abs(angle)>125?'뒤로 돌아 엘리베이터 방향으로':angle>28?'오른쪽으로 방향을 맞추세요':angle< -28?'왼쪽으로 방향을 맞추세요':'엘리베이터 방향으로 직진';
      $('explore-hud-distance').textContent=`${view.remaining.toFixed(1)} m 남음 · 모의 관측 기준`;
    }
    map(view);
    const signature=JSON.stringify(model.events);
    if(signature!==logSignature){
      logSignature=signature;$('explore-events').replaceChildren();
      for(const item of model.events.slice(-5).reverse()){
        const li=document.createElement('li'),t=document.createElement('time'),text=document.createElement('span');
        t.textContent=`${item.time_s.toFixed(1)}s`;text.textContent=item.message;li.append(t,text);$('explore-events').append(li);
      }
    }
    $('explore-export').disabled=!view.started;
  }
  function paint(){const view=model.view();ui(view);if(!failed)scene.render(model.pose,view);}
  function frame(now){
    if(!active||failed)return;
    const dt=(now-last)/1000;last=now;
    const actions=new Set(keys);if(held&&now-heldSince>260)actions.add(held);
    model.tick(dt,{forward:Number(actions.has('forward'))-Number(actions.has('back')),side:Number(actions.has('right'))-Number(actions.has('left')),turn:Number(actions.has('turnRight'))-Number(actions.has('turnLeft'))});
    const view=model.view();scene.render(model.pose,view);
    if(now-lastUI>80){lastUI=now;ui(view);}raf=requestAnimationFrame(frame);
  }
  $('explore-start').onclick=()=>{clearInput();model.start();canvas.focus({preventScroll:true});paint();};
  $('explore-pause').onclick=()=>{clearInput();model.pause();paint();};
  $('explore-reset').onclick=()=>{clearInput();model.reset();paint();};
  $('explore-mask').onclick=()=>{clearInput();model.setMasked(!model.masked);paint();};
  $('explore-unmask').onclick=()=>{model.setMasked(false);paint();};
  $('explore-close').onclick=()=>{clearInput();model.setClosed(!model.closed);paint();};
  for(const button of document.querySelectorAll('[data-explore-move]')){
    const action=button.dataset.exploreMove;
    button.addEventListener('pointerdown',event=>{if(!model.running||event.button>0)return;event.preventDefault();button.setPointerCapture(event.pointerId);held=action;heldSince=performance.now();step(action);});
    const release=()=>{held=null;};button.addEventListener('pointerup',release);button.addEventListener('pointercancel',release);button.addEventListener('lostpointercapture',release);
    button.addEventListener('click',event=>{if(event.detail===0)step(action);});
    button.addEventListener('contextmenu',event=>event.preventDefault());
  }
  canvas.addEventListener('keydown',event=>{
    if(event.code==='Escape'){event.preventDefault();clearInput();model.pause();paint();return;}
    const action=keyActions[event.code];if(!action||!active||!model.running)return;event.preventDefault();
    if(!event.repeat)step(action,.18);keys.add(action);
  });
  window.addEventListener('keyup',event=>{const action=keyActions[event.code];if(action)keys.delete(action);});
  canvas.addEventListener('pointerdown',event=>{if(!model.running||event.button>0)return;canvas.focus({preventScroll:true});canvas.setPointerCapture(event.pointerId);drag={id:event.pointerId,x:event.clientX};});
  canvas.addEventListener('pointermove',event=>{if(drag?.id!==event.pointerId)return;const dx=event.clientX-drag.x;drag.x=event.clientX;model.move(0,0,dx*.004);paint();});
  const endDrag=()=>{drag=null;};canvas.addEventListener('pointerup',endDrag);canvas.addEventListener('pointercancel',endDrag);canvas.addEventListener('lostpointercapture',endDrag);
  const suspend=()=>{clearInput();model.pause();paint();};
  window.addEventListener('blur',suspend);document.addEventListener('visibilitychange',()=>{if(document.hidden)suspend();});
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();failed=true;suspend();$('explore-error').hidden=false;$('explore-shade').hidden=true;cancelAnimationFrame(raf);});
  canvas.addEventListener('webglcontextrestored',()=>{failed=false;$('explore-error').hidden=true;model.pause();last=performance.now();paint();if(active)raf=requestAnimationFrame(frame);});
  $('explore-export').onclick=()=>{
    const blob=new Blob([JSON.stringify(model.report(),null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download='wayfinding-interaction.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  paint();
  return {setActive(value){
    if(active===value)return;active=value;cancelAnimationFrame(raf);clearInput();
    if(!value){model.pause();paint();return;}scene.resize();last=performance.now();paint();if(!failed)raf=requestAnimationFrame(frame);
  }};
}
