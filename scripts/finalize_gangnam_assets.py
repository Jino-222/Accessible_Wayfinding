"""Join attribution manifests and verify public images against their recorded hashes."""
import hashlib
import json
from research.paths import ROOT, write_json


def main():
    web = ROOT / 'web/gangnam'
    read = lambda name: json.loads((web / 'data' / name).read_text('utf-8'))
    rights = read('asset-rights.json')
    entries = {r['file']: r for r in rights['assets']}
    for name in ('corridor.json', 'corridor-observations.json'):
        for r in read(name)['rights']:
            entries[r['file']] = r
    for r in entries.values():
        path = (web / r['file']).resolve()
        assert path.is_relative_to(web.resolve()) and path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == r['sha256']
        assert r['modified'] is False
    actual = {p.relative_to(web).as_posix() for p in (web/'assets/naver-originals').glob('*.jpg')}
    assert actual == set(entries), 'Unattributed or missing images'
    rights.update(assets=sorted(entries.values(), key=lambda r: r['file']),
                  count=len(entries), original_bytes_verified=True,
                  scope='Noncommercial educational demo. Original photographs displayed separately from authored diagrams. No provider endorsement.')
    write_json(web/'data/asset-rights.json', rights)
    print(json.dumps({'images': len(entries), 'bytes': sum((web/r['file']).stat().st_size for r in entries.values())}))


if __name__ == '__main__': main()
