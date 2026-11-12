"""Evaluator is the only stage allowed to read held-out reference poses."""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
from .geometry import pose_error
from .localizer import Localizer
from .paths import ASSETS,ROOT,write_json


def summarize(rows,method):
    selected=[r for r in rows if r['method']==method]
    poses=[r for r in selected if r['success']]
    accepted=[r for r in selected if r['accepted']]
    def quantile(values,q):return float(np.quantile(values,q)) if len(values) else None
    total=len(selected)
    value=dict(method=method,total=total,success_count=len(poses),accepted_count=len(accepted),
        output_rate=len(poses)/total,acceptance_rate=len(accepted)/total,
        position_median_m=quantile([r['position_error_m'] for r in poses],.5),
        position_p95_m=quantile([r['position_error_m'] for r in poses],.95),
        orientation_median_deg=quantile([r['orientation_error_deg'] for r in poses],.5),
        accepted_position_median_m=quantile([r['position_error_m'] for r in accepted],.5),
        elapsed_p50_ms=quantile([r['elapsed_ms'] for r in selected],.5),
        elapsed_p95_ms=quantile([r['elapsed_ms'] for r in selected],.95),
        failures=dict(Counter(r['reason'] for r in selected if not r['success'])))
    for name,metres,degrees in [('025m_2deg',.25,2),('05m_5deg',.5,5),('1m_10deg',1,10)]:
        value['success_'+name]=sum(r['position_error_m']<=metres and r['orientation_error_deg']<=degrees for r in poses)/total
        value['accepted_success_'+name]=sum(r['position_error_m']<=metres and r['orientation_error_deg']<=degrees for r in accepted)/total
    return value


def plots(rows,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
    out.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for method,color in [('sift_pnp','#b17b46'),('rootsift_pnp','#17736a')]:
        selected=[r for r in rows if r['method']==method];good=[r for r in selected if r['success']]
        errors=sorted(r['position_error_m'] for r in good)
        ax[0].step(errors,np.arange(1,len(errors)+1)/len(selected),where='post',label=method,color=color)
        ax[1].scatter([r['position_error_m'] for r in good],[r['orientation_error_deg'] for r in good],s=12,alpha=.5,label=method,color=color)
    ax[0].set(xlabel='Position error (m)',ylabel='Fraction of ALL queries',ylim=(0,1),xlim=(0,5));ax[0].legend(fontsize=8)
    ax[1].set(xlabel='Position error (m)',ylabel='Orientation error (deg)',xscale='symlog',yscale='symlog')
    fig.suptitle('Image localization | failures stay in CDF denominator')
    fig.savefig(out/'localization-errors.png',dpi=160);plt.close(fig)
    return ['localization-errors.png']


def run(study,split,limit=0):
    if study=='gangnam':
        queries=json.loads((ASSETS/f'protocol/{split}-queries.json').read_text('utf-8'))
        truth_file=ASSETS/'evaluation_only/validation-truth.json'
        map_file=ASSETS/'gangnam-map/map.npz';out=ASSETS/'gangnam-results'
        scope='Gangnam B2 public validation, held-out session; not the official hidden test'
    else:
        software=study=='synthetic-software'
        queries=json.loads((ASSETS/('synthetic/software-rendered/query-inputs.json' if software else 'synthetic/rendered/query-inputs.json')).read_text('utf-8'))
        truth_file=ASSETS/('evaluation_only/software-truth.json' if software else 'evaluation_only/synthetic-truth.json')
        map_file=ASSETS/('synthetic/software-map/map.npz' if software else 'synthetic/map/map.npz')
        out=ASSETS/('synthetic/software-vision-results' if software else 'synthetic/vision-results')
        scope=('Python 2.5D raycast' if software else 'Unity')+' synthetic RGB at held-out positions, headings and heights'
    if limit:queries=queries[:limit]
    if not queries:raise ValueError('No registered queries')
    out.mkdir(parents=True,exist_ok=True)
    # Inference does not load any reference poses. Predictions flushed to disk first.
    suffix=f'{split}-smoke-{limit}' if limit else split
    predictions=[]
    with (out/f'{suffix}-predictions.jsonl').open('w',encoding='utf-8') as stream:
        for root_sift in (False,True):
            algorithm=Localizer(map_file,root_sift)
            for index,query in enumerate(queries):
                result=algorithm.estimate(query)
                stream.write(json.dumps(result,allow_nan=False)+'\n');stream.flush()
                predictions.append(result)
                if index%25==0:print(json.dumps(dict(study=study,method=result['method'],done=index+1,total=len(queries))),flush=True)
    truth=json.loads(truth_file.read_text('utf-8'))
    for result in predictions:
        if result['success']:
            result['position_error_m'],result['orientation_error_deg']=pose_error(result['pose'],truth[result['id']])
        else:result['position_error_m']=result['orientation_error_deg']=None
    summary=[summarize(predictions,method) for method in ('sift_pnp','rootsift_pnp')]
    figures=plots(predictions,out/'figures')
    report=dict(kind=study+'_image_localization',scope=scope,split=split,smoke=bool(limit),summary=summary,
        results=predictions,figures=figures,units=dict(position='metres',orientation='degrees',processing='milliseconds'),
        assumptions=['No query ground truth is available to Localizer','SIFT features + registered map depths + PnP; no model training',
            'Independently localized still images, no IMU or real-time trajectory tracking',
            'Quality acceptance is a heuristic, not a calibrated probability or safety guarantee'])
    write_json(out/f'{suffix}-summary.json',report)
    write_json(ROOT/f'docs/evidence/ar-{study}-{suffix}.json',report)
    print(json.dumps(summary,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--study',choices=['gangnam','synthetic','synthetic-software'],required=True)
    parser.add_argument('--split',choices=['development','evaluation'],default='development');parser.add_argument('--limit',type=int,default=0)
    args=parser.parse_args();run(args.study,args.split,args.limit)
