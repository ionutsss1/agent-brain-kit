# Agent Brain Kit

**One brain, many hands, nothing forgotten.**

A ready-made way to run a team of AI agents on real, long projects. One lead agent plans the work, hands out tasks and checks every result. Worker agents on separate accounts do the work. A rulebook you approve decides what "right" means. A live task board shows who is doing what, right now.

## What you get
- **One brain.** A single lead session plans, delegates and reviews. When its account runs low, it hands over to another one without losing the thread.
- **Workers across accounts.** Each account has its own usage cap, and jobs go where there's room. A paid-API runner has a budget per job and in total.
- **A rulebook.** Every owner decision is dated, and the newest one wins. Jobs follow the book and never invent rules.
- **A task board.** Cards carry a full brief, a live "Running now" tag and the account doing the work. You drag cards to set priority, and you can assign and start a task from its card.
- **A paper trail.** Every hand-off and result is logged. The owner is only ever quoted in their own words.
- **Review before you see it.** Nothing reaches you until the brain has checked it against your rules.

**For** anyone directing AI agents on months-long work who wants clarity instead of chaos.

## In practice
- An **owner-approved Rulebook** governs every job: no rule enters a job unless it is in the book.
- A **Task Board** (a Claude Artifact with a shared database) is the ticketing hub: the owner orders the work
  and presses "Assign and start"; the brain keeps every card current.
- **Every hand-off is logged** (agents, workflows, messages, Codex, workers, remote jobs), and every new
  session sees the last 40 lines before it does anything.
- **Review before anything reaches the owner:** the brain opens every result, checks the tests and the
  claims, and sends its own verdict, or a fix job.
- **One brain at a time** through a lease; when its account runs out, a watcher names the next account and
  prints the takeover command.
- **Caps and pacing per account**, a pause rule when all are at their caps, and a capped runner for paid jobs.

## The flow
owner decision -> Rulebook -> card -> brief -> worker prompt -> result -> brain review -> card update -> owner

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the diagram and every part.

## What is in the box
| Folder | Contents |
|---|---|
| `bin/` | `cca` (start Claude Code as an account; `cca list`), `brainlease`, `brainwatch`, `apijob`, `brainlib.py`, `kitconfig.py` |
| `hooks/` | `activity_log.py`, `brain_hook.py`, `statusline.py`, `path_guard.py` |
| `settings/` | Claude Code settings examples: per account (status line + guard) and for the team folder (activity + brain hooks) |
| `config/` | `kit.example.json`: the one config file (accounts, caps, reset days, paths, API budget, guard rules) |
| `board/` | The Task Board page, build/seed/brief tools, example data, tests, PUBLISH.md |
| `templates/` | CLAUDE.md, RULEBOOK, decisions questionnaire, BRIEF, TAKEOVER, brain_state, worker prompt, tree lock, memory examples |
| `docs/` | ARCHITECTURE, ROLES, ACCOUNTS_AND_CAPS, TASK_BOARD, RULEBOOK, REVIEW_RULES, PROMPTS |
| `optional/remote-runner/` | `ws` + `ws_daemon.py`: signed jobs on another machine through a shared folder |
| `optional/mcp-policy-server/` | Example MCP server: bounded tools behind one policy file |
| `tools/` | `selftest.sh` (all offline checks), `scrub_check.py` (white-label check) |

## Requirements
- macOS or Linux, `bash`, Python 3.9+ (standard library only), `node` 18+ for the board tests.
- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) and one or more Claude plan accounts.
- For the Task Board: a Claude plan where Artifacts can use the shared database, user identity and comments.
- Optional: Codex CLI (reviews, code writing), a paid Anthropic API key (capped jobs), a second machine with a
  shared folder (remote runner), `screen` (keeps takeover sessions alive).

## Quick start
```sh
git clone <this repo> agent-brain-kit && cd agent-brain-kit
./setup.sh --home ~/agent-brain-kit-home      # folders, config, settings, team files; no keys
export AGENT_KIT_HOME=~/agent-brain-kit-home
export PATH="$PWD/bin:$PATH"
$EDITOR $AGENT_KIT_HOME/config/kit.json        # your accounts, caps, reset days, guard rules
cca main                                       # first time: /login; this session becomes the brain:
#   brainlease acquire --reason "first brain"
cca list                                       # usage, cap, pace, today's allowance per account
bash tools/selftest.sh                         # every offline check
```
Then fill the placeholders in `team/CLAUDE.md`, publish the board (`board/PUBLISH.md`) and schedule
`brainwatch` (`./setup.sh --print-launchd` on macOS; a cron line on Linux).

## Keys and secrets
The kit never stores a key. Keys live in the OS keychain or in files the owner creates under
`$AGENT_KIT_HOME/secrets` (mode 600); scripts only read them. `path_guard.py` refuses reads of the secret
paths and names in the config, and commands that name them.

## Checks
`bash tools/selftest.sh` runs: `bash -n` on the shell scripts, a compile of every Python file, `--help` and
dry runs of every tool, the hooks on sample payloads, the remote runner end to end, the MCP policy tests, the
three board test files, a board build, and the white-label scrub (`tools/scrub_check.py`, must report 0 hits).
