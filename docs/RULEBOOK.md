# The Rulebook: how decisions are recorded

Every area of work that keeps changing (a product feature, an API, a design system) gets one Rulebook the owner
approves. It is the single rule for every job in that area. Template: `templates/RULEBOOK.template.md`.

## Why
Jobs that read rules from memory, old notes or another job's spec drift. They mix old and new decisions, fill
gaps with guesses, and quote the owner where the owner never spoke. One approved book, with every row's status
and source, stops that.

## The order of authority
**Owner words > the Rulebook > job specs.** A worker's proposal, a passing test or a successful build never
creates a rule. The newest explicit owner decision wins; the older one moves to "Superseded" with its date.

## Rows and status
Every rule is a table row: the item, the required behaviour, and its **status with a dated source**:
- **PROVEN**: a dated real check shows this exact part works. It proves only that part.
- **DECIDED NOT YET PROVEN**: the owner requires it; no check shows it yet.
- **UNCLEAR**: the exact choice or number is missing or conflicts. No worker may fill it in silently: it
  goes to §9 as a question.

## Owner decisions (§10)
- Asked through the questionnaire (`templates/DECISIONS_Q.template.md`): plain questions, the recommended
  option first, at most 4 per batch, each option saying where it came from.
- Recorded in §10 with date and time, the owner's pick **verbatim**, and any "Other" text verbatim; then the
  matching row is updated and the §9 question closed. Newest lines last; a newer line wins.
- The approval line ("BOOK APPROVAL ...") makes the book binding. Until then it is a draft and says so.

## Quoting the owner (hard rule)
- Quote the owner **only** with words found verbatim in their own messages (session transcripts,
  questionnaire answers), and **only** on the task or row those words decide.
- Everything else is a summary: `Summary (date, source): ...`, never in quote marks, never called verbatim.
- A cleaned-up, shortened or translated sentence is a summary.
- The brain checks this in every brief, Rulebook change and owner sheet before it is published.

## Changing the book
1. The brain proposes: the reason, the exact new text, the rows it affects, the evidence.
2. The owner approves (questionnaire).
3. The brain writes the dated §10 line and changes the rows. Jobs started after that cite the new version.
4. A job that finds a conflict stops and reports it; it does not pick a side.

## Jobs and the book
- Every brief names the Rulebook sections that govern it (§3 of the brief) and quotes no rule that is not there.
- A result is reviewed against those rows. A row becomes PROVEN only with a dated real check.
