"""Register a short, visually inspected B2 corridor from MAPPING records only.

The destination is an observed point beside an elevator, not a surveyed doorway.
No validation/test reference poses enter this map. The facility's current serial
number and current operating status remain unverified.
"""
from pathlib import Path
import hashlib
import shutil
import numpy as np
from .gangnam import metadata,poses
from .paths import ROOT,write_json


def main():
    views=sorted([v for v in metadata('mapping') if v['camera_id']=='40027089_28'],key=lambda v:v['timestamp'])
    reference=poses('mapping')
    if len(views)!=381:raise ValueError('Mapping sequence changed; annotations require review')
    selected=[(260,'corridor-a','승강장 관측지점 A'),
              (272,'elevator-approach','엘리베이터 앞 관측지점'),
              (284,'corridor-b','계단 인근 관측지점 B')]
    out=ROOT/'web/gangnam';nodes=[];rights=[]
    for index,id,label in selected:
        view=views[index];file='assets/naver-originals/map-'+id+'.jpg';target=out/file
        shutil.copyfile(view['path'],target)
        nodes.append(dict(id=id,label=label,floor='B2',position=reference[view['id']][:3,3].tolist(),
            reference_image=file,reference_id=view['id'],source='mapping_camera_position',
            annotation='visually inspected public mapping photograph',
            current_facility_id=None,operation='unknown'))
        rights.append(dict(file=file,original_id=view['id'],sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            modified=False,copyright='NAVER LABS',license='CC BY-NC-ND 4.0 (modified ver.)'))
    edges=[]
    for a,b,lo,hi in [('corridor-a','elevator-approach',260,272),('elevator-approach','corridor-b',272,284)]:
        path=[reference[v['id']][:3,3].tolist() for v in views[lo:hi+1]]
        segments=np.linalg.norm(np.diff(np.asarray(path)[:,:2],axis=0),axis=1)
        if segments.max()>3:raise ValueError('Discontinuous mapping trajectory; do not join by shortcut')
        edges.append(dict(a=a,b=b,kind='walk',stairs=False,polyline=path,
            sampled_path_length_m=float(segments.sum()),length_method='XY length along mapping camera samples',
            width_m=None,slope=None,field_verified=False))
    data=dict(id='gangnam-b2-observed-corridor',nodes=nodes,edges=edges,rights=rights,
        coordinates='NAVER mapping camera-to-world; horizontal XY. Z is not a floor number.',
        destination_evidence='Mapping image 40027089_1575341564779869.jpg shows elevator, overhead elevator arrow and B1/B2 panel.',
        identity='B2 elevator approach observed in historical imagery; current elevator serial number not established',
        scope='Short recorded corridor only. No elevator boarding, no B1 or street routing in these coordinates.',
        connectivity='Recorded mapping trajectory and visual inspection; wheelchair width/slope not verified',
        route_direction='Bidirectional for replay experiment only; current passage restrictions unverified',
        input_truth='Mapping poses only; no validation/test ground truth used',
        completion='Approach checkpoint in demonstration; not proof of actual arrival or safe boarding')
    write_json(out/'data/corridor.json',data)
    write_json(ROOT/'docs/evidence/gangnam-corridor-registration.json',data)
    print('Registered 3 observed checkpoints, 2 corridor segments; facility identity and field access remain unverified')


if __name__=='__main__':main()
