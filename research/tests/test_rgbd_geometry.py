import numpy as np
import cv2
from research.localizer import points_from_depth
from research.geometry import project_points


def test_scaled_image_and_registered_depth_reconstruct_known_world_points():
    camera=dict(model='PINHOLE',width=640,height=480,params=[400,400,320,240])
    depth=np.full((240,320),5.,np.float32)
    pose=np.eye(4);pose[:3,3]=[8,2,4]
    xy=np.array([[160,120],[200,120],[160,80]],np.float32)
    world,valid=points_from_depth(xy,depth,camera,pose,.5)
    assert valid.all()
    np.testing.assert_allclose(world,[[8,2,9],[9,2,9],[8,1,9]])
    pixels,_=project_points(world,pose,np.array([[400,0,320],[0,400,240],[0,0,1.]]))
    np.testing.assert_allclose(pixels,xy*2)


def test_missing_depth_is_not_filled_with_invented_geometry():
    camera=dict(model='PINHOLE',width=4,height=4,params=[2,2,2,2])
    depth=np.zeros((4,4),np.float32)
    _,valid=points_from_depth(np.array([[2,2],[1,1]]),depth,camera,np.eye(4))
    assert not valid.any()
