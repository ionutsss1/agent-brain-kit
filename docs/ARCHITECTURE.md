# Architecture

One **brain** session plans and reviews. **Workers** do the jobs, on several Claude accounts, on Codex, or on
a paid API key. An owner-approved **Rulebook** governs every job. The **Task Board** Artifact is the
ticketing hub. Every hand-off is **logged**. Nothing reaches the owner before the brain has **reviewed** it.

## The flow

```mermaid
flowchart LR
  O[Owner] -- decision (questionnaire) --> R[Rulebook §10]
  O -- order + "Assign and start" --> B[(Task Board)]
  R --> C[Card]
  B --> C
  C --> BR[Brief: 12 sections]
  BR --> P[Worker prompt + traps]
  P --> W{{Worker: Claude account / Codex / API key}}
  W --> RES[RESULT.md + STATE.txt READY]
  RES --> REV[Brain review: open it, test it, judge it]
  REV -- fails the bar --> P
  REV -- passes --> UPD[Card update]
  UPD --> O
```

In words: owner decision -> Rulebook -> card -> brief -> worker prompt -> result -> brain review -> card
update -> owner.

## The parts

```
                       ┌────────────────────────── planning machine ───────────────────────────┐
 owner ── chat ──────▶ │ brain session (cca main)   ◀── SessionStart: lease + last 40 activity   │
   │                   │   │  brainlease (lease.json, heartbeat via brain_hook --renew)          │
   │                   │   ├─▶ cca second -p ...   worker   ─┐                                    │
   │                   │   ├─▶ codex exec ...      worker    ├─▶ activity_log.py ─▶ activity.jsonl │
   │                   │   ├─▶ apijob ...          worker    │   (send/back for every hand-off)  │
   │                   │   └─▶ ws run ...          remote ───┘                                    │
   │                   │  statusline.py ─▶ ledger/<account>.json (5h / week %)                    │
   │                   │  path_guard.py: secrets, forbidden commands, remote-only paths          │
   │                   │  brainwatch (every 2 min, no Claude usage): stale/capped brain ─▶ alert  │
   │                   └──────────────────────────────────────────────────────────────────────────┘
   └── Task Board Artifact (cards db, comments "START <id> on <account>") ◀─▶ brain (ArtifactData)
       optional: remote machine ── ws_daemon.py ◀── shared spool folder (signed requests)
```

| Piece | File | Job |
|---|---|---|
| Config | `config/kit.json` | Accounts (caps, reset days), paths, API budget, guard rules, runner name. One file. |
| Account launcher | `bin/cca` | Starts Claude Code as one account (its own config folder); `cca list` shows usage, cap, pace, daily allowance. |
| Brain lease | `bin/brainlease`, `bin/brainlib.py` | Exactly one brain. Fresh / idle / stale / released. Takeover needs `--force` (owner's word). |
| Brain watch | `bin/brainwatch` | Runs every 2 min from launchd/cron. Names the takeover account and prints the command; pauses everything when every account is at its cap. Never starts a session itself. |
| API jobs | `bin/apijob` | One `-p` job on the paid key with `--max-budget-usd`, refused past the total; cost ledger. |
| Hooks | `hooks/*.py` | Activity log, brain lease guard + heartbeat, status line ledger, path/secret/command guard. |
| Board | `board/` | The Artifact page, seed + brief bundle tools, tests. |
| Remote runner | `optional/remote-runner/` | Signed jobs to another machine through a shared folder. |
| MCP policy server | `optional/mcp-policy-server/` | Example of bounded tools with one policy file. |

## Folders at run time (`{{KIT_HOME}}`, set in the config)
```
{{KIT_HOME}}/
  accounts/<account>/     CLAUDE_CONFIG_DIR per account (login, settings.json, transcripts, memory)
  team/                   where sessions start: CLAUDE.md, brain_state.md, RULEBOOK.md, TREE_LOCK.md
    .claude/settings.json activity + brain hooks
    brain/                lease.json, TAKEOVER.md, TAKEOVER_DUE.md, PAUSED.md, watch_state.json
    activity/activity.jsonl
    board/                board.config.json, tasks.json, briefs/, dist/
    jobs/<job>/           STATE.txt, RESULT.md per worker
  ledger/                 <account>.json usage, api_spend.jsonl
  logs/                   brainwatch.log, <account>_*.jsonl worker streams, mcp_audit.jsonl
  secrets/                mode 700; key files the owner creates (mode 600); never read by agents
```

## Scheduling brainwatch
- macOS: a LaunchAgent with `StartInterval` 120 running `<repo>/bin/brainwatch` (print the plist with
  `setup.sh --print-launchd`).
- Linux: `*/2 * * * * <repo>/bin/brainwatch >> {{KIT_HOME}}/logs/brainwatch.log 2>&1`.
brainwatch never launches a Claude session: an unattended launcher is a safety risk. It writes
`TAKEOVER_DUE.md` with the exact command and sends a desktop notification; the owner runs the command.

## Failure modes it handles
| Event | What happens |
|---|---|
| The brain's account hits its 5-hour or week cap | brainwatch sees the quiet capped holder, names the account with most headroom, prints the takeover command. |
| The brain's process dies | Heartbeat goes stale and the process is gone: same takeover alert. |
| Every account is at its cap | `PAUSED.md`, the pause command (for example `ws pause`), a notification; nothing resumes until the owner runs `brainwatch --resume`. |
| A second session tries to launch jobs | The guard hook reminds it that it is not the brain (once per 10 min). |
| A worker is cut off mid-job | Its STATE.txt has dated lines; no READY line means "continue from the last part". |
| A job reads a secret or pushes git | path_guard refuses it with the reason. |
