"""Map construction from registered mapping RGB/depth only."""
import argparse
import json
from pathlib import Path
import time
import cv2
import numpy as np
from .paths import ROOT,ASSETS,write_json
from .localizer import load_features,points_from_depth


def synthetic_views(software=False):
    base=ASSETS/('synthetic/software-rendered' if software else 'synthetic/rendered')
    manifest=json.loads((base/'capture-manifest.json').read_text('utf-8'))
    mapping=[];queries=[];truth={}
    for record in manifest['records']:
        camera=dict(model='PINHOLE',width=record['width'],height=record['height'],params=[record[k] for k in ('fx','fy','cx','cy')])
        item=dict(id=record['id'],path=str(base/record['image']),camera=camera)
        pose=np.array(record['camera_to_world']).reshape(4,4)
        if record['split']=='mapping':
            mapping.append(item|dict(pose=pose,depth_path=str(base/record['depth']),depth_shape=(record['height'],record['width'])))
        else:
            queries.append(item);truth[record['id']]=pose.tolist()
    write_json(base/'query-inputs.json',queries)
    write_json(ASSETS/('evaluation_only/software-truth.json' if software else 'evaluation_only/synthetic-truth.json'),truth)
    return mapping


def build(views,out,stride=1):
    cv2.setNumThreads(2);cv2.setRNGSeed(23)
    started=time.perf_counter();descriptors=[];points=[];image_ids=[];stats=[]
    views=views[::stride]
    for index,view in enumerate(views):
        xy,desc,k,dist,scale=load_features(view['path'],view['camera'])
        depth=np.fromfile(view['depth_path'],dtype='<f4').reshape(view['depth_shape'])
        xyz,valid=points_from_depth(xy,depth,view['camera'],np.array(view['pose']),scale,view.get('depth_camera'))
        descriptors.append(desc[valid]);points.append(xyz[valid]);image_ids.extend([index]*int(valid.sum()))
        stats.append(dict(id=view['id'],features=len(xy),depth_features=int(valid.sum())))
        if index%20==0:print(json.dumps(dict(stage='map_features',done=index+1,total=len(views),depth_features=int(valid.sum()))),flush=True)
    desc=np.concatenate(descriptors);xyz=np.concatenate(points)
    if len(xyz)<20:raise ValueError('Insufficient registered depth features; inspect camera/depth registration')
    out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'map.npz',xyz=xyz,descriptors=desc,image_ids=np.array(image_ids))
    write_json(out/'map-report.json',dict(images=len(views),features=len(xyz),stride=stride,
        method='SIFT with nearest valid registered depth; no depth filling',build_seconds=time.perf_counter()-started,
        max_image_side=960,stats=stats))
    print(json.dumps(dict(map=str(out/'map.npz'),images=len(views),features=len(xyz))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--study',choices=['gangnam','synthetic','synthetic-software'],required=True)
    parser.add_argument('--stride',type=int,default=1);args=parser.parse_args()
    if args.study.startswith('synthetic'):
        software=args.study=='synthetic-software'
        views=synthetic_views(software);out=ASSETS/('synthetic/software-map' if software else 'synthetic/map')
    else:
        from .gangnam_mapping import mapping_views
        views=mapping_views();out=ASSETS/'gangnam-map'
    build(views,out,args.stride)
