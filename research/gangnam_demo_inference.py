"""Run selected public test images without loading hidden or validation truth.

This is a demonstration run, not a scored benchmark. The query manifest must
contain IDs from the official test split; mapping images cannot be queries.
"""
from pathlib import Path
import argparse
import hashlib
import json
from .gangnam import metadata
from .learned_matching import PairedMatcher, METHODS, COMMIT
from .paths import ASSETS, write_json


def run(manifest):
    manifest=Path(manifest)
    spec=json.loads(manifest.read_text('utf-8'))
    if set(spec)-{'ids','selection','name'}:raise ValueError('Unexpected manifest field')
    if not spec['ids'] or len(set(spec['ids']))!=len(spec['ids']):raise ValueError('Empty or duplicate queries')
    available={r['id']:r for r in metadata('test')}
    if any(id not in available for id in spec['ids']):raise ValueError('Queries must belong to the public test split')
    digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
    out=ASSETS/'gangnam-results/demo-test'/digest[:12]
    out.mkdir(parents=True,exist_ok=True)
    config=dict(kind='unscored_public_test_demo',query_manifest_sha256=digest,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        methods=METHODS,lightglue_commit=COMMIT,count=len(spec['ids']),selection=spec['selection'],
        ground_truth='Not supplied by the public test split; no accuracy claims',
        policy='Keep unsuccessful and rejected estimates; select/rank using image observations only')
    frozen=out/'config.json'
    if frozen.exists() and json.loads(frozen.read_text('utf-8'))!=config:raise ValueError('Existing run config differs')
    write_json(frozen,config)
    path=out/'predictions.jsonl'
    done={(r['id'],r['method']) for r in map(json.loads,path.read_text('utf-8').splitlines())} if path.exists() else set()
    algorithm=PairedMatcher()
    with path.open('a',encoding='utf-8') as f:
        for i,id in enumerate(spec['ids']):
            if all((id,m) in done for m in METHODS):continue
            for row in algorithm.infer(available[id]):
                if (id,row['method']) in done:continue
                f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
            print(json.dumps(dict(done=i+1,total=len(spec['ids']),run=out.name)),flush=True)
    records=[json.loads(s) for s in path.read_text('utf-8').splitlines()]
    report=dict(config=config,methods=[dict(method=m,queries=len(spec['ids']),
        output_count=sum(r['success'] for r in records if r['method']==m),
        quality_accepted_count=sum(r['accepted'] for r in records if r['method']==m),
        accuracy=None) for m in METHODS])
    write_json(out/'summary.json',report)
    print(json.dumps(report));return out


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('manifest');args=parser.parse_args();run(args.manifest)
