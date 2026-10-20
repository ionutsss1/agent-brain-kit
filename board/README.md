# Task Board

The ticketing hub: one Artifact page where the owner orders the work and the brain keeps every card current.

| File | What it is |
|---|---|
| `board.html` | The page. Tabs: Tasks (kanban: Pipeline, To do, In progress, In review, Done), Media, Goals, and an optional 3D tab (off by default). No project data inside. |
| `build.py` | Embeds `board.config.json` into the page and writes the publish bundle (`dist/`). |
| `make_seed.py` | Turns a `tasks.json` into the first database batch (`seed.json`). Once per board. |
| `make_brief_stub.py` | Writes brief stubs (12 headings, `NEEDS DETAIL` gaps) for cards without a brief. |
| `example/` | `board.config.json`, `tasks.json` (5 neutral cards), `goals.json`, `briefs/EX01.md`. |
| `tests/` | `node tests/test_board.cjs`, `test_runtime.cjs` (whole page on a mocked platform), `test_3d.cjs`. |
| `PUBLISH.md` | How the brain publishes and updates it. |

## Board settings (`board.config.json`)
| Key | Meaning |
|---|---|
| `title`, `eyebrow`, `intro` | Header text. |
| `focusTrack` | A track shown first with a FOCUS chip; `""` for none. |
| `tabs` | `{"media": true, "goals": true, "3d": false}`. Tasks is always on. |
| `assignees` | The "Assign and start" choices: `[{"value": "main · worker", "label": "Main · worker"}, ...]`. The value is what the brain reads. |
| `goalGroups` | Goal sections, in display order. A goal with another group is not shown. |
| `modelGroups` | 3D picker groups. |
| `storageKey` | Browser key for each viewer's private filters. |

## Card fields
`title, track, column, order, status_note, why, why_source, how[], done_means, depends_on[], last_progress,
open_questions[], owner_note, paused, focus, brief, updated_at, updated_by` from the seed; the brain adds
`running, progress, progress_at, account, start_request` while work runs. Full schema: docs/TASK_BOARD.md.

Icons are Material Symbols only.
