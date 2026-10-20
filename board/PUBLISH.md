# Publishing the Task Board

The board is one HTML page published as a Claude Artifact, with a shared database (cards), viewer identity
(user) and comments (the "Assign and start" message to the brain). Only the brain publishes it.

## Needs
- A Claude plan where Artifacts can use the shared database, user identity and comments.
- `python3` and, for the tests, `node` (18 or newer).

## 1. Build the bundle
```sh
python3 board/build.py --config board/board.config.json --tasks board/tasks.json \
  --briefs board/briefs --goals board/goals.json --out board/dist
```
Start from `board/example/` (5 neutral cards, one full brief, a small goals file). Media and 3D files are
optional: `--media media.json` and `--models models3d/` (folder with `index.json` + bundles).

## 2. Test before publishing
```sh
node board/tests/test_board.cjs && node board/tests/test_runtime.cjs && node board/tests/test_3d.cjs
```

## 3. Publish (the brain, in a Claude session with the Artifact tool)
1. Publish `dist/board.html` as the page content. Do not add `<html>`, `<head>` or `<body>` tags.
2. Capabilities: `{"db": {}, "user": {}, "comments": {}}`.
3. Publish `briefs.json`, `goals.json`, `media.json` (and `models3d/`) beside the page as same-origin files.
   Keep the file count low: one `briefs.json` instead of one file per brief.
4. FIRST publish only: send `seed.json` through ArtifactData to the artifact's database, once. Each entry is
   `{op: "set", collection: "cards", doc_id: <id>, data: <card>}`.
5. Later publishes: same artifact URL (`url` set), never reseed. An artifact can only be read and updated by
   the account that published it: write that account down in TAKEOVER.md.

## 4. Reading and updating cards (the brain)
- Read: ArtifactData list collection `cards`; group by `column`; sort by numeric `order` ascending. The top
  of the owner's To do column is the next task.
- Update: read the current card first, then update with `if_version`, and merge ONLY the fields you mean to
  change. Never overwrite the owner's `column`, `order` or `owner_note` unless the owner asked.
- A running job: `running: true`, `progress` (one line), `progress_at` (real local time), `account`.
  When it ends: clear `running`, move the card, write `last_progress`.
- A start request from the page: `start_request: {account, at, sent}`; after acting on it, remove it with
  `{"__delete__": true}`. See docs/TASK_BOARD.md for the whole start-from-card procedure.

## 5. Known limits
- Last writer wins: two people moving cards at the same instant can interleave.
- The tests mock the platform; check drag, touch, clipboard and the live database once on the published page.
