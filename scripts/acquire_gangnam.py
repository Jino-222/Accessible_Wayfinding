"""Fetch official B2 archives, verify checksums, and extract without path traversal.

Run: python -m scripts.acquire_gangnam --parts mapping validation
Raw and extracted files are cached outside OneDrive by research.paths.ASSETS.
No original images or derived visuals are uploaded by this command.
"""
import argparse
import hashlib
import json
import re
import tarfile
import time
from pathlib import Path
import requests
from research.paths import ASSETS, ROOT, write_json

BASE = 'https://download.europe.naverlabs.com/kapture/'
LICENSE = 'GangnamStation_LICENSE.txt'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def acquire(name, folder, session, expected=None):
    target=folder/name
    if target.exists() and (expected is None or digest(target)==expected):
        return target
    partial=folder/(name+'.part')
    url=BASE+name
    for attempt in range(5):
        start=partial.stat().st_size if partial.exists() else 0
        try:
            with session.get(url, headers={'Range':f'bytes={start}-'} if start else {},
                             stream=True, timeout=(20,90)) as response:
                response.raise_for_status()
                if response.status_code==206:
                    header=response.headers.get('Content-Range','')
                    if not header.startswith(f'bytes {start}-'):
                        raise ValueError('Server returned a different byte range')
                    mode='ab'
                else:
                    mode='wb';start=0
                total=int(response.headers.get('Content-Length',0))+start
                done=start;reported=time.monotonic()
                with partial.open(mode) as stream:
                    for chunk in response.iter_content(2*1024*1024):
                        if chunk:stream.write(chunk);done+=len(chunk)
                        if time.monotonic()-reported>20:
                            print(json.dumps(dict(file=name,received=done,total=total)),flush=True)
                            reported=time.monotonic()
            if expected and digest(partial)!=expected:
                raise ValueError(f'Checksum mismatch: {name}; .part retained for inspection')
            partial.replace(target)
            return target
        except (requests.ConnectionError, requests.Timeout):
            if attempt==4:raise
            time.sleep(min(2**attempt,10))
    raise RuntimeError('Download retries exhausted')


def extract(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    resolved=destination.resolve()
    count=0
    with tarfile.open(archive,'r:gz') as bundle:
        for member in bundle:
            output=(destination/member.name).resolve()
            if not output.is_relative_to(resolved) or member.issym() or member.islnk():
                raise ValueError(f'Unsafe archive member: {member.name}')
            if not (member.isfile() or member.isdir()):
                raise ValueError(f'Unsupported archive member: {member.name}')
            bundle.extract(member,destination,filter='data')
            count+=1
    return count


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parts',nargs='+',choices=['mapping','validation','test'],default=['mapping','validation'])
    parser.add_argument('--metadata-only',action='store_true')
    parser.add_argument('--skip-extract',action='store_true')
    args=parser.parse_args()
    folder=ASSETS/'downloads';folder.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    license_path=acquire(LICENSE,folder,session)
    report_path=ROOT/'docs/evidence/ar-data-acquisition.json'
    report=json.loads(report_path.read_text('utf-8')) if report_path.exists() else dict(dataset='GangnamStation B2',files={})
    report.update(source=BASE,asset_root=str(ASSETS),license=dict(file=str(license_path),sha256=digest(license_path),
        use='local noncommercial research; modified visual redistribution not authorized by this script'))
    for part in args.parts:
        name=f'GangnamStation_B2_release_{part}.tar.gz'
        checksum=acquire(name+'.sha256sum',folder,session)
        expected=checksum.read_text('utf-8').split()[0]
        if not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Invalid official checksum')
        record=dict(url=BASE+name,expected_sha256=expected,checksum_file=str(checksum),status='metadata_verified')
        old=report['files'].get(part,{})
        if old.get('status')=='extracted' and old.get('expected_sha256')==expected:
            record=old
        report['files'][part]=record;write_json(report_path,report)
        print(json.dumps(dict(part=part,status=record['status'])),flush=True)
        if args.metadata_only:continue
        archive=acquire(name,folder,session,expected)
        record.update(status='archive_verified',archive=str(archive),bytes=archive.stat().st_size,sha256=digest(archive))
        write_json(report_path,report)
        if not args.skip_extract:
            marker=ASSETS/'gangnam_b2'/f'.{part}.extracted.json'
            if marker.exists() and json.loads(marker.read_text('utf-8')).get('sha256')==expected:
                extracted=json.loads(marker.read_text('utf-8'))
            else:
                extracted=dict(sha256=expected,members=extract(archive,ASSETS/'gangnam_b2'))
                write_json(marker,extracted)
            record.update(status='extracted',members=extracted['members'],extract_root=str(ASSETS/'gangnam_b2'))
            write_json(report_path,report)
        print(json.dumps(dict(part=part,status=record['status'],bytes=record['bytes'])),flush=True)


if __name__=='__main__':main()
