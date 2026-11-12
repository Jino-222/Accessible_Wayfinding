"""Vision-environment tests for image-only guidance boundaries and transitions."""
import base64
import numpy as np
import cv2
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from research.gangnam_walk_service import WalkGuidance, ImageFrame
import research.gangnam_walk_service as service

def estimate(x=0,z=0,ok=True):
    pose=np.eye(4);pose[:3,3]=[x,1.2,z]
    return dict(success=ok,accepted=ok,pose=pose.tolist() if ok else None,inliers=30 if ok else 0,
                reprojection_px=.5 if ok else None,elapsed_ms=2,reason='test_pose')

def guidance():return WalkGuidance([[0,0,0],[0,0,10],[0,0,22]])

def test_needs_three_independent_observations_and_recovers():
    g=guidance()
    assert [g.observe(estimate(),t,1.2)['state'] for t in [0,.5,1]]==['confirming','confirming','guiding']
    assert not g.observe(estimate(ok=False),1.5,1.2)['arrow_visible']
    assert [g.observe(estimate(),t,1.2)['state'] for t in [2,2.5,3]]==['confirming','confirming','guiding']

@pytest.mark.parametrize('x,z',[(2,0),(0,30)])
def test_outside_corridor_is_rejected(x,z):
    assert guidance().observe(estimate(x,z),0,1.2)['state']=='position_uncertain'

def test_wrong_height_and_jump_do_not_guide():
    g=guidance();e=estimate();e['pose'][1][3]=5.7
    assert not g.observe(e,0,1.2)['arrow_visible']
    for t in [1,1.5,2]:g.observe(estimate(),t,1.2)
    assert g.observe(estimate(z=12),2.5,1.2)['reason']=='inconsistent_position'

def test_closed_route_stops_immediately_and_reopening_reconfirms():
    g=guidance()
    for t in [0,.5,1]:g.observe(estimate(),t,1.2)
    g.closed=True
    result=g.observe(estimate(),1.5,1.2)
    assert result['state']=='blocked' and not result['arrow_visible']
    g.closed=False
    assert g.observe(estimate(),2,1.2)['state']=='confirming'

def test_arrival_requires_confirmed_nearby_image_positions():
    g=guidance()
    for t in [0,.5]:assert g.observe(estimate(z=21.5),t,1.2)['state']=='confirming'
    result=g.observe(estimate(z=21.5),1,1.2)
    assert result['state']=='arrived' and not result['arrow_visible']

def image_body():
    ok,png=cv2.imencode('.png',np.zeros((32,32),np.uint8));assert ok
    return dict(frame=0,time_s=0,image=base64.b64encode(png).decode(),width=32,height=32,fx=25,fy=25,cx=15.5,cy=15.5,camera_height=1.2)

@pytest.mark.parametrize('extra',['pose','reference_pose','position','floor'])
def test_query_cannot_supply_truth(extra):
    with pytest.raises(ValidationError):ImageFrame(**(image_body()|{extra:[0,0,0]}))

def test_http_rejects_duplicate_and_calibration_mismatch(monkeypatch,tmp_path):
    class Stub:
        def estimate(self,query):return estimate()
    monkeypatch.setattr(service,'algorithm',Stub())
    service.sessions['test']=dict(g=guidance(),frame=-1,time=-1.,use=0,out=tmp_path/'predictions.jsonl')
    with TestClient(service.app) as client:
        body=image_body()
        assert client.post('/sessions/test/frame',json=body).status_code==200
        assert client.post('/sessions/test/frame',json=body).status_code==409
        assert client.post('/sessions/test/frame',json=body|dict(frame=1,time_s=1,width=64)).status_code==422
        assert client.post('/sessions/test/frame',json=body|dict(frame=1,time_s=1,pose=[0,0,0])).status_code==422
    service.sessions.pop('test',None)
