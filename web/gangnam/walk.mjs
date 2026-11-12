const $=id=>document.getElementById(id);
const labels={guiding:'엘리베이터 방향으로 이동',confirming:'위치를 다시 확인하는 중',locating:'위치 확인 중',position_uncertain:'위치 확인 불가',arrived:'가상 접근 지점 도착',blocked:'엘리베이터 접근 중단'};
const names={overview:'전체 과정',normal:'정상 이동',loss:'상실·복구',closed:'접근 중단'};
export function frameAt(frames,time){
  if(!frames?.length||!Number.isFinite(time))return null;
  let lo=0,hi=frames.length-1;
  while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(frames[mid].time_s<=time)lo=mid;else hi=mid-1;}
  return frames[lo];
}
export async function initWalk(){
  const read=async path=>{const r=await fetch(new URL(path,location.href));if(!r.ok)throw Error(`HTTP ${r.status}`);return r.json();};
  const [results,timeline]=await Promise.all([read('assets/walk/results.json'),read('assets/walk/timeline.json')]);
  const video=$('walk-video');let selected='normal';
  function sync(){
    const frame=frameAt(timeline[selected],video.currentTime);if(!frame)return;
    const obs=frame.observation,chapter=frame.chapter||selected;
    $('walk-state').textContent=labels[frame.state]||'위치 확인 중';
    $('walk-state').dataset.state=frame.state;
    $('walk-distance').textContent=frame.state==='guiding'&&obs?.remaining_m!=null?`${obs.remaining_m.toFixed(1)} m`:frame.state==='arrived'?'접근 완료':'—';
    $('walk-inliers').textContent=obs?`${obs.inliers}개`:'—';
    $('walk-latency').textContent=obs?`${(obs.http_ms/1000).toFixed(2)}초`:'—';
    $('walk-arrow').textContent=frame.visible?'표시':'숨김';
    $('walk-clock').textContent=`${video.currentTime.toFixed(1)} / ${(video.duration||0).toFixed(1)}초`;
    $('walk-chapter').textContent=names[chapter];
    $('walk-observed').textContent=obs?`관측 시각 ${obs.time_s.toFixed(1)}초 · 다음 관측 전까지 같은 추정값`:'관측 대기';
    $('walk-description').textContent=frame.state==='blocked'?'이 실험에는 대체 연결을 등록하지 않았습니다. 경로를 만들어 안내하지 않고 중단합니다.':frame.state==='position_uncertain'?'입력 영상을 인식하지 못해 화살표를 숨겼습니다. 서로 다른 관측 3개를 확인한 뒤 안내를 재개합니다.':frame.state==='arrived'?'가상 장면의 등록 지점에 접근했습니다. 실제 강남역 현장 도착을 판정한 결과는 아닙니다.':'가상 카메라의 영상으로 위치를 추정하고, 등록된 경로에서 다음 안내 방향을 계산합니다.';
  }
  function choose(id){
    video.pause();selected=id;
    video.src=`./assets/walk/${id}.mp4`;video.poster=`./assets/walk/${id}.jpg`;
    const track=$('walk-captions');track.removeAttribute('src');if(id!=='overview')track.src=`./assets/walk/${id}.vtt`;
    document.querySelectorAll('[data-walk-case]').forEach(b=>{const active=b.dataset.walkCase===id;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));});
    $('walk-edit-note').textContent=id==='overview'?'정상 이동 전체 + 복구·중단 구간을 이어 붙인 요약 영상':'한 번의 시나리오를 처음부터 끝까지 재생';
    const row=results.runs.find(r=>r.id===id);
    $('walk-case-summary').textContent=row?`영상 관측 ${row.observations}회 · 0.5 m·5° 이내 ${row.accurate}회 · 안내 표시 중 기준 초과 ${row.visible_inaccurate}회`:'세 시나리오의 주요 장면';
    sync();
  }
  document.querySelectorAll('[data-walk-case]').forEach(b=>b.onclick=()=>choose(b.dataset.walkCase));
  $('walk-play').onclick=async()=>{try{await video.play();}catch{$('walk-description').textContent='영상의 재생 버튼을 눌러 주세요.';}};
  $('walk-restart').onclick=()=>{video.pause();video.currentTime=0;sync();};
  $('walk-event').onclick=()=>{choose('loss');const jump=()=>{video.currentTime=11;video.removeEventListener('loadedmetadata',jump);};video.addEventListener('loadedmetadata',jump);};
  video.addEventListener('timeupdate',sync);video.addEventListener('loadedmetadata',sync);
  video.addEventListener('seeking',sync);video.addEventListener('seeked',sync);
  video.addEventListener('error',()=>{$('walk-description').textContent='영상을 불러오지 못했습니다. 네트워크를 확인하거나 GitHub의 영상 파일을 내려받아 주세요.';});
  $('walk-length').textContent=`${results.length_m.toFixed(1)} m`;
  choose('normal');return {pause:()=>video.pause()};
}
