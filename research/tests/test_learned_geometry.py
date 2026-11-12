import cv2
import numpy as np
from research.learned_matching import estimate_pose,select_candidate


def test_known_nonplanar_correspondences_recover_camera_world_position():
    rng=np.random.default_rng(64)
    center=np.array([3.,-2.,1.])
    local=rng.uniform([-2,-1,5],[2,1,10],(40,3))
    world=local+center
    k=np.array([[500.,0,320],[0,500.,240],[0,0,1.]])
    pixels=cv2.projectPoints(world,np.zeros(3),-center,k,None)[0].reshape(-1,2)
    result=estimate_pose(world,pixels,k,None)
    assert result['accepted'] and result['inliers']==40
    assert np.allclose(np.array(result['pose'])[:3,3],center,atol=1e-5)


def test_candidate_ranking_does_not_consult_reference_errors():
    a=dict(accepted=True,success=True,inliers=20,reprojection_px=1,position_error_m=100)
    b=dict(accepted=True,success=True,inliers=12,reprojection_px=.5,position_error_m=0)
    assert select_candidate([a,b]) is a
    a['position_error_m']=0;b['position_error_m']=100
    assert select_candidate([a,b]) is a


def test_insufficient_geometry_is_a_recorded_failure():
    result=estimate_pose(np.zeros((7,3)),np.zeros((7,2)),np.eye(3),None)
    assert not result['success'] and result['pose'] is None
