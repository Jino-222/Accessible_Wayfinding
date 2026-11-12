"""Export original test photographs and precomputed, unscored observations."""
from pathlib import Path
import hashlib
import json
import shutil
from research.paths import ROOT,ASSETS,write_json
from research.gangnam import metadata


def main():
    queries={r['id']:r for r in metadata('test')}
    out=ROOT/'web/gangnam';streams=[];rights=[]
    for manifest,name in [('gangnam-test-demo-queries.json','승강장 접근 · 카메라 55'),
                          ('gangnam-test-elevator-queries.json','엘리베이터 시야 · 카메라 54')]:
        path=ROOT/'docs'/manifest;digest=hashlib.sha256(path.read_bytes()).hexdigest();run=ASSETS/'gangnam-results/demo-test'/digest[:12]
        if not (run/'summary.json').exists():continue
        spec=json.loads(path.read_text('utf-8'));summary=json.loads((run/'summary.json').read_text('utf-8'))
        predictions={r['id']:r for r in map(json.loads,(run/'predictions.jsonl').read_text('utf-8').splitlines()) if r['method']=='retrieved_lightglue_pnp'}
        if set(predictions)!=set(spec['ids']):raise ValueError('Incomplete sequence')
        frames=[]
        for id in spec['ids']:
            q=queries[id];p=predictions[id];name_on_disk='test-'+Path(id).name;file='assets/naver-originals/'+name_on_disk
            dest=out/file;shutil.copyfile(q['path'],dest)
            frames.append(dict(id=id,timestamp=q['timestamp'],image=file,pose=p['pose'],accepted=p['accepted'],
                inliers=p['inliers'],reprojection_px=p['reprojection_px'],reason=p['reason'],elapsed_ms=p['elapsed_ms']))
            rights.append(dict(file=file,original_id=id,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                modified=False,copyright='NAVER LABS',license='CC BY-NC-ND 4.0 (modified ver.)'))
        streams.append(dict(id=digest[:12],name=name,frames=frames,summary=summary,
            accuracy=None,selection=spec['selection'],mode='precomputed_public_test_predictions'))
    if not streams:raise ValueError('No complete inference run')
    write_json(out/'data/corridor-observations.json',dict(streams=streams,rights=rights,
        notice='공개 test 원본 영상의 저장된 추정값. 정답 비공개로 정확도 미채점. 사진 위 합성 표시 없음.',
        route_source='Separately inspected mapping trajectory and elevator-approach checkpoint',
        field_service=False))
    print('Exported',len(streams),'streams,',len(rights),'unchanged test images')


if __name__=='__main__':main()
