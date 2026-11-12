"""Score actual Unity image traces and publish continuous rendered walkthroughs."""
import argparse,hashlib,json,math,shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from .paths import ASSETS,ROOT,write_json
from .geometry import pose_error

LABELS={'normal':'엘리베이터까지 이동','loss':'영상 상실과 복구','closed':'엘리베이터 접근 중단'}
STATES={'guiding':'엘리베이터 방향으로 이동','locating':'위치 확인 중','confirming':'위치를 다시 확인하는 중',
        'position_uncertain':'위치 확인 불가 · 이동 안내 중단','arrived':'가상 엘리베이터 접근 지점 도착','blocked':'접근 중단 · 등록된 대체 경로 없음'}
BASE=ASSETS/'gangnam-walk'
WEB=ROOT/'web/gangnam/assets/walk'

def load_lines(path):return [json.loads(x) for x in path.read_text('utf-8').splitlines()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def font(size):return ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',size)

def decorate(folder,frame,prediction,label):
    canvas=Image.new('RGB',(960,720),'#122b29');canvas.paste(Image.open(folder/frame['image']).convert('RGB'),(0,76))
    d=ImageDraw.Draw(canvas);d.text((28,17),'WAYFINDING  /  '+LABELS[label],font=font(23),fill='#f2f5ed')
    d.text((610,24),'강남역 공개 동선 참고 · 가상 재현',font=font(16),fill='#c4d3ca')
    state=frame['state'] or 'locating';d.text((28,632),STATES.get(state,state),font=font(26),fill='white')
    if state=='guiding' and prediction:
        distance=prediction['remaining_m'];d.text((735,632),f'{distance:.1f} m 남음',font=font(25),fill='#8ae5b6')
    detail=f'기록 시각 {frame["time_s"]:.1f}s  ·  '
    detail+=f'대응점 {prediction["inliers"]}개  ·  영상 위치 추정' if prediction else '위치 추정 결과 없음'
    d.text((28,681),detail,font=font(16),fill='#bdcfc5')
    d.text((610,681),'15 fps 재생 · 추정 처리시간과 별도',font=font(15),fill='#bdcfc5')
    return canvas

def writer(path):
    import imageio_ffmpeg
    w=imageio_ffmpeg.write_frames(str(path),(960,720),fps=15,codec='libx264',pix_fmt_in='rgb24',pix_fmt_out='yuv420p',
        output_params=['-crf','22','-movflags','+faststart'],macro_block_size=1);w.send(None);return w

def vtt_time(t):
    ms=round(t*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d}.{ms%1000:03d}'

def generate(run):
    WEB.mkdir(parents=True,exist_ok=True);results=[];timelines={};folders={};observations={};frames={}
    for name in LABELS:
        folder=BASE/'runs'/run/name;folders[name]=folder
        rows=load_lines(folder/'observations.jsonl');video=load_lines(folder/'video.jsonl');info=json.loads((folder/'run.json').read_text('utf-8'))
        if len(video)!=info['video_frames'] or len(rows)!=info['observations']:raise ValueError('Trace count mismatch')
        if not all(b['time_s']>a['time_s'] for a,b in zip(rows,rows[1:])):raise ValueError('Unordered queries')
        events=[];last=None;errors=[];angles=[];accurate=0;shown_wrong=0;by_frame={};timeline=[]
        for r in rows:
            pr=r['prediction'] if not r.get('transport_error') else None
            position_error=angle=None
            if pr and pr.get('success'):
                position_error,angle=pose_error(np.array(pr['pose']).reshape(4,4),np.array(r['reference_pose']).reshape(4,4))
                errors.append(position_error);angles.append(angle)
            good=position_error is not None and position_error<=.5 and angle<=5
            accurate+=bool(good);shown_wrong+=bool(r['visible'] and not good)
            if r['visible'] and (not pr or not pr['arrow_visible']):raise ValueError('Arrow without valid guidance')
            if r['blackout'] and r['visible']:raise ValueError('Arrow during black image observation')
            state=pr['state'] if pr else 'position_uncertain'
            if state!=last:events.append(dict(time_s=r['time_s'],state=state));last=state
            by_frame[r['frame']]=dict(time_s=r['time_s'],frame=r['frame'],state=state,
                remaining_m=pr['remaining_m'] if pr and state in ('guiding','arrived') else None,
                inliers=pr['inliers'] if pr else 0,accepted=bool(pr and pr['accepted']),
                position_error_m=position_error,orientation_error_deg=angle,http_ms=r['http_ms'],
                position=pr['position'] if pr and pr['success'] else None,reason=pr['reason'] if pr else r['transport_error'],
                localization_reason=pr['localization_reason'] if pr else 'transport_error')
        for v in video:
            if v['visible'] and (v['blackout'] or v['state']!='guiding'):raise ValueError('Stale guidance on a rendered frame')
            obs=by_frame.get(v['observation_frame'])
            timeline.append(dict(time_s=v['time_s'],state=v['state'],visible=v['visible'],blackout=v['blackout'],observation=obs))
        w=writer(WEB/f'{name}.mp4');pmap={r['frame']:r['prediction'] for r in rows}
        for v in video:
            im=decorate(folder,v,pmap.get(v['observation_frame']),name);w.send(np.asarray(im).tobytes())
            if v['frame']==0:im.save(WEB/f'{name}.jpg',quality=93)
            if v['frame']==min(120,len(video)-1):im.save(WEB/f'{name}-scene.jpg',quality=93)
        w.close();duration=len(video)/15
        render_events=[]
        for v in video:
            if not render_events or render_events[-1]['state']!=v['state']:render_events.append(dict(time_s=v['time_s'],state=v['state']))
        captions=['WEBVTT','']
        for i,e in enumerate(render_events):
            end=render_events[i+1]['time_s'] if i+1<len(render_events) else duration
            captions.extend([f'{vtt_time(e["time_s"])} --> {vtt_time(end)}',STATES.get(e['state'],e['state']),''])
        (WEB/f'{name}.vtt').write_bytes('\n'.join(captions).encode())
        result=dict(id=name,label=LABELS[name],observations=len(rows),accepted=sum(bool(r['prediction']['accepted']) for r in rows if not r['transport_error']),
            accurate=accurate,visible=sum(r['visible'] for r in rows),visible_inaccurate=shown_wrong,
            position_p50_m=float(np.median(errors)) if errors else None,position_p95_m=float(np.quantile(errors,.95)) if errors else None,
            http_p50_ms=float(np.median([r['http_ms'] for r in rows])),final_state=info['final_state'],duration_s=duration,events=events,render_events=render_events,
            trace_sha256=sha(folder/'observations.jsonl'),video_trace_sha256=sha(folder/'video.jsonl'))
        results.append(result);timelines[name]=timeline;observations[name]=pmap;frames[name]=video
        print(json.dumps(result,ensure_ascii=False),flush=True)
    # Unmodified execution order within each chapter; overview is explicitly edited, not a single continuous trial.
    segments=[('normal',0,len(frames['normal'])),('loss',int(10*15),int(22*15)),('closed',int(5*15),len(frames['closed']))]
    total=sum(b-a for _,a,b in segments);hold=max(0,900-total)
    overview=[];w=writer(WEB/'overview.mp4')
    for name,a,b in segments:
        for index in range(a,b):
            v=frames[name][index];im=decorate(folders[name],v,observations[name].get(v['observation_frame']),name)
            w.send(np.asarray(im).tobytes());overview.append(dict(time_s=len(overview)/15,chapter=name,source_time_s=v['time_s'],**{k:v for k,v in timelines[name][index].items() if k!='time_s'}))
    for _ in range(hold):w.send(np.asarray(im).tobytes());overview.append(overview[-1]|dict(time_s=len(overview)/15))
    w.close();shutil.copy2(WEB/'normal.jpg',WEB/'overview.jpg');timelines['overview']=overview
    summary=dict(status='executed',run=run,exporter_sha256=sha(__import__('pathlib').Path(__file__)),scene_revision='gangnam-walk-v2',scope='Synthetic Unity XR Simulation; historical Gangnam trajectory only',
        length_m=json.loads((BASE/'scene.json').read_text('utf-8'))['length'],runs=results,
        accuracy='Position <=0.5 m AND orientation <=5 degrees; denominator includes every image query, including failures',
        timing='15 fps is video playback. Image queries every 8 video frames (0.533 logical s); wall HTTP latency is measured separately. Offline retimed capture.',
        movement='Scripted user follows the authored path and pauses while guidance is unavailable. Manual control is available in Unity. This does not demonstrate autonomous navigation.',
        source_snapshot=json.loads((BASE/'runs'/run/'source/manifest.json').read_text('utf-8')) if (BASE/'runs'/run/'source/manifest.json').exists() else None,
        assumptions=['Identical synthetic scene for map and queries with different viewpoints and camera heights','Unique authored signs and posters improve feature matching','No present-day Gangnam field, device or user validation'],
        representative_duration_s=len(overview)/15,representative_edit='Normal full run, loss seconds 10–22, closure seconds 5–end, final still hold if needed')
    if not 60<=summary['representative_duration_s']<=90:raise ValueError('Overview must be 60–90 seconds')
    write_json(WEB/'results.json',summary);write_json(WEB/'timeline.json',timelines)
    write_json(ROOT/'docs/evidence/gangnam-walk-results.json',summary)
    plots(results,timelines)
    files=[p for p in WEB.iterdir() if p.name!='manifest.json']
    write_json(WEB/'manifest.json',dict(license='Original synthetic imagery; no NAVER photographs used in these renders',files={p.name:sha(p) for p in files}))

def plots(results,timelines):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(3,1,figsize=(10,5.8),layout='constrained',sharex=True)
    colors={'guiding':'#218570','arrived':'#255c95','blocked':'#a76623','position_uncertain':'#b35b53','confirming':'#bdab73','locating':'#999999'}
    for ax,r in zip(axes,results):
        timeline=timelines[r['id']]
        for state in colors:
            xs=[v['time_s'] for v in timeline if v['state']==state]
            ax.scatter(xs,[1]*len(xs),s=11,marker='|',c=colors[state],label=STATES.get(state,state))
        ax.set_ylim(.7,1.3);ax.set_yticks([]);ax.set_title(r['label'],loc='left',fontsize=11);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlabel('재생 시계 (초) · 추정 처리시간과 별도');fig.savefig(WEB/'states.png',dpi=160);plt.close(fig)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);generate(parser.parse_args().run)
