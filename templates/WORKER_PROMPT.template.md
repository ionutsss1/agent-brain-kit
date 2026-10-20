WORKER {{JOB_NAME}} ({{ACCOUNT}}, {{DATE}}; the brain is {{BRAIN_ACCOUNT}} session {{BRAIN_SESSION}}). Card {{CARD_ID}}.

TASK: {{one paragraph: the goal, from the brief §1}}.
BRIEF: {{KIT_HOME}}/team/board/briefs/{{CARD_ID}}.md (read it whole first). RULEBOOK: {{RULEBOOK}} §{{sections}}.

BUILD IN: {{JOB_FOLDER}}/ (write nowhere else). Inputs (read only): {{paths}}.

SCOPE: {{what is in}}. NOT in scope: {{what is out}}. Do not change: {{protected files / folders}}.

TRAPS (from CLAUDE.md; you do not read memory):
- {{trap 1 with its prevention step}}
- {{trap 2}}
- Secrets: never open, print or copy {{secret list}}; the guard refuses them; do not work around it.
- No git writes. No service restarts. No spending. No sign-ins anywhere.
- Owner words: quote the owner only verbatim from their own messages, only on the task they decide;
  anything else is a "Summary:" line.

HOW TO WORK:
- Helpers (subagents) in the FOREGROUND only: a -p session that ends its turn kills background helpers.
- Tests before apply: write or run the checks named in the brief §10 before you call anything done.
- One code worker per shared tree: check {{TREE_LOCK}} before editing; if it is held by someone else, stop
  and report.
- After each part, append one dated line (time from `date`) to {{JOB_FOLDER}}/STATE.txt: what is done, what
  is next. If you are cut off, the next session continues from STATE.txt.

DONE MEANS: {{the brief §10, short}}.

REPORT: {{JOB_FOLDER}}/RESULT.md: what you made from what, test output (exact commands and results), what
failed, what you did NOT do, open points. Last line of STATE.txt: 'READY'. Final answer: three to six short
lines (result, tests, open points). Never claim a check you did not run.
