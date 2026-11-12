"""Read public kapture metadata; query bundles deliberately contain no poses."""
import csv
import hashlib
from pathlib import Path
import numpy as np
from .geometry import kapture_to_camera_world
from .paths import ASSETS, ROOT, write_json

DATA = ASSETS/'gangnam_b2/GangnamStation/B2/release'


def rows(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        yield from csv.reader((line for line in stream if line.strip() and not line.startswith('#')),skipinitialspace=True)


def metadata(part):
    base=DATA/part/'sensors'
    cameras={}
    for row in rows(base/'sensors.txt'):
        if row[2]!='camera':continue
        model=row[3];values=list(map(float,row[4:]))
        if model not in ('OPENCV','PINHOLE','SIMPLE_PINHOLE'):
            raise ValueError(f'Unsupported camera model: {model}')
        cameras[row[0]]=dict(model=model,width=int(values[0]),height=int(values[1]),params=values[2:])
    images=[]
    seen=set()
    for timestamp,camera,path in rows(base/'records_camera.txt'):
        if path in seen:raise ValueError('Duplicate image path')
        resolved=(base/'records_data'/path).resolve()
        if not resolved.is_relative_to((base/'records_data').resolve()):raise ValueError('Unsafe record path')
        if camera not in cameras:raise ValueError('Unregistered camera')
        if not resolved.is_file():raise FileNotFoundError(resolved)
        seen.add(path)
        images.append(dict(id=path,timestamp=int(timestamp),camera_id=camera,
            sequence=path.split('/')[0],path=str(resolved),camera=cameras[camera]))
    return images


def poses(part):
    """Ground truth is loaded only by mapping construction or evaluation."""
    base=DATA/part/'sensors'
    direct={(int(r[0]),r[1]):kapture_to_camera_world(list(map(float,r[2:6])),list(map(float,r[6:9])))
        for r in rows(base/'trajectories.txt')}
    # Current B2 release has camera poses, not unresolved rig trajectories.
    # Fail loudly for a changed distribution rather than treating rig pose as camera pose.
    result={}
    for record in metadata(part):
        key=(record['timestamp'],record['camera_id'])
        if key not in direct:raise ValueError('Unresolved rig pose: explicit rig composition required')
        result[record['id']]=direct[key]
    return result


def intrinsics(camera,scale=1.0):
    p=camera['params']
    if camera['model']=='SIMPLE_PINHOLE':fx,fy,cx,cy=p[0],p[0],p[1],p[2];dist=np.zeros(4)
    else:fx,fy,cx,cy=p[:4];dist=np.array(p[4:8] if camera['model']=='OPENCV' else [0]*4)
    return np.array([[fx*scale,0,cx*scale],[0,fy*scale,cy*scale],[0,0,1.]],float),dist


def prepare_validation():
    images=metadata('validation')
    sequences=sorted({r['sequence'] for r in images})
    if len(sequences)!=2:raise ValueError('Review split for changed release')
    # Entire acquisition sessions, not neighboring images randomly shuffled.
    split={name:[r for r in images if r['sequence']==seq]
        for name,seq in zip(('development','evaluation'),sequences)}
    for name,records in split.items():write_json(ASSETS/f'protocol/{name}-queries.json',records)
    truth=poses('validation')
    write_json(ASSETS/'evaluation_only/validation-truth.json',{k:v.tolist() for k,v in truth.items()})
    report=dict(dataset='Gangnam Station B2 public validation',images=len(images),
        split={name:dict(count=len(records),sequence=records[0]['sequence'],
            ids_sha256=hashlib.sha256('\n'.join(r['id'] for r in records).encode()).hexdigest()) for name,records in split.items()},
        cameras=sorted({r['camera_id'] for r in images}),
        coordinate_convention='kapture world-to-camera inverted to OpenCV camera-to-world',
        evaluation_scope='Self-defined held-out session inside the public validation set; NOT official hidden benchmark test',
        truth_boundary='query manifests contain image, timestamp, camera only; evaluator alone loads validation-truth.json',
        license='Local noncommercial research; modified public images not included in redistributable package')
    write_json(ROOT/'docs/evidence/ar-validation-manifest.json',report)
    return report


if __name__=='__main__':
    import json
    print(json.dumps(prepare_validation(),ensure_ascii=True,indent=2))
