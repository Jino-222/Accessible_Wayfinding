"""Build the new map without altering the previous generic station experiment."""
import json
from .paths import ASSETS
from .build_rgbd_map import build

def main():
    base=ASSETS/'gangnam-walk/mapping'
    records=json.loads((base/'manifest.json').read_text('utf-8'))['records']
    views=[]
    for r in records:
        if r['split']!='mapping':raise ValueError('Non-mapping view found')
        views.append(dict(id=r['id'],path=str(base/r['image']),
            camera=dict(model='PINHOLE',width=r['width'],height=r['height'],params=[r[k] for k in ('fx','fy','cx','cy')]),
            pose=[r['camera_to_world'][i:i+4] for i in range(0,16,4)],depth_path=str(base/r['depth']),depth_shape=(r['height'],r['width'])))
    build(views,ASSETS/'gangnam-walk/map')

if __name__=='__main__':main()
