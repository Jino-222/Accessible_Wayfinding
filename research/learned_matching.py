"""Paired image-retrieval + RootSIFT NN / pretrained SIFT-LightGlue experiment.

Both methods receive the same candidates, keypoints, mapping depth and PnP.
No training is performed. This is a follow-up on already inspected B2 validation,
not a new hidden-test score. Inference writes predictions before loading truth.
"""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
import time
import cv2
import numpy as np
import torch
from .paths import ASSETS,ROOT,write_json
from .localizer import Localizer,normalize_root,points_from_depth,MAX_SIDE,FEATURES
from .gangnam import intrinsics
from .geometry import invert_pose,pose_error
from .evaluate_localization import summarize

TOP_K=3
MATCH_FEATURES=1024
METHODS=('retrieved_rootsift_pnp','retrieved_lightglue_pnp')
COMMIT='5a650c444718caffc2669dc0094cde908f42dd73'


def features(query):
    im=cv2.imdecode(np.fromfile(query['path'],np.uint8),cv2.IMREAD_GRAYSCALE)
    c=query['camera']
    if im is None or im.shape!=(c['height'],c['width']):raise ValueError('Image/calibration mismatch')
    scale=min(1.,MAX_SIDE/max(im.shape))
    if scale!=1:im=cv2.resize(im,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    keys,desc=cv2.SIFT_create(nfeatures=FEATURES).detectAndCompute(im,None)
    if desc is None:desc=np.empty((0,128),np.float32)
    roots=normalize_root(desc)
    keep=np.argsort([-k.response for k in keys],kind='stable')[:MATCH_FEATURES]
    allxy=np.asarray([k.pt for k in keys],np.float32).reshape(-1,2)
    value=dict(keypoints=allxy[keep],descriptors=roots[keep],
        scales=np.asarray([k.size for k in keys],np.float32)[keep],
        oris=np.deg2rad(np.asarray([k.angle for k in keys],np.float32))[keep],
        image_size=np.array([im.shape[1],im.shape[0]],np.float32))
    return value,roots,scale


def estimate_pose(world,pixels,k,dist):
    result=dict(success=False,accepted=False,pose=None,inliers=0,reprojection_px=None,matches=len(world),reason='insufficient_correspondences')
    if len(world)<8:return result
    cv2.setRNGSeed(23)
    ok,rv,tv,indices=cv2.solvePnPRansac(np.asarray(world,np.float64),np.asarray(pixels,np.float64),k,dist,
        iterationsCount=3000,reprojectionError=4.,confidence=.999,flags=cv2.SOLVEPNP_EPNP)
    if not ok or indices is None or len(indices)<6:return result|dict(reason='pnp_failed')
    ids=indices.ravel();w=np.asarray(world,np.float64)[ids];xy=np.asarray(pixels,np.float64)[ids]
    rv,tv=cv2.solvePnPRefineLM(w,xy,k,dist,rv,tv)
    projected=cv2.projectPoints(w,rv,tv,k,dist)[0].reshape(-1,2)
    error=float(np.median(np.linalg.norm(projected-xy,axis=1)))
    cw=np.eye(4);cw[:3,:3]=cv2.Rodrigues(rv)[0];cw[:3,3]=tv.ravel()
    front=bool(((w@cw[:3,:3].T+cw[:3,3])[:,2]>0).all())
    pose=invert_pose(cw)
    accepted=len(ids)>=12 and error<=4 and front
    return result|dict(success=True,accepted=accepted,pose=pose.tolist(),inliers=len(ids),
        reprojection_px=error,reason='pose_estimated' if accepted else 'pose_rejected_by_quality')


def select_candidate(candidates):
    # All ranking fields are observable. No reference pose/floor/distance.
    return max(candidates,key=lambda c:(bool(c['accepted']),bool(c['success']),c['inliers'],
        -(c['reprojection_px'] if c['reprojection_px'] is not None else float('inf'))))


class PairedMatcher:
    def __init__(self):
        from lightglue import LightGlue
        from .gangnam_mapping import mapping_views
        torch.set_num_threads(2);torch.manual_seed(23)
        torch.hub.set_dir(str(ASSETS/'model-cache'))
        self.lightglue=LightGlue(features='sift',flash=False).eval()
        self.retrieval=Localizer(ASSETS/'gangnam-map/map.npz',True)
        with np.load(ASSETS/'gangnam-map/map.npz') as archive:self.image_ids=archive['image_ids']
        self.views=mapping_views()
        report=json.loads((ASSETS/'gangnam-map/map-report.json').read_text('utf-8'))
        if [v['id'] for v in self.views]!=[v['id'] for v in report['stats']]:raise ValueError('Retrieval map/view order mismatch')
        self.cache=ASSETS/'gangnam-map/learned-pair-cache-v1';self.cache.mkdir(exist_ok=True)

    @lru_cache(maxsize=24)
    def mapping(self,index):
        view=self.views[index];name=hashlib.sha256(view['id'].encode()).hexdigest()[:24]
        path=self.cache/(name+'.npz')
        if path.exists():
            with np.load(path) as archive:return {key:archive[key] for key in archive.files}
        f,_,scale=features(view)
        depth=np.fromfile(view['depth_path'],dtype='<f4').reshape(view['depth_shape'])
        xyz,valid=points_from_depth(f['keypoints'],depth,view['camera'],np.array(view['pose']),scale,view['depth_camera'])
        f.update(xyz=xyz,valid=valid);np.savez_compressed(path,**f)
        return f

    def tensor(self,f):
        return {key:torch.from_numpy(np.ascontiguousarray(f[key])).unsqueeze(0)
                for key in ('keypoints','descriptors','scales','oris','image_size')}

    def infer(self,query):
        begin=time.perf_counter();q,all_desc,scale=features(query)
        matches=self.retrieval.index.knnMatch(all_desc,k=2) if len(all_desc)>=8 else []
        votes=Counter(int(self.image_ids[p[0].trainIdx]) for p in matches
                      if len(p)==2 and p[0].distance<.8*p[1].distance)
        ids=[i for i,_ in sorted(votes.items(),key=lambda x:(-x[1],x[0]))[:TOP_K]]
        candidates=[(i,self.mapping(i)) for i in ids]
        k,dist=intrinsics(query['camera'],scale)
        shared_ms=(time.perf_counter()-begin)*1000
        outputs=[]
        for method in METHODS:
            started=time.perf_counter();estimates=[]
            for index,ref in candidates:
                try:
                    if method==METHODS[0]:
                        pairs=cv2.BFMatcher(cv2.NORM_L2).knnMatch(q['descriptors'],ref['descriptors'],k=2)
                        raw=sorted((p[0] for p in pairs if len(p)==2 and p[0].distance<.8*p[1].distance),key=lambda m:m.distance)
                        used=set();matches=[]
                        for m in raw:
                            if m.trainIdx not in used:matches.append((m.queryIdx,m.trainIdx));used.add(m.trainIdx)
                        pair=np.asarray(matches,dtype=int).reshape(-1,2)
                    else:
                        with torch.inference_mode():
                            found=self.lightglue({'image0':self.tensor(q),'image1':self.tensor(ref)})
                        pair=found['matches'][0].cpu().numpy().reshape(-1,2)
                    pair=pair[ref['valid'][pair[:,1]]]
                    pose=estimate_pose(ref['xyz'][pair[:,1]],q['keypoints'][pair[:,0]],k,dist)
                    estimates.append(pose|dict(mapping_id=self.views[index]['id'],retrieval_votes=votes[index]))
                except (ValueError,RuntimeError,cv2.error) as exc:
                    estimates.append(dict(success=False,accepted=False,pose=None,inliers=0,reprojection_px=None,
                        matches=0,reason='processing_error',error=str(exc),mapping_id=self.views[index]['id']))
            best=select_candidate(estimates) if estimates else dict(success=False,accepted=False,pose=None,
                inliers=0,reprojection_px=None,matches=0,reason='no_retrieval_candidate')
            outputs.append(best|dict(id=query['id'],method=method,query_features=len(q['keypoints']),
                candidates=[{key:c[key] for key in ('mapping_id','success','accepted','inliers','reprojection_px','reason')} for c in estimates],
                shared_preparation_ms=shared_ms,elapsed_ms=shared_ms+(time.perf_counter()-started)*1000))
        return outputs


def run(split,limit=0):
    queries_path=ASSETS/f'protocol/{split}-queries.json'
    queries=json.loads(queries_path.read_text('utf-8'))
    if limit:queries=queries[:limit]
    out=ASSETS/'gangnam-results/learned';out.mkdir(parents=True,exist_ok=True)
    label=split+('-smoke-'+str(limit) if limit else '')
    algorithm=PairedMatcher()
    weights=list((ASSETS/'model-cache/checkpoints').glob('sift_lightglue*.pth'))
    config=dict(source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
        queries_sha256=hashlib.sha256(queries_path.read_bytes()).hexdigest(),methods=METHODS,
        lightglue_commit=COMMIT,lightglue_weights_sha256={w.name:hashlib.sha256(w.read_bytes()).hexdigest() for w in weights},
        top_candidates=TOP_K,matching_features=MATCH_FEATURES,retrieval_features=FEATURES,max_side=MAX_SIDE,
        cpu_threads=2,torch_version=torch.__version__,opencv_version=cv2.__version__,device='cpu',
        split=split,limit=limit,scope='Previously inspected B2 validation; paired system comparison, not independent hidden test')
    frozen=out/f'{label}-config.json'
    if frozen.exists() and json.loads(frozen.read_text('utf-8'))!=json.loads(json.dumps(config)):
        raise ValueError('Configuration changed: use a new experiment directory rather than overwrite prior run')
    write_json(frozen,config)
    prediction_path=out/f'{label}-predictions.jsonl'
    predictions=[json.loads(line) for line in prediction_path.read_text('utf-8').splitlines()] if prediction_path.exists() else []
    seen={(r['id'],r['method']) for r in predictions}
    with prediction_path.open('a',encoding='utf-8') as stream:
        for index,query in enumerate(queries):
            if all((query['id'],method) in seen for method in METHODS):continue
            for row in algorithm.infer(query):
                if (row['id'],row['method']) in seen:continue
                stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush();predictions.append(row)
            print(json.dumps(dict(stage='paired_matching',done=index+1,total=len(queries))),flush=True)
    truth=json.loads((ASSETS/'evaluation_only/validation-truth.json').read_text('utf-8'))
    for row in predictions:
        row['position_error_m'],row['orientation_error_deg']=pose_error(row['pose'],truth[row['id']]) if row['success'] else (None,None)
    summary=[summarize(predictions,method) for method in METHODS]
    for row in summary:
        accepted=[r for r in predictions if r['method']==row['method'] and r['accepted']]
        row['severe_accepted_count']=sum(r['position_error_m']>5 for r in accepted)
    report=dict(kind='paired_learned_matching',config=config,summary=summary,results=predictions,
        figures=[],assumptions=['Both methods use the same top-3 RootSIFT-vote mapping images, top-1024 SIFT features and registered depth.',
        'NN ratio matching versus pretrained SIFT-LightGlue; no model training.',
        'Mapping candidate selection and ranking use no evaluation truth. Scoring loads truth only after prediction files are written.',
        'Elapsed time charges shared query/retrieval/map-cache preparation to both methods; offline model/map load excluded.',
        'Fixed held-out session was already inspected in the earlier study. This follow-up is not an independent benchmark.'])
    write_json(out/f'{label}-summary.json',report)
    write_json(ROOT/f'docs/evidence/ar-learned-{label}.json',report)
    print(json.dumps(summary,indent=2));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--split',choices=['development','evaluation'],default='development')
    parser.add_argument('--limit',type=int,default=0);args=parser.parse_args();run(args.split,args.limit)
