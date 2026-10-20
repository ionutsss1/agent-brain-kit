# Accounts and caps

The kit spreads work across several Claude plan accounts, Codex and a paid API key, and keeps each within
the owner's limits. All numbers come from `config/kit.json`.

## Accounts in the config
```json
{"name": "main",   "kind": "claude", "role": "brain and workers", "cap_percent": 95, "week_reset": "Tue 10:00"}
{"name": "second", "kind": "claude", "role": "workers; brain while main rests", "cap_percent": 95}
{"name": "shared", "kind": "claude", "role": "fallback", "cap_percent": 40, "fallback": true,
 "cap_schedule": [{"until": "2026-02-01T00:00", "cap": 60}]}
{"name": "api",    "kind": "api-key", "role": "paid API jobs"}
```
- `cap_percent`: the most of its week the project may use on this account.
- `cap_schedule`: dated owner limits that override `cap_percent` until a date (first match wins). Use it when
  the owner says "up to 60% until Friday": the date is written down, not remembered.
- `week_reset`: for people; the real reset time comes from the usage reading.
- Each account has its own folder `{{KIT_HOME}}/accounts/<name>` (its own login). Start it with `cca <name>`.

## Where the numbers come from
- `hooks/statusline.py` (the status line of every session) writes `ledger/<account>.json`: the 5-hour and
  week usage and their reset times (plan logins report them after the session's first answer).
- Background workers (`cca <account> -p --output-format stream-json`) log to `logs/<account>_*.jsonl`; their
  rate-limit events are newer readings, and `brainlib.usage()` prefers them.
- `cca list` shows each account: 5h %, week % of cap, pace, today's allowance, and AT LIMIT when it is.
- `apijob --total` shows the paid key's spend against its total.

## Formulas
- **Pace** = 100 x (time since the account's week started / 7 days). "On pace" = week % not above pace.
- **Headroom** = cap - week %.
- **Daily allowance** = headroom / days to the reset. On its last day an account may spend all it has left.
- **At limit**: 5-hour window at `brain.five_hour_limit` (default 98%) with its reset more than 20 min away,
  or week % at the cap.

## Picking an account for a job
1. Skip accounts at their limit, and any in its 5-hour cool-down.
2. Use the account with the soonest week reset first (its unused points expire first).
3. Stay within today's allowance; a big job goes to the account with the most headroom.
4. A fallback account (`"fallback": true`, for example one the owner also uses for other work) only when the
   others cannot take the job, and only while the owner has it open.
5. The API key last, and only for jobs the owner allowed: `apijob` caps each job (`per_job_usd`) and the
   total (`total_usd`), and refuses to start past it.

## Pause rule
When every account is at its cap: pause every job (stop the workflows, run the pause command, for example
`ws pause`), start nothing new, tell the owner what stopped where, and resume only on their command, with a
RESUMED note per step. `brainwatch` does the detection and writes `team/brain/PAUSED.md`; only
`brainwatch --resume` (the owner) clears it.

## Brain hand-over
- One brain at a time: `brainlease who`.
- When the brain's account is capped or its session died, `brainwatch` names the next account (5-hour under
  80% first, then the most headroom) and prints the exact command for the owner.
- The new brain follows `team/brain/TAKEOVER.md`: take the lease, catch up, recreate crons, check the board,
  resume interrupted work only when it is safe, tell the owner in one line.

## Fallback order (default)
main -> second -> shared (fallback, owner open) -> API key (owner allowed, capped) -> pause.
