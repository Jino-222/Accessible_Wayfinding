"""Image-only localization bridge for a synthetic Gangnam-derived approach."""
import base64, json, math, threading, time
from uuid import uuid4
import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from .paths import ASSETS
from .localizer import Localizer

BASE=ASSETS/'gangnam-walk'
app=FastAPI(title='Gangnam synthetic walk image bridge')
sessions={}; lock=threading.Lock(); algorithm=None

class ImageFrame(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    frame:int=Field(ge=0)
    time_s:float=Field(ge=0)
    image:str=Field(max_length=3000000)
    width:int=Field(ge=16,le=1280)
    height:int=Field(ge=16,le=1280)
    fx:float=Field(gt=0);fy:float=Field(gt=0);cx:float;cy:float
    camera_height:float=Field(ge=.8,le=2.)
    action:Literal['observe','board','exit']='observe'
    resuming:bool=False

class Start(BaseModel):
    model_config=ConfigDict(extra='forbid')
    label:str=Field(pattern=r'^[a-z0-9_-]{1,48}$')
    closed:bool=False

class Closure(BaseModel):
    model_config=ConfigDict(extra='forbid')
    closed:bool

class WalkGuidance:
    def __init__(self,path,closed=False):
        self.path=np.asarray(path,float);self.closed=closed;self.count=0;self.last=None;self.last_time=None
        self.lengths=np.linalg.norm(np.diff(self.path[:,[0,2]],axis=0),axis=1)
        self.cumulative=np.r_[0.,self.lengths.cumsum()]
    def observe(self,estimate,t,height):
        pose=np.asarray(estimate['pose']) if estimate.get('success') else None
        position=pose[:3,3] if pose is not None else None
        result=dict(state='locating',reason='image_not_accepted',arrow_visible=False,target=[0.,0.,0.],remaining_m=None,recovery_count=0)
        if self.closed:
            self.count=0;self.last=None;return result|dict(state='blocked',reason='elevator_access_closed')
        valid=bool(estimate.get('accepted'))
        if valid:
            candidates=[]
            for i,(a,b) in enumerate(zip(self.path[:-1],self.path[1:])):
                av=a[[0,2]];bv=b[[0,2]];point=position[[0,2]]
                f=np.clip(np.dot(point-av,bv-av)/np.dot(bv-av,bv-av),0,1)
                candidates.append((float(np.linalg.norm(point-(av+f*(bv-av)))),i,float(f)))
            offset,i,f=min(candidates);progress=float(self.cumulative[i]+self.lengths[i]*f)
            valid=offset<=1.0 and abs(position[1]-height)<=.4
            if not valid:result['reason']='outside_registered_corridor'
            if valid and self.last is not None:
                valid=np.linalg.norm(position-self.last)<=max(.75,(t-self.last_time)*1.5)
                if not valid:result['reason']='inconsistent_position'
        if not valid:
            self.count=0;self.last=None;return result|dict(state='position_uncertain')
        self.last=position.copy();self.last_time=t;self.count+=1
        result.update(recovery_count=self.count,remaining_m=max(0.,float(self.cumulative[-1]-progress)))
        if self.count<3:return result|dict(state='confirming',reason='three_consistent_images_required')
        if result['remaining_m']<=.8 and np.linalg.norm(position[[0,2]]-self.path[-1,[0,2]])<=.9:
            return result|dict(state='arrived',reason='synthetic_approach_reached')
        d=min(progress+2.5,self.cumulative[-1]);target=[float(np.interp(d,self.cumulative,self.path[:,k])) for k in range(3)]
        return result|dict(state='guiding',reason='accepted_image_pose',arrow_visible=True,target=target)

def local(request):
    if request.client and request.client.host not in ('127.0.0.1','::1','testclient'):raise HTTPException(403,'Loopback only')

@app.get('/health')
def health():return dict(service='gangnam-walk',ready=(BASE/'map/map.npz').exists(),pose_input_allowed=False)

@app.post('/sessions')
def start(body:Start,request:Request):
    local(request)
    global algorithm
    with lock:
        if algorithm is None:algorithm=Localizer(BASE/'map/map.npz',True)
        for key in list(sessions):
            if time.monotonic()-sessions[key]['use']>3600:del sessions[key]
        if len(sessions)>=32:raise HTTPException(429,'Too many sessions')
        path=[r['position'] for r in json.loads((BASE/'scene.json').read_text('utf-8'))['path']]
        sid=uuid4().hex;out=BASE/'predictions'/f'{body.label}-{sid}.jsonl';out.parent.mkdir(exist_ok=True,parents=True)
        sessions[sid]=dict(g=WalkGuidance(path,body.closed),frame=-1,time=-1.,use=time.monotonic(),out=out)
        return dict(session=sid,prediction_file=out.name)

@app.post('/sessions/{sid}/closure')
def closure(sid:str,body:Closure,request:Request):
    local(request)
    with lock:
        if sid not in sessions:raise HTTPException(404,'Unknown session')
        g=sessions[sid]['g'];g.closed=body.closed;g.count=0;g.last=None
    return dict(closed=body.closed)

@app.post('/sessions/{sid}/frame')
def frame(sid:str,body:ImageFrame,request:Request):
    local(request)
    with lock:
        entry=sessions.get(sid)
        if entry is None:raise HTTPException(404,'Unknown session')
        if body.frame<=entry['frame'] or body.time_s<=entry['time']:raise HTTPException(409,'Old or duplicate observation')
        try:raw=base64.b64decode(body.image,validate=True)
        except Exception:raise HTTPException(422,'Invalid image encoding')
        im=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_GRAYSCALE)
        if im is None or im.shape!=(body.height,body.width):raise HTTPException(422,'Image calibration mismatch')
        camera=dict(model='PINHOLE',width=body.width,height=body.height,params=[body.fx,body.fy,body.cx,body.cy])
        estimate=algorithm.estimate(dict(id=str(body.frame),path=im,camera=camera))
        if body.resuming:entry['g'].count=0;entry['g'].last=None
        guided=entry['g'].observe(estimate,body.time_s,body.camera_height)
        result=dict(frame=body.frame,time_s=body.time_s)|estimate|guided
        result['pose']=np.asarray(estimate['pose']).ravel().tolist() if estimate['success'] else []
        result['position']=estimate['pose'] and np.asarray(estimate['pose'])[:3,3].tolist() or []
        result['localization_reason']=estimate['reason'];result['pose_source']='synthetic RGB / RootSIFT + PnP'
        entry.update(frame=body.frame,time=body.time_s,use=time.monotonic())
        with entry['out'].open('a',encoding='utf-8') as f:f.write(json.dumps(result,allow_nan=False)+'\n')
        return result

@app.delete('/sessions/{sid}')
def close(sid:str,request:Request):
    local(request)
    with lock:sessions.pop(sid,None)
    return dict(closed=True)
