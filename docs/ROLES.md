# Roles

## Owner
- Decides goals, order, looks and spending. Approves the Rulebook and every change to it.
- Orders the To do column on the Task Board; starts work with "Assign and start" or in chat.
- Answers questions only through the questionnaire (max 4 per batch, recommended option first).
- Holds the keys: creates key files, signs in accounts, runs any script that touches system settings.
- Starts a takeover brain with the command brainwatch prints; clears a pause with `brainwatch --resume`.

## Brain (one session at a time, holds the lease)
- Plans: turns owner decisions into Rulebook rows, cards and briefs.
- Starts work: picks the account (caps, pace, 5-hour window, API budget), checks the tree lock and
  dependencies, writes the worker prompt from the brief + the traps, starts it, logs it, tags the card.
- Reviews every result before the owner sees it: opens the files, runs or reads the tests, checks the
  claims against evidence, compares before/after. Sends a fix job when it fails the bar.
- Keeps the state: brain_state.md (dated lines), the board cards, the memory.
- Talks to the owner: short, plain, questions through the questionnaire.
- Never does the long work itself when a worker can: its context is the project's memory.

## Workers
- **Claude worker** (`cca <account> -p ... --model opus`): specs, tests, reviews, research, applying and
  checking changes, anything that needs judgment or tools.
- **Codex** (`codex exec`): writes code, data and drafts when the split "Claude plans + reviews, Codex
  writes code" is in force; read-only reviews (`--sandbox read-only`), one per phase.
- **API-key worker** (`apijob`): the same as a Claude worker, on the paid key, capped per job and in total.
  For when the plan accounts are at their caps and the owner allowed the spend.
- Every worker: builds only in its job folder, holds the tree lock for shared trees, writes STATE.txt lines,
  runs helpers in the foreground, ends with RESULT.md and a READY line, never claims a check it did not run.

## Reviewers
- The brain reviews everything. A second reviewer (Codex read-only, or another Claude account) looks at each
  phase: architecture, risky changes, anything the owner will see.
- A reviewer's finding is a claim like any other: verify it before fixing.

## Who does what (the split)

| Work | Who |
|---|---|
| Decisions, priorities, approval | Owner |
| Rulebook rows, cards, briefs, worker prompts | Brain (or a Claude worker it starts) |
| Code, data, concept drafts | Codex (or a Claude worker when the owner prefers) |
| Tests and specs | Claude worker |
| Applying a change and checking it in the real environment | Claude worker, then the brain's review |
| Reviews | Brain always; Codex or a second account per phase |
| Sending results to the owner | Brain only (the main session) |
