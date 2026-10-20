# {{AREA}} Rulebook

Status: {{DRAFT_OR_APPROVED}}. Compiled {{DATE}} by {{WHO}}. One reference page for every {{AREA}} job.

## 1. How to use this book
**Owner words > this book > job specs.** A worker's proposal, test or successful build cannot create a rule.
The newest explicit owner decision wins over an older one; keep the older one in §9 "Superseded". If the
newer words do not settle the exact choice, leave the row UNCLEAR.

The brain proposes a change with its reason, exact text, affected rows and evidence. The owner approves it
(questionnaire). Then the brain records the dated approval in §10 and updates the row. Every job cites the
book sections it implements. No extra rule enters a job from memory.

Source keys used in the tables:

| Key | Exact source location |
|---|---|
| B | `team/brain_state.md` (cite the dated entry, not a line number) |
| M | the memory folder (one fact per file) |
| J | job folders (`team/jobs/<job>/RESULT.md`) |

Status words:

| Status | Meaning |
|---|---|
| **PROVEN** | A dated real check records this exact part. It does not certify neighbouring behaviour. |
| **DECIDED NOT YET PROVEN** | The owner requires it. The sources do not show the complete behaviour yet. |
| **UNCLEAR** | The exact choice, mapping or number is missing or conflicts. No worker may fill it in silently. |

## 2. The owner's words
Only verbatim owner words, each with date and source. Explanations outside the quote marks are summaries.

| Date | Owner words (verbatim) | Rule and source |
|---|---|---|
| {{DATE}} | "{{EXACT WORDS}}" | {{rule it sets}}. M/{{file}}; B. |

## 3. {{First topic}}
| Item / state | Required behaviour | Status and dated source |
|---|---|---|
| {{item}} | {{what must happen; limits; numbers}} | **DECIDED NOT YET PROVEN**. Owner {{date}}, B. |
| {{item}} | {{...}} | **PROVEN**, check {{name}} {{date}}, J/{{job}}/RESULT.md. |
| {{item}} | {{...}} | **UNCLEAR**: see §9 Q1. |

## 4. {{Second topic}}
(same table shape)

## 8. What "done" means for a round
- Automated checks (exact commands) and the real-environment check, with the proof each must produce.
- The owner's short acceptance script (what they do, what they should see).

## 9. Conflicts and open questions
### Open
- Q1 {{question}}. Options: {{a}} / {{b}}. Sources: {{...}}. Impact: {{...}}. Safe stop until answered: {{...}}.
### Superseded
- {{date}}: "{{older rule}}" replaced by §10 #{{n}}.

## 10. Owner decisions (newest last; a newer line wins)
- {{DATE HH:MM}}, #1 (§9 Q1): **"{{the owner's pick, verbatim}}"**. {{what it means, as a summary}}.
- {{DATE HH:MM}}, **BOOK APPROVAL: "{{verbatim}}"**. This Rulebook (with the §10 decisions overriding any §9
  option) is the rule for every {{AREA}} job from now on.
