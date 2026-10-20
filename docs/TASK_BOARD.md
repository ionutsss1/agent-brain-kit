# Task Board

The board is the project's ticketing hub: one Claude Artifact page with a shared database. The owner sets the
order and starts work; the brain keeps every card current. Files: `board/` (page, tools, tests, PUBLISH.md).

## Columns
| Column id | Name | Meaning |
|---|---|---|
| `pipeline` | Pipeline | Known work, not ready or paused. |
| `todo` | To do | Ready. **The owner's order is the priority: top first.** |
| `doing` | In progress | Started (or a start was requested). |
| `review` | In review | A result waits for the brain's or the owner's review. |
| `done` | Done | Accepted. |

Higher in a column = higher priority. The page moves cards by drag (desktop), by the "Move to" select and the
arrows (phone, keyboard); every move renumbers the affected columns.

## Card schema (collection `cards`, document id = task id)
| Field | Type | Written by | Meaning |
|---|---|---|---|
| `title` | text | seed / brain | Short task name. |
| `track` | text | seed | Group (filter chips; `focusTrack` gets a FOCUS chip). |
| `column` | id | owner / brain | One of the columns above. |
| `order` | number | owner / brain | Position in its column, 0 = top. |
| `status_note` | text | brain | One line: where it stands, or `waiting: <reason>`. |
| `why` / `why_source` | text | seed / brain | Why it matters, and the dated source. |
| `how` | list | seed / brain | Steps. |
| `done_means` | text | seed / brain | Acceptance. |
| `depends_on` | list of ids | seed / brain | Other cards. |
| `last_progress` | text | brain | Dated last progress line. |
| `open_questions` | list | brain | Owner decisions it waits on ("Waiting on me" filter). |
| `owner_note` | text | **owner only** | The owner's direction. The brain reads it, never overwrites it. |
| `paused` / `focus` | bool | seed / brain | Tags. |
| `brief` | `briefs/<id>.md` | seed | Its key in the published `briefs.json`. |
| `running` | bool | brain | A job runs now ("Running now" tag, live dot). |
| `progress` / `progress_at` | text | brain | One live line and its real local time. |
| `account` | text | page / brain | Who does it: "main · worker", "main · brain", "Codex", "API key"... |
| `start_request` | `{account, at, sent}` | page | Set by "Assign and start"; removed by the brain when it acts. |
| `updated_at` / `updated_by` | text | page | UTC time and an opaque viewer id (never a name or email). |

## The brief bundle
Every card's brief is a 12-section Markdown hand-off (`templates/BRIEF.template.md`). All briefs ship in one
published file, `briefs.json` (`{"briefs/<id>.md": "<markdown>"}`), built by `board/build.py`. One file keeps
the published file count low. The page renders it safely (no raw HTML, safe links) and has "Copy brief".

## Publish (the brain)
1. `python3 board/build.py --config ... --tasks ... --briefs ... --out dist/` (see board/PUBLISH.md).
2. Publish `dist/board.html` as the Artifact page with capabilities `{"db": {}, "user": {}, "comments": {}}`;
   publish `briefs.json`, `goals.json`, `media.json` beside it.
3. First time only: send `seed.json` through ArtifactData (`set` per card). Never reseed a live board.
4. Write the board's link and the publishing account into TAKEOVER.md: only that account can update it.

## Keeping it current (every tick and every event)
- Read before write: ArtifactData read, then update with `if_version`, merging only the fields you change.
- Never overwrite the owner's `column`, `order` or `owner_note` unless they asked.
- Job starts: `column: doing`, `running: true`, `progress`, `progress_at`, `account`.
- Job ends: clear `running`, write `last_progress`, move to `review` (result waits) or `done` (accepted).
- Decision recorded: update `why` / `status_note`, remove the answered `open_questions`.
- New work: from the top of the owner's To do column.

## Start from a card (the procedure)
The card sheet has **Assign and start** (choices from `assignees` in board.config.json). Pressing Start
writes `column: doing`, `account`, `start_request {account, at, sent}` and `status_note: "start requested:
..."`, and, when the comments capability is connected, sends the brain a comment `START <id> on <account>:
<title>`. The brain then:
1. Reads the card and its brief.
2. Checks the account: its cap and pace, its 5-hour window, whether a fallback account is open, the API
   budget (per job and total). Checks the tree lock (one code worker per shared tree), the dependencies, and
   the owner rules (Rulebook; the work split).
3. Starts the worker with the brief and the traps (`cca <account> -p ... --model opus`, `codex exec`, or
   `apijob`), a process waiter, and an activity line.
4. Sets `running: true` + `progress` with the real time; removes `start_request` with `{"__delete__": true}`.
5. Replies in the comment thread what started (or why it waits and what it needs) and resolves the thread.
If a rule blocks it: the card stays In progress with `status_note: "waiting: <reason>"`, and the owner gets
the reason in the thread and in chat. Every tick also picks up any card with a `start_request` (a comment can
be missed, or the brain was not connected: `sent: false`).

## The other tabs
- **Media** (`media.json`): `{"items": [{"id", "kind": "image"|"video", "title", "caption", "topic", "date",
  "file", "poster", "duration_s", "orig_path"}]}`; files must be same-origin. Grouped by month; filters; viewer.
- **Goals** (`goals.json`): `{"generated", "now", "goals": [{"id", "title", "group", "status", "progress",
  "why", "where_we_are", "cards": [ids], "decisions": [{"date", "text", "source"}], "subgoals": [...],
  "sources": [...]}]}`. Groups come from `goalGroups`; cards link back to the Tasks tab.
- **3D** (optional, off by default): `models3d/index.json` + bundles of base64 GLB models, lazy-loaded per
  bundle, orbit viewer with a 1.8 m figure and a 1 m grid. Turn it on with `"tabs": {"3d": true}`.
