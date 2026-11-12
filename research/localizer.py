"""Small SIFT + registered RGB-D map + PnP baseline. No query truth inputs.

This is a project baseline, not a reproduction of the published NAVER results.
OpenCV feature detection/RANSAC are deterministic given a fixed thread count,
seed, library version and input files; real wall time remains hardware dependent.
"""
from pathlib import Path
import time
import cv2
import numpy as np
from .geometry import invert_pose

MAX_SIDE=960
FEATURES=2200


def load_features(path,camera,root_sift=False):
    from .gangnam import intrinsics
    image=(path.copy() if isinstance(path,np.ndarray) else
           cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_GRAYSCALE))
    if image is not None and image.ndim==3:image=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    if image is None:raise ValueError('Image could not be decoded')
    if image.shape!=(camera['height'],camera['width']):raise ValueError('Camera/image dimension mismatch')
    scale=min(1.,MAX_SIDE/max(image.shape))
    if scale!=1.:image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    keypoints,descriptors=cv2.SIFT_create(nfeatures=FEATURES).detectAndCompute(image,None)
    xy=np.array([k.pt for k in keypoints],dtype=np.float32).reshape(-1,2)
    if descriptors is None:descriptors=np.empty((0,128),np.float32)
    if root_sift:descriptors=normalize_root(descriptors)
    k,dist=intrinsics(camera,scale)
    return xy,descriptors,k,dist,scale


def normalize_root(descriptors):
    return np.sqrt(descriptors/np.maximum(descriptors.sum(axis=1,keepdims=True),1e-12)).astype(np.float32)


def points_from_depth(xy,depth,camera,pose,feature_scale=1.,depth_camera=None):
    """Depth must share the RGB optical frame; independently sized registered map.

    Sample only valid nearest depth pixels, never interpolate across missing data.
    Depth is Z distance in metres, not radial range. Require caller to validate the
    supplied depth sensor's extrinsics and field of view before this function.
    """
    from .gangnam import intrinsics
    rgb=np.asarray(xy,dtype=np.float64)/feature_scale
    k,dist=intrinsics(camera)
    rays=cv2.undistortPoints(rgb.reshape(-1,1,2),k,dist).reshape(-1,2)
    if depth_camera is None:
        # Same distorted image grid, at a potentially different resolution.
        pixels=rgb*np.array([depth.shape[1]/camera['width'],depth.shape[0]/camera['height']])
    else:
        dk,dd=intrinsics(depth_camera)
        pixels=cv2.projectPoints(np.c_[rays,np.ones(len(rays))],np.zeros(3),np.zeros(3),dk,dd)[0].reshape(-1,2)
    ij=np.rint(pixels).astype(int)
    inside=(ij[:,0]>=0)&(ij[:,0]<depth.shape[1])&(ij[:,1]>=0)&(ij[:,1]<depth.shape[0])
    z=np.zeros(len(xy));z[inside]=depth[ij[inside,1],ij[inside,0]]
    valid=inside&np.isfinite(z)&(z>.1)&(z<80)
    xyz=np.c_[rays*z[:,None],z]
    world=xyz@pose[:3,:3].T+pose[:3,3]
    return world,valid


class Localizer:
    def __init__(self,map_file,root_sift=False):
        cv2.setNumThreads(2);cv2.setRNGSeed(23)
        archive=np.load(map_file)
        self.xyz=archive['xyz'].astype(np.float64)
        self.descriptors=archive['descriptors'].astype(np.float32)
        if root_sift:self.descriptors=normalize_root(self.descriptors)
        self.root_sift=root_sift
        self.index=cv2.FlannBasedMatcher(dict(algorithm=1,trees=4),dict(checks=96))
        self.index.add([self.descriptors]);self.index.train()

    def estimate(self,query):
        started=time.perf_counter()
        output=dict(id=query['id'],method='rootsift_pnp' if self.root_sift else 'sift_pnp',
                    success=False,accepted=False,pose=None,inliers=0,reprojection_px=None)
        try:
            xy,desc,k,dist,_=load_features(query['path'],query['camera'],self.root_sift)
            output['query_features']=len(xy)
            if len(desc)<8:output['reason']='insufficient_features';return output
            matches=self.index.knnMatch(desc,k=2)
            selected=[pair[0] for pair in matches if len(pair)==2 and pair[0].distance<.80*pair[1].distance]
            # Each query keypoint and map descriptor used at most once.
            used=set();unique=[]
            for match in sorted(selected,key=lambda m:m.distance):
                if match.trainIdx in used:continue
                used.add(match.trainIdx);unique.append(match)
            output['matches']=len(unique)
            if len(unique)<8:output['reason']='insufficient_correspondences';return output
            image_points=np.array([xy[m.queryIdx] for m in unique],np.float64)
            world=self.xyz[[m.trainIdx for m in unique]]
            cv2.setRNGSeed(23)
            ok,rvec,tvec,inliers=cv2.solvePnPRansac(world,image_points,k,dist,
                iterationsCount=3000,reprojectionError=4.,confidence=.999,flags=cv2.SOLVEPNP_EPNP)
            if not ok or inliers is None or len(inliers)<6:
                output['reason']='pnp_failed';return output
            indices=inliers.ravel()
            rvec,tvec=cv2.solvePnPRefineLM(world[indices],image_points[indices],k,dist,rvec,tvec)
            projected=cv2.projectPoints(world[indices],rvec,tvec,k,dist)[0].reshape(-1,2)
            error=float(np.median(np.linalg.norm(projected-image_points[indices],axis=1)))
            camera_from_world=np.eye(4);camera_from_world[:3,:3]=cv2.Rodrigues(rvec)[0];camera_from_world[:3,3]=tvec.ravel()
            pose=invert_pose(camera_from_world)
            front=(world[indices]@camera_from_world[:3,:3].T+camera_from_world[:3,3])[:,2]>0
            output.update(success=True,pose=pose.tolist(),inliers=len(indices),reprojection_px=error,
                accepted=len(indices)>=12 and error<=4 and bool(front.all()),
                reason='pose_estimated')
            if not output['accepted']:output['reason']='pose_rejected_by_quality'
        except (ValueError,cv2.error,OSError) as exc:
            output['reason']='processing_error';output['error']=str(exc)
        finally:output['elapsed_ms']=(time.perf_counter()-started)*1000
        return output
