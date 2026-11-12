"""Validate B2 registered RGB/depth pairs before metric unprojection."""
from collections import defaultdict
import numpy as np
from .gangnam import DATA,rows,metadata,poses
from .geometry import kapture_to_camera_world
from .paths import ROOT,write_json


def mapping_views(frame_stride=4):
    base=DATA/'mapping/sensors'
    cameras=metadata('mapping');reference=poses('mapping')
    depths={}
    for row in rows(base/'sensors.txt'):
        if row[2]!='depth':continue
        values=list(map(float,row[4:]))
        depths[row[0]]=dict(model=row[3],width=int(values[0]),height=int(values[1]),params=values[2:])
    records={(int(r[0]),r[1]):r[2] for r in rows(base/'records_depth.txt')}
    rig_members={r[1]:(r[0],kapture_to_camera_world(list(map(float,r[2:6])),list(map(float,r[6:9])))) for r in rows(base/'rigs.txt')}
    groups=defaultdict(list)
    for camera in cameras:groups[camera['camera_id']].append(camera)
    selected=[];counts={}
    for camera_id,group in sorted(groups.items()):
        chosen=sorted(group,key=lambda c:c['timestamp'])[::frame_stride]
        counts[camera_id]=dict(available=len(group),selected=len(chosen))
        depth_id=camera_id+'_depth'
        if depth_id not in depths:raise ValueError('Missing paired depth calibration')
        rgb_rig,rgb_pose=rig_members[camera_id];depth_rig,depth_pose=rig_members[depth_id]
        if rgb_rig!=depth_rig or not np.allclose(rgb_pose,depth_pose,atol=1e-8):
            raise ValueError('RGB and depth optical frames differ; explicit reprojection required')
        depth_camera=depths[depth_id]
        for view in chosen:
            depth_path=base/'records_data'/records[(view['timestamp'],depth_id)]
            shape=(depth_camera['height'],depth_camera['width'])
            if depth_path.stat().st_size!=np.prod(shape)*4:raise ValueError('Depth length/calibration mismatch')
            selected.append(view|dict(pose=reference[view['id']],depth_path=str(depth_path),depth_shape=shape,depth_camera=depth_camera))
    write_json(ROOT/'docs/evidence/ar-map-inputs.json',dict(available_images=len(cameras),selected_images=len(selected),
        selection='Every fourth timestamp independently in each camera/sequence; all 12 sensors retained',
        frame_stride=frame_stride,sensors=counts,depth_registration='Verified common rig and equal extrinsics',
        depth_intrinsics='Use separately supplied 864x682 depth calibration, not naive RGB height divided by 3',
        truth_use='Mapping poses only; validation/evaluation ground truth not read'))
    return selected
