#!/usr/bin/env python3
"""Write a brief stub briefs/<id>.md for every task in tasks.json that has no brief yet. Existing briefs are
never touched. A stub is NOT an executable hand-off: every NEEDS DETAIL must be resolved by a brief job
(templates/BRIEF.template.md) before a worker starts from it.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_seed  # noqa: E402

HEADINGS = ['1 Goal', '2 Owner decisions', '3 Rulebook sections that govern it', '4 Current state + proof so far',
            '5 Method', '6 Code + files', '7 Data + assets', '8 Dependencies', '9 Traps', '10 Done means',
            '11 Open questions for the owner', '12 Start here']


def stub(task):
    t = make_seed.text
    known = {
        '1 Goal': t(task.get('why')) or 'NEEDS DETAIL: the intended result and scope.',
        '2 Owner decisions': 'NEEDS DETAIL: quote the owner only verbatim from their own messages, dated, with the '
                             'source; anything else is a "Summary:" line.',
        '5 Method': '\n'.join(f'{i}. {step}' for i, step in enumerate(make_seed.strings(task.get('how')), 1))
                    or 'NEEDS DETAIL: numbered steps with who, tool, inputs, expected output, stop conditions.',
        '8 Dependencies': ', '.join(make_seed.strings(task.get('depends_on'))) or 'None recorded.',
        '10 Done means': t(task.get('done_means')) or 'NEEDS DETAIL: tests with exact commands and the proof.',
        '11 Open questions for the owner': '\n'.join('- ' + q for q in make_seed.strings(task.get('open_questions')))
                                           or 'None recorded.',
    }
    parts = [f"# {task['id']}: {t(task.get('title'))}", '', 'STUB: not an executable hand-off until every NEEDS '
             'DETAIL is resolved.', '']
    for h in HEADINGS:
        parts += [f'## {h}', known.get(h, 'NEEDS DETAIL'), '']
    return '\n'.join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path, help='tasks.json')
    ap.add_argument('--briefs', type=Path, default=Path(__file__).resolve().parent / 'briefs')
    a = ap.parse_args()
    a.briefs.mkdir(parents=True, exist_ok=True)
    made = 0
    for task in make_seed.flatten(json.loads(a.source.read_text(encoding='utf-8'))):
        path = a.briefs / f"{task['id']}.md"
        if not path.exists():
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(stub(task))
            made += 1
    print(f'{made} stubs written in {a.briefs}; existing briefs kept')


if __name__ == '__main__':
    main()
