# {{ID}}: {{TITLE}}

<!-- A brief must let a fresh Claude or Codex session do the task safely with no memory. Keep the twelve
headings in this order. Cite evidence. Separate decisions, observations, assumptions and open questions.
Do not invent commands, sources, proof, account access, licences or owner approval: write NEEDS DETAIL and
say where to find it. Owner words only verbatim from their own messages, only on the task they decide;
anything else is a "Summary:" line. Publish as briefs/{{ID}}.md (bundled into briefs.json by board/build.py). -->

## 1 Goal
One paragraph: the intended result, the scope, what is out of scope.

## 2 Owner decisions
Verbatim quotes, dated, with source file and line, only where the owner decided THIS task. Priorities and
explicit pauses. Never turn a paraphrase into a quote: use "Summary (date, source): ...".

## 3 Rulebook sections that govern it
Rulebook file/version and section ids, and the constraint each puts on this task.

## 4 Current state + proof so far
Dated observations, exact proof files, verified results, remaining gaps. Separate current evidence from stale history.

## 5 Method
Numbered concrete steps. For each: who (Codex / a Claude worker on which account / the brain / the owner),
which tool, working folder, inputs, action, expected output, stop conditions.

## 6 Code + files
Exact paths, functions, line references, checksums or versions where they matter, which tree and its lock
(TREE_LOCK.md: one code worker per shared tree). What to read and what to edit.

## 7 Data + assets
Inputs, sources, licences, versions/checksums, locations, permitted use. Which copy is authoritative.

## 8 Dependencies
Other cards by id; tools; accounts and budget (account caps, apijob per-job cap); environment state needed.
Prerequisite status and who unblocks it.

## 9 Traps
The relevant entries from CLAUDE.md "Traps" and lessons, with their source, and the concrete prevention or
recovery step.

## 10 Done means
Tests with exact commands, the real-environment check, the owner's acceptance script, expected results, and
what proof goes to whom. Automated checks separate from owner acceptance.

## 11 Open questions for the owner
Only unresolved owner decisions, with impact and the safe stopping point. Say "None" explicitly.

## 12 Start here
Exact first commands (folder, lock checks) and a ready-to-paste prompt for a fresh session: task id, brief,
rulebook sections, evidence, authorized scope, dependencies, acceptance criteria, where to report.
