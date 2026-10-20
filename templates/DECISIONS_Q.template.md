# {{AREA}} Rulebook: the open decisions as ready questionnaires

Prepared {{DATE}} by {{WHO}} (read-only except this file). Source of every group: RULEBOOK.md §9.
Nothing here is a new rule: every option comes from a dated owner pick, a worker draft or a plan proposal
named in its description. Where the sources are silent, the option says so.

## How to use (brain)
- Paste each batch's JSON as the `questions` argument of one AskUserQuestion call (max 4 questions per call).
- The recommended option is always first. The answer goes into RULEBOOK.md §10 (date, time, the pick
  verbatim, any "Other" text verbatim) and the matching §9 row is marked decided.
- "Decide later after a test" keeps the row UNCLEAR and adds the test to the next check. No worker fills it in.
- Owner-facing text uses the owner's words for things, never internal code names.

---

## Batch 1: #1, #2

```json
[
  {
    "question": "{{One plain question the owner can answer without reading the book?}}",
    "header": "{{Short tag}}",
    "multiSelect": false,
    "options": [
      {"label": "{{Option A}} (Recommended)", "description": "{{What happens, what it costs, where it came from (dated source).}}"},
      {"label": "{{Option B}}", "description": "{{...}}"},
      {"label": "Decide after a test", "description": "{{Which test, when, what it would show.}}"}
    ]
  }
]
```
If they pick A: {{the exact book change}}. If B: {{...}}.
