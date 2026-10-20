#!/usr/bin/env python3
"""Build the first ArtifactData batch (seed.json) from a tasks.json. Use it ONCE per board: never reseed over a
live board, or the owner's moves, priorities and notes are lost.

tasks.json shapes accepted:
  {"tracks": [{"name": "Platform", "focus": false, "tasks": [ {task}, ... ]}, ...]}
  {"tracks": {"Platform": [ {task}, ... ]}}
  {"tracks": [{"id": "plat", "title": "Platform"}], "tasks": [{"track": "plat", ...}, ...]}
A task: id (required, unique, [A-Za-z0-9_~:@+.-]), title, status (next | doing | waiting-owner | blocked |
paused | done | pipeline), why, why_source, how [steps], done_means, depends_on [ids], last_progress,
open_questions [..], focus, status_note.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOC_ID = re.compile(r'^[A-Za-z0-9_~:@+.\-]+$')


def text(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '\n'.join(text(item) for item in value)
    if isinstance(value, dict):
        return '; '.join(f'{key}: {text(item)}' for key, item in value.items() if item is not None)
    return str(value)


def strings(value):
    if value is None or value == '':
        return []
    return [text(item) for item in (value if isinstance(value, list) else [value])]


def status_column(status):
    return {'done': 'done', 'doing': 'doing', 'review': 'review', 'waiting-owner': 'todo',
            'blocked': 'todo', 'next': 'todo', 'todo': 'todo', 'paused': 'pipeline'}.get(status, 'pipeline')


def flatten(payload, focus_track=''):
    """Accept tracks as a list or a keyed object; keep the source order."""
    tracks = payload.get('tracks', [])
    if isinstance(tracks, dict):
        tracks = [dict(value, name=key) if isinstance(value, dict)
                  else {'name': key, 'tasks': value} for key, value in tracks.items()]
    if payload.get('tasks') and not any(isinstance(t, dict) and t.get('tasks') for t in tracks):
        names = {t.get('id'): t for t in tracks if isinstance(t, dict)}
        grouped = {}
        for source in payload['tasks']:
            grouped.setdefault(source.get('track'), []).append(source)
        tracks = [dict(names.get(tid, {}), name=text((names.get(tid) or {}).get('title') or tid), tasks=items)
                  for tid, items in grouped.items()]
    result, seen = [], set()
    for track in tracks:
        name = text(track.get('name') or track.get('title') or track.get('track') or track.get('id'))
        for source in track.get('tasks', []):
            task = dict(source)
            task['track'] = text(task.get('track') or name) or 'Unassigned'
            task['focus'] = bool(task.get('focus') or track.get('focus') or
                                 (focus_track and task['track'].casefold() == focus_track.casefold()))
            task_id = task.get('id', '')
            if not isinstance(task_id, str) or not DOC_ID.fullmatch(task_id) or task_id in {'.', '..'} \
                    or len(task_id.encode()) > 200:
                raise ValueError(f'Invalid task id: {task_id!r}')
            if task_id in seen:
                raise ValueError(f'Duplicate task id: {task_id}')
            seen.add(task_id)
            result.append(task)
    return result


def build_seed(payload, focus_track='', stamp=None):
    tasks = flatten(payload, focus_track)
    tasks = sorted(tasks, key=lambda task: not task['focus'])   # stable: focus cards first, source order kept
    stamp = stamp or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    batch, order = [], {}
    for task in tasks:
        status = text(task.get('status'))
        column = status_column(status)
        index = order.get(column, 0)
        order[column] = index + 1
        why = task.get('why', '')
        why_source = task.get('why_source') or task.get('source')
        if isinstance(why, dict):
            why_source = why_source or {k: v for k, v in why.items() if k not in {'text', 'decision', 'reason'}}
            why = why.get('text') or why.get('decision') or why.get('reason') or text(why)
        data = dict(
            title=text(task.get('title')), track=task['track'], column=column,
            order=index, status_note=text(task.get('status_note') or task.get('note') or status),
            why=text(why), why_source=text(why_source), how=strings(task.get('how')),
            done_means=text(task.get('done_means')), depends_on=strings(task.get('depends_on')),
            last_progress=text(task.get('last_progress')), open_questions=strings(task.get('open_questions')),
            owner_note='', paused=status == 'paused' or bool(task.get('paused')),
            focus=task['focus'], brief=f"briefs/{task['id']}.md", updated_at=stamp, updated_by=None)
        batch.append(dict(op='set', collection='cards', doc_id=task['id'], data=data))
    return batch


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path, help='tasks.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'seed.json')
    parser.add_argument('--focus-track', default='', help='track whose cards get the FOCUS tag')
    args = parser.parse_args()
    if not args.source.exists():
        parser.exit(1, f'Tasks are not ready: {args.source}. No seed file changed.\n')
    batch = build_seed(json.loads(args.source.read_text(encoding='utf-8')), args.focus_track)
    args.output.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(batch)} cards to {args.output}')


if __name__ == '__main__':
    main()
