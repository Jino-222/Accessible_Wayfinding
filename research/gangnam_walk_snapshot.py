"""Preserve exact scene, code and map identity before a named run."""
import argparse,hashlib,re,shutil
from .paths import ROOT,ASSETS,write_json

def main(run):
    if not re.fullmatch(r'[a-z0-9_-]{1,48}',run):raise ValueError('Invalid run name')
    target=ASSETS/'gangnam-walk/runs'/run/'source';target.mkdir(parents=True,exist_ok=False)
    files=list(ROOT.glob('research/gangnam_walk*.py'))+list(ROOT.glob('unity/AccessibleStation/Assets/**/GangnamWalk*.cs'))
    files+=list(ROOT.glob('unity/AccessibleStation/Assets/StreamingAssets/GangnamWalk/*.png'))
    files+=[ROOT/n for n in ['unity/AccessibleStation/Assets/StreamingAssets/gangnam-walk.json','research/localizer.py','research/geometry.py','research/gangnam.py','research/build_rgbd_map.py','research/requirements-gangnam-walk.txt','unity/AccessibleStation/Packages/manifest.json']]
    hashes={}
    for p in files:
        name=p.relative_to(ROOT).as_posix();dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    write_json(target/'manifest.json',dict(recorded='before execution',files=hashes,map_sha256=hashlib.sha256((ASSETS/'gangnam-walk/map/map.npz').read_bytes()).hexdigest()))
    print('Preserved',len(files),'source/configuration files')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);main(parser.parse_args().run)
