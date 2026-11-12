"""Explicit camera conventions for recorded images and synthetic metric worlds.

Internal pose: camera-to-world, camera axes +x right, +y down, +z forward.
Synthetic world: right-handed, +x right, +y up, +z backward, metres. Unity's
left-handed world needs an explicit z reflection at its rendering boundary;
never copy Unity quaternions directly into an internal pose.
Kapture/COLMAP inputs are world-to-camera; convert once at the boundary.
"""
import numpy as np
from scipy.spatial.transform import Rotation


def rigid(matrix):
    value=np.asarray(matrix,dtype=float)
    if value.shape!=(4,4) or not np.isfinite(value).all():
        raise ValueError('Pose must be a finite 4x4 matrix')
    if not np.allclose(value[3],[0,0,0,1],atol=1e-8):raise ValueError('Invalid homogeneous row')
    if not np.allclose(value[:3,:3].T@value[:3,:3],np.eye(3),atol=1e-6):raise ValueError('Non-orthogonal rotation')
    # Coordinate convention changes can have determinant -1. A pose itself must not.
    if not np.isclose(np.linalg.det(value[:3,:3]),1,atol=1e-6):raise ValueError('Pose has reflected axes')
    return value


def invert_pose(matrix):
    matrix=rigid(matrix)
    result=np.eye(4)
    result[:3,:3]=matrix[:3,:3].T
    result[:3,3]=-result[:3,:3]@matrix[:3,3]
    return result


def kapture_to_camera_world(qwxyz,translation,rig_from_world=None):
    q=np.asarray(qwxyz,dtype=float)
    t=np.asarray(translation,dtype=float)
    if q.shape!=(4,) or not np.isfinite(q).all() or np.linalg.norm(q)<1e-12:
        raise ValueError('Invalid quaternion')
    if t.shape!=(3,) or not np.isfinite(t).all():raise ValueError('Invalid translation')
    camera_from_parent=np.eye(4)
    camera_from_parent[:3,:3]=Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
    camera_from_parent[:3,3]=t
    camera_from_world=camera_from_parent if rig_from_world is None else camera_from_parent@rigid(rig_from_world)
    return invert_pose(camera_from_world)


def project_points(points,camera_to_world,intrinsics):
    points=np.asarray(points,dtype=float).reshape(-1,3)
    k=np.asarray(intrinsics,dtype=float)
    if k.shape!=(3,3) or not np.isfinite(k).all() or k[0,0]<=0 or k[1,1]<=0:
        raise ValueError('Invalid intrinsic matrix')
    if not np.isfinite(points).all():raise ValueError('Invalid world points')
    inverse=invert_pose(camera_to_world)
    xyz=points@inverse[:3,:3].T+inverse[:3,3]
    visible=xyz[:,2]>1e-6
    pixels=np.full((len(points),2),np.nan)
    homogeneous=xyz[visible]@k.T
    pixels[visible]=homogeneous[:,:2]/homogeneous[:,2:3]
    return pixels,visible


def pose_error(estimate,reference):
    estimate=rigid(estimate);reference=rigid(reference)
    translation=float(np.linalg.norm(estimate[:3,3]-reference[:3,3]))
    relative=estimate[:3,:3].T@reference[:3,:3]
    rotation=float(np.degrees(np.arccos(np.clip((np.trace(relative)-1)/2,-1,1))))
    return translation,rotation


def rebase_pose(camera_to_world,new_from_old):
    """Apply a fixed proper metric transform, fitted without evaluation poses."""
    return rigid(new_from_old)@rigid(camera_to_world)


def unity_to_camera_world(unity_local_to_world):
    """Reflect both world and camera conventions; result is a proper rotation."""
    source=rigid(unity_local_to_world)
    return rigid(np.diag([1,1,-1,1])@source@np.diag([1,-1,1,1]))
