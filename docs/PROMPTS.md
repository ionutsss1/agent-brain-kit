# Worker prompts

Workers do not read memory and do not remember earlier sessions. Everything a worker needs is in its prompt
and the files it points to. Template: `templates/WORKER_PROMPT.template.md`.

## Shape of a worker prompt
1. **Header**: job name, account, date, who the brain is, the card id.
2. **Task**: one paragraph (the brief §1).
3. **Pointers, not pastes**: the brief file, the Rulebook sections, the input files. Keep prompts short.
4. **Build in**: the one job folder it may write; inputs it may only read.
5. **Scope**: what is in, what is out, what it must not change.
6. **Traps**: the relevant entries from CLAUDE.md "Traps", each with its prevention step. Always also:
   secrets, no git writes, no service restarts, no spending, owner quotes only verbatim.
7. **How to work**: helpers in the foreground; tests before apply; the tree lock; dated STATE.txt lines.
8. **Done means**: the brief §10, short.
9. **Report**: RESULT.md, the final READY line, a short final answer.

## STATE.txt
- One dated line per finished part, time from `date` (never guessed): `2026-01-07 09:15 part 1 done: ...`.
- The first line says what the worker read and which locks it took. The last line is `READY`.
- If a worker is cut off (usage limit, crash), the next session reads STATE.txt and continues from the last
  finished part with a `RESUMED` line. No READY = not finished.

## Helpers in the foreground
A worker started with `-p` lives only as long as its turn. Subagents or tools it starts in the background die
when the turn ends. So: run helpers in the foreground, wait for them, and end the turn only when the work is
done.

## Starting a worker (the brain)
```sh
# Claude worker on an account, logged so cca list sees its usage
cca second -p "$(cat team/jobs/EX01/PROMPT.txt)" --model opus --output-format stream-json --verbose \
  > logs/second_EX01.jsonl 2>&1 < /dev/null &
# Codex, read-only review
codex exec --sandbox read-only "Review team/jobs/EX01/RESULT.md against briefs/EX01.md §10 ..."
# Paid key, capped
apijob EX01 logs/api_EX01.jsonl "$(cat team/jobs/EX01/PROMPT.txt)" --model opus
```
Then: a process waiter, an activity line (the hook writes it), and the card set to running.

## The final answer
Three to six short lines: the result, the tests and their outcome, the open points. The brain reads RESULT.md
for detail and reviews before anything reaches the owner.

## Prompt hygiene
- Workflow scripts: LF newlines; changing or reordering a prompt re-runs every later cached call.
- Do not paste results from other jobs: point to their files.
- Do not paste owner quotes unless they decide this task (verbatim, with date and source).
- Name the model explicitly (`--model opus`, `model: 'opus'` in workflow agents) so every job runs on the same one.
