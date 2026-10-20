# Brain takeover: what the new {{PROJECT}} brain does first

You were started as the new brain, either by the owner with the command from `brainwatch`, or because the
owner told you to take over. The old brain ran out of usage or died. Exactly one session is the brain, and
that is recorded in the brain lease (`team/brain/lease.json`). Work through the steps in order. Keep every
message to the owner short and plain.

## 1. Take the lease (first, before anything else)
- `brainlease who`. If another session holds a **fresh** lease, and neither your prompt nor the owner told
  you to take over, stop. Tell the owner in one line and do nothing else.
- Otherwise: `brainlease acquire --force --reason "takeover: <why, from the prompt>"`. Then `brainlease who`
  must show your account and session.
- From now on your tool use renews the heartbeat by itself, through the brain hook.

## 2. Catch up (read with limits)
- `team/brain_state.md`: the "Right now" section (about the first 60 lines) and "THE PLAN".
- The activity log injected at session start (or the last 60 lines of `team/activity/activity.jsonl`).
- Remote machines, if used: `ws status` (and `ws --target <name> status` for each).
- Usage: `cca list`. Brain numbers: `brainlease status`. Watch log: last 20 lines of `logs/brainwatch.log`.
- `team/brain/TAKEOVER_DUE.md`, if it is there: why the takeover was called.

## 3. The old brain
- `brainlease status` shows the old holder under `lease.previous`. Its session may still be alive, just out
  of usage. When its window resets, the brain hook warns it that it lost the lease and tells it to delete its
  crons. You cannot stop it yourself: tell the owner if it is alive, so they can close it.
- Never restart, kill or resume something the old brain's session is still running.

## 4. Recreate the session crons (they are session-only and died with the old brain)
- **Owner update tick**, every {{TICK_MINUTES}} minutes: check the jobs (runner status, activity log), usage
  (`cca list`) and the Task Board; update the board cards; send the owner a short update when something changed.
- Check with CronList that you have exactly the tick cron, and no duplicates.

## 5. The Task Board (the ticketing hub)
- Board: {{BOARD_ARTIFACT_URL}} (published by account {{BOARD_OWNER_ACCOUNT}}; only that account can update
  it. If the read fails from your account: publish the page again as a new artifact, reseed once from the
  last card export, and give the owner the new link).
- Keep it current: every job, decision and result updates its card (ArtifactData read, then update with
  `if_version`; never overwrite the owner's column, order or owner_note). A running job's card has
  `running: true`, `progress`, `progress_at`, `account`; cleared and moved when it ends. Every tick checks it.
  New work starts from the top of the owner's To do column.
- **Start from the board:** when a card carries `start_request` (or a comment "START <id> on <account>"
  arrives), follow docs/TASK_BOARD.md "Start from a card": read card + brief; check the account (cap, 5-hour
  window, API budget), the tree lock, dependencies and the Rulebook; start the worker with the brief and the
  traps; set `running` + `progress`; delete `start_request`; reply in the comment thread and resolve it. If a
  rule blocks it: the card stays In progress with `status_note: "waiting: <reason>"`, and the owner gets the
  reason in the thread and in chat.

## 6. Interrupted work
- List runs and workers with open steps; for each, check: its session is gone (or is the old brain at its
  limit); nothing it owns wrote in the last 10 minutes; no activity line for it in the last 15 minutes; no
  runner job of its own still running; brain_state does not say it was finished or cancelled on purpose.
  Resume only when all hold. When in doubt, ask the owner.
- A workflow run cannot be resumed from another session: write a short continuation script that skips the
  finished steps and puts a RESUMED note (what was done, where it stopped, what to check first) in the first
  unfinished step's prompt. Put the traps from CLAUDE.md in every job prompt.
- Background `cca <account> -p` workers: check their logs (`logs/<account>_*.jsonl`, last lines) and
  processes before you relaunch anything.

## 7. Tell the owner (one short message)
"<account> took over as brain at HH:MM because <reason>. Old brain: <alive or gone>. Resumed: <runs or none>.
Crons: back." Add one line on what you do next.

## 8. Record it
One dated line at the top of "Right now" in `brain_state.md`: the takeover, the reason, what was resumed,
and the cron ids.

## Rules that stay
- CLAUDE.md is binding: caps, pause rule, service restart rule, git rule, secrets, one model everywhere.
- When you stop being the brain on purpose, run `brainlease release`, or let the next brain take the lease
  with `--force`.
