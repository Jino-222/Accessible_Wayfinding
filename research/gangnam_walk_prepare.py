"""Prepare an explicitly synthetic, Gangnam-derived elevator approach scene."""
import json, math, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .paths import ROOT, ASSETS, write_json

BASE = ASSETS / 'gangnam-walk'
STREAM = ROOT / 'unity/AccessibleStation/Assets/StreamingAssets'

def main():
    source = ROOT / 'web/gangnam/data/corridor.json'
    original = json.loads(source.read_text('utf-8'))
    p = np.array(original['edges'][0]['polyline'])
    start = p[0, :2]; forward = p[-1, :2] - start; forward /= np.linalg.norm(forward)
    right = np.array([forward[1], -forward[0]])
    xy = p[:, :2] - start
    path = np.c_[xy @ right, np.zeros(len(p)), xy @ forward]
    length = float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum())
    cumulative = np.r_[0., np.linalg.norm(np.diff(path, axis=0), axis=1).cumsum()]
    def at(d):
        return [float(np.interp(d, cumulative, path[:, k])) for k in range(3)]
    mapping = []
    for d in np.arange(0, length + .01, 1.25):
        for lateral in (-.65, .65):
            for yaw in (155., 180., 205.):
                pos = at(d); pos[0] += lateral; pos[1] = 1.5
                mapping.append(dict(id=f'map-{len(mapping):04d}', split='mapping', position=pos, yaw=yaw, pitch=6.))
    scene = dict(revision='gangnam-walk-v2', path=[dict(position=v.tolist()) for v in path], length=length,
                 width=640, height=360, fov=62., output=str(BASE / 'mapping'), mapping=mapping,
                 corridor_half_width=3.4, ceiling_height=3.3)
    write_json(STREAM / 'gangnam-walk.json', scene)
    write_json(BASE / 'scene.json', scene)
    provenance = dict(revision=scene['revision'], source='web/gangnam/data/corridor.json',
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), length_m=length,
        source_origin_xy=start.tolist(), source_forward_xy=forward.tolist(), source_right_xy=right.tolist(),
        transform='local x=dot(source_xy-origin,right); local z=dot(source_xy-origin,forward); local y=synthetic height; Unity=(x,y,-z)',
        observed=['historical mapping camera trajectory between observation A and elevator approach'],
        synthetic=['corridor width 6.8 m','ceiling height 3.3 m','walls, signs, posters, floor and elevator geometry','walk camera height 1.2 m'],
        limitations=['Not a surveyed Gangnam model','No present facility identity or operation verified','No proof of wheelchair passability'],
        mapping_views=len(mapping), query_policy='Different height (1.2 m), centre-line path and continuously changing viewpoints; no query images in mapping',
        boundary='Only RGB, camera intrinsics, timestamp and declared camera height cross the localization API; truth is evaluation-only')
    write_json(ROOT / 'docs/evidence/gangnam-walk-protocol.json', provenance)
    textures = STREAM / 'GangnamWalk'; textures.mkdir(exist_ok=True)
    font_path = 'C:/Windows/Fonts/malgun.ttf'
    def font(size): return ImageFont.truetype(font_path, size)
    palettes = [('#173b4b','#80c5b8'),('#273d63','#b3c5e8'),('#5d4930','#d8bf82'),('#31574e','#a9ceaf')]
    titles = ['길을 잇다','모두의 이동','도시의 하루','다음 목적지','함께 걷는 길','가까운 일상']
    for i in range(18):
        dark, accent = palettes[i % 4]
        im = Image.new('RGB',(512,640),'#f1eee5'); draw = ImageDraw.Draw(im)
        draw.rectangle((0,0,512,16),fill=dark)
        draw.text((32,36),f'STATION JOURNAL  /  {i+1:02d}',font=font(20),fill=dark)
        draw.text((32,90),titles[i%6],font=font(52),fill=dark)
        # Authored geometric poster designs provide visual texture; no original dataset imagery.
        for j in range(7):
            x=30+((i*71+j*67)%370); y=210+((i*47+j*43)%230)
            if (j+i)%2: draw.ellipse((x,y,x+70+(i%3)*10,y+70),fill=accent,outline=dark,width=3)
            else: draw.polygon([(x,y),(x+80,y+20),(x+55,y+90),(x-15,y+65)],fill=dark)
        draw.line([(32,530),(480,530)],fill=dark,width=2)
        draw.text((32,552),f'GANGNAM  B2   /   구역 {i+1:02d}',font=font(25),fill=dark)
        draw.text((32,592),'가상 공간 · 시각 인식 실험',font=font(18),fill=dark)
        im.save(textures/f'poster-{i:02d}.png')
    for name,title,sub in [('elevator','엘리베이터','ELEVATOR   /   B2'),('wayfinding','엘리베이터 ↑','ELEVATOR  /  STEP-FREE ROUTE')]:
        im=Image.new('RGB',(1024,256),'#173b38'); d=ImageDraw.Draw(im)
        d.rectangle((0,0,18,256),fill='#7cd0a8');d.text((60,25),title,font=font(82),fill='white')
        d.text((65,153),sub,font=font(35),fill='#b6d7cb');im.save(textures/f'{name}.png')
    im=Image.new('RGB',(512,640),'#f2f1e9');d=ImageDraw.Draw(im)
    d.rectangle((0,0,512,160),fill='#244b44');d.text((35,15),'B2',font=font(110),fill='white')
    d.text((35,190),'엘리베이터',font=font(50),fill='#244b44')
    for i,line in enumerate(['출입문 앞에서 잠시 대기','내리는 사람 먼저','이동 중 손잡이 이용','B1 대합실 / B2 승강장']):
        d.rectangle((35,280+i*62,43,288+i*62),fill='#244b44')
        d.text((58,270+i*62),line,font=font(23),fill='#244b44')
    d.line((35,545,470,545),fill='#244b44',width=3);d.text((35,575),'SYNTHETIC FACILITY  E-01',font=font(22),fill='#244b44')
    im.save(textures/'lift-info.png')
    write_json(ROOT/'docs/gangnam-walk-delivery.json',dict(status='in_progress',scope='Continuous image-localized elevator approach demonstration',
        requirements={k:'pending' for k in ['synthetic_scene_and_provenance','rgb_only_guidance','automatic_and_manual_movement','normal_loss_closed_trials','video_60_90_seconds','web_integration','regressions','portfolio_pdf_zip','github_and_public_demo']}))
    print(json.dumps(dict(mapping_views=len(mapping),length_m=length,scene=str(BASE/'scene.json'))))

if __name__=='__main__':main()
