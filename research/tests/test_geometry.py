import numpy as np
from research.geometry import unity_to_camera_world


def test_unity_reflects_world_and_camera_axes_without_reflecting_pose():
    source=np.eye(4);source[:3,3]=[2,3,5]
    pose=unity_to_camera_world(source)
    np.testing.assert_allclose(pose[:3,3],[2,3,-5])
    np.testing.assert_allclose(pose[:3,:3],np.diag([1,-1,-1]))
    assert np.isclose(np.linalg.det(pose[:3,:3]),1)
import pytest
from scipy.spatial.transform import Rotation
from research.geometry import kapture_to_camera_world,invert_pose,project_points,pose_error,rigid


def test_translation_is_not_camera_center():
    camera=kapture_to_camera_world([1,0,0,0],[-2,-3,-4])
    np.testing.assert_allclose(camera[:3,3],[2,3,4])


def test_rotation_inverse_and_rig_composition():
    rig=np.eye(4);rig[:3,3]=[2,0,0]
    camera=kapture_to_camera_world([2**-0.5,0,0,2**-0.5],[0,1,0],rig)
    np.testing.assert_allclose(camera[:3,3],[-3,0,0],atol=1e-8)
    np.testing.assert_allclose(invert_pose(camera)@camera,np.eye(4),atol=1e-8)


def test_projection_direction_and_behind_camera():
    k=np.array([[100,0,320],[0,100,240],[0,0,1]])
    pixels,valid=project_points([[0,0,2],[1,1,2],[0,0,-2]],np.eye(4),k)
    np.testing.assert_allclose(pixels[:2],[[320,240],[370,290]])
    assert valid.tolist()==[True,True,False]
    assert np.isnan(pixels[2]).all()


def test_error_uses_position_and_rotation_not_euler_component_difference():
    estimate=np.eye(4);estimate[:3,3]=[3,4,0]
    estimate[:3,:3]=Rotation.from_euler('y',30,degrees=True).as_matrix()
    distance,angle=pose_error(estimate,np.eye(4))
    assert distance==pytest.approx(5)
    assert angle==pytest.approx(30)


@pytest.mark.parametrize('bad',[np.zeros((4,4)),np.diag([-1,1,1,1]),np.full((4,4),np.nan)])
def test_malformed_transforms_fail(bad):
    with pytest.raises(ValueError):rigid(bad)
