// Interaction experiment: poses are synthetic observations, never image estimates.
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
export const wrapAngle=a=>Math.atan2(Math.sin(a),Math.cos(a));

export function projectPath(path,pose){
  let best=null,along=0;
  for(let i=0;i<path.length-1;i++){
    const a=path[i],b=path[i+1],dx=b.x-a.x,dz=b.z-a.z,len=Math.hypot(dx,dz);
    if(!len)continue;
    const t=clamp(((pose.x-a.x)*dx+(pose.z-a.z)*dz)/(len*len),0,1);
    const point={x:a.x+dx*t,z:a.z+dz*t},offset=distance(pose,point);
    if(!best||offset<best.offset)best={point,offset,progress:along+len*t};
    along+=len;
  }
  if(!best)throw Error('A non-empty path is required');
  return {...best,length:along};
}
export function pointAt(path,metres){
  let left=Math.max(0,metres);
  for(let i=1;i<path.length;i++){
    const a=path[i-1],b=path[i],length=distance(a,b);
    if(length&&left<=length){const f=left/length;return {x:a.x+(b.x-a.x)*f,z:a.z+(b.z-a.z)*f};}
    left-=length;
  }
  return {...path.at(-1)};
}

export class Explorer{
  constructor(scene){
    if(!scene?.path?.length||scene.path.length<2||!Number.isFinite(scene.halfWidth))throw Error('Invalid scene');
    this.scene=scene;this.path=scene.path;this.length=projectPath(this.path,this.path[0]).length;this.reset();
  }
  reset(){
    this.pose={...this.path[0],yaw:0};this.running=false;this.started=false;
    this.masked=false;this.closed=false;this.time=0;this.travelled=0;
    this.count=0;this.sampleId=0;this.lastId=-1;this.lastTime=-Infinity;this.observation=null;
    this.sampleClock=0;this.events=[];this.status='ready';this.note('출발 지점 준비');
  }
  note(message){this.events.push({time_s:Number(this.time.toFixed(2)),message});if(this.events.length>100)this.events.shift();}
  reconfirm(){this.count=0;this.observation=null;this.sampleClock=0;}
  start(){this.started=true;this.running=true;this.reconfirm();this.note('직접 이동 시작');this.refresh();}
  pause(){if(!this.running)return;this.running=false;this.reconfirm();this.note('이동 일시정지');this.refresh();}
  setMasked(value){
    if(this.masked===value)return;this.masked=value;this.reconfirm();
    this.note(value?'위치 관측 끊김 주입':'위치 관측 재개');this.refresh();
  }
  setClosed(value){
    if(this.closed===value)return;this.closed=value;this.reconfirm();
    this.note(value?'엘리베이터 접근 중단':'접근 재개 · 위치 재확인');this.refresh();
  }
  move(forward=0,side=0,turn=0){
    if(!this.running||![forward,side,turn].every(Number.isFinite))return;
    this.pose.yaw=wrapAngle(this.pose.yaw+turn);
    const old={...this.pose},s=Math.sin(this.pose.yaw),c=Math.cos(this.pose.yaw),w=this.scene.halfWidth-.65;
    this.pose.x=clamp(this.pose.x+s*forward+c*side,-w,w);
    this.pose.z=clamp(this.pose.z+c*forward-s*side,-1.1,this.length+.35);
    this.travelled+=distance(old,this.pose);
    // Arrival/remaining distance only change on a new observation, not on movement truth.
    this.refresh();
  }
  observe(observation){
    if(!this.running||this.masked||!observation||observation.id<=this.lastId||observation.time<=this.lastTime)return false;
    const {x,z,yaw}=observation.pose||{};
    if(![x,z,yaw,observation.time].every(Number.isFinite)||observation.time>this.time+1e-6||this.time-observation.time>.8)return false;
    this.lastId=observation.id;this.lastTime=observation.time;
    this.observation={x,z,yaw};this.count=Math.min(3,this.count+1);this.refresh();return true;
  }
  tick(delta,controls={}){
    if(!this.running)return;
    const dt=clamp(Number.isFinite(delta)?delta:0,0,.08);this.time+=dt;
    const forward=clamp(controls.forward||0,-1,1),side=clamp(controls.side||0,-1,1);
    const norm=Math.max(1,Math.hypot(forward,side));
    this.move(forward/norm*1.65*dt,side/norm*1.65*dt,clamp(controls.turn||0,-1,1)*1.15*dt);
    this.sampleClock+=dt;
    if(this.sampleClock>=.45){
      this.sampleClock%=.45;
      if(!this.masked)this.observe({id:++this.sampleId,time:this.time,pose:{...this.pose},source:'synthetic-camera-pose'});
    }
    this.refresh();
  }
  refresh(){
    const previous=this.status;
    this.status=!this.started?'ready':!this.running?'paused':this.closed?'blocked':this.masked?'lost':this.count<3?'confirming':distance(this.observation,this.path.at(-1))<=.85?'arrived':'guiding';
    if(previous!==this.status){
      const labels={confirming:'위치 재확인',guiding:'안내 시작',lost:'안내 숨김',blocked:'접근 안내 중단',arrived:'가상 엘리베이터 앞 도착'};
      if(labels[this.status])this.note(labels[this.status]);
    }
  }
  view(){
    const localized=this.running&&!this.masked&&this.count===3&&this.observation;
    const p=localized?projectPath(this.path,this.observation):null;
    const target=p?pointAt(this.path,Math.min(p.length,p.progress+2.8)):null;
    const direction=target?wrapAngle(Math.atan2(target.x-this.observation.x,target.z-this.observation.z)-this.observation.yaw):null;
    return {status:this.status,confirmations:this.count,arrowVisible:this.status==='guiding',
      remaining:this.status==='arrived'?0:this.status==='guiding'?Math.max(p.length-p.progress,distance(this.observation,this.path.at(-1))):null,
      observation:localized?{...this.observation}:null,target,direction,progress:p?.progress??null,
      running:this.running,started:this.started,masked:this.masked,closed:this.closed};
  }
  report(){return {kind:'browser-interaction-experiment',tracking:'synthetic pose observations; not image localization',
    sceneVersion:this.scene.version,referenceLength_m:this.length,elapsedSimulation_s:Number(this.time.toFixed(2)),
    travelledSimulation_m:Number(this.travelled.toFixed(2)),finalState:this.status,events:this.events.map(e=>({...e}))};}
}
