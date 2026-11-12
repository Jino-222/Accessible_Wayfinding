"""Large research assets stay outside the OneDrive source directory."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(os.environ.get('WAYFINDING_RESEARCH_DATA',
    Path(os.environ.get('LOCALAPPDATA', Path.home()/'.cache'))/'AccessibleWayfinding'/'research'))


def write_json(path, value):
    import json
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)
