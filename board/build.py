#!/usr/bin/env python3
"""Build the publish bundle for the Task Board Artifact.

  python3 board/build.py --config board.config.json --tasks tasks.json --briefs briefs/ --out dist/
                         [--goals goals.json] [--media media.json] [--models models3d/]

Writes into --out:
  board.html    the page, with board.config.json embedded between the BOARD_CONFIG markers
  seed.json     the first ArtifactData batch (make_seed.py); send it ONCE, right after the first publish
  briefs.json   every briefs/<id>.md in one file {"briefs/<id>.md": markdown} (the page reads only this)
  goals.json / media.json / models3d/   copied when given (Goals, Media and 3D tabs; all optional)
Nothing is uploaded: PUBLISH.md says how the brain publishes the folder as an Artifact.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import make_seed  # noqa: E402

START, END = '/* BOARD_CONFIG_START */', '/* BOARD_CONFIG_END */'
KEYS = {'title': str, 'eyebrow': str, 'intro': str, 'focusTrack': str, 'tabs': dict, 'assignees': list,
        'goalGroups': list, 'modelGroups': list, 'storageKey': str}
BRIEF_NAME = re.compile(r'^[A-Za-z0-9_~:@+.\-]+\.md$')


def check_config(cfg):
    if not isinstance(cfg, dict):
        raise SystemExit('board config must be a JSON object')
    for key, kind in KEYS.items():
        if key in cfg and not isinstance(cfg[key], kind):
            raise SystemExit(f'board config: "{key}" must be {kind.__name__}')
    unknown = sorted(set(cfg) - set(KEYS) - {'_comment'})
    if unknown:
        raise SystemExit(f'board config: unknown keys {unknown}')
    for item in cfg.get('assignees', []):
        if not isinstance(item, dict) or not isinstance(item.get('value'), str) or not item['value'].strip():
            raise SystemExit('board config: every assignee needs a non-empty "value"')
    return {k: v for k, v in cfg.items() if k != '_comment'}


def embed(page, cfg):
    a, b = page.find(START), page.find(END)
    if a < 0 or b < a:
        raise SystemExit('board.html: BOARD_CONFIG markers not found')
    body = json.dumps(cfg, ensure_ascii=False, indent=2).replace('</', '<\\/')
    return page[:a + len(START)] + body + page[b:]


def bundle_briefs(folder):
    out = {}
    if folder and folder.is_dir():
        for path in sorted(folder.glob('*.md')):
            if BRIEF_NAME.fullmatch(path.name):
                out['briefs/' + path.name] = path.read_text(encoding='utf-8')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--tasks', type=Path, required=True)
    ap.add_argument('--briefs', type=Path)
    ap.add_argument('--goals', type=Path)
    ap.add_argument('--media', type=Path)
    ap.add_argument('--models', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    cfg = check_config(json.loads(a.config.read_text(encoding='utf-8')))
    a.out.mkdir(parents=True, exist_ok=True)
    page = (ROOT / 'board.html').read_text(encoding='utf-8')
    with open(a.out / 'board.html', 'w', encoding='utf-8', newline='\n') as f:
        f.write(embed(page, cfg))
    seed = make_seed.build_seed(json.loads(a.tasks.read_text(encoding='utf-8')), cfg.get('focusTrack', ''))
    (a.out / 'seed.json').write_text(json.dumps(seed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    briefs = bundle_briefs(a.briefs)
    missing = [c['doc_id'] for c in seed if c['data']['brief'] not in briefs]
    (a.out / 'briefs.json').write_text(json.dumps(briefs, ensure_ascii=False) + '\n', encoding='utf-8')
    for name, src in (('goals.json', a.goals), ('media.json', a.media)):
        if src:
            json.loads(src.read_text(encoding='utf-8'))   # must be valid JSON
            shutil.copyfile(src, a.out / name)
    if a.models:
        shutil.copytree(a.models, a.out / 'models3d', dirs_exist_ok=True)
    print(f'board.html, seed.json ({len(seed)} cards), briefs.json ({len(briefs)} briefs) in {a.out}')
    if missing:
        print('cards without a brief yet (the page says "Brief not written yet"): ' + ', '.join(missing))


if __name__ == '__main__':
    main()
