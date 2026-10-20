# Review rules

Nothing reaches the owner unreviewed. These rules came from real mistakes; each one has its reason.

## 1. Review every result before sending
- Open the result yourself: the images, the video frames, the diff, the test output. Judge it against the
  owner's rules and against the exact complaint the job was fixing.
- Send it with your own verdict and the flaws you see. If it fails the bar, send it to a fix job first and
  tell the owner in one line.
- Why: job notes describe their own work favourably. A brain that forwards unreviewed work makes the owner
  the reviewer.

## 2. Verify job claims
- A claim is not a fact until you have seen its evidence: "tests pass" needs the command and its output;
  "deployed" needs the checksum; "fixed" needs a before/after.
- Never relay a job's claim to the owner as fact. Say what you checked.
- "Done" means seen working in the real environment, not "the job says so".
- A reviewer's finding (Codex or another account) is also a claim: verify it before fixing.

## 3. Tests before apply
- A change is applied only after its tests ran (the brief §10 commands). New behaviour gets a failing test first.
- Visual and moving results get a real-environment proof (a screenshot or a short video), compared with the
  previous version at the same size.
- A safety gate needs drawn proof: check the thing actually rendered or ran, not only that it was called.

## 4. One code worker per shared tree
- Two workers editing the same tree at once overwrite each other. `TREE_LOCK.md` holds one line per shared
  tree; the brain checks it before starting a code worker; the worker releases it with its RESULT.md.
- Reviews and read-only jobs need no lock.

## 5. Do not hide gaps
- RESULT.md lists what failed and what was not done. STATE.txt lines are dated. A missing READY line means
  the worker was cut off.
- If the sources are silent, write NEEDS DETAIL or UNCLEAR. Never invent a command, a source, a proof, a
  licence or an approval.

## 6. Owner words
- Quote the owner only verbatim and only where those words decide the task. Otherwise: "Summary:".

## 7. No blocking question before a critical step at night
- When the owner is away, do not stop a running plan on a question: take the safe default, write the question
  down, and ask through the questionnaire when they are back. Never take an irreversible step on a default.

## Checklist the brain runs on every result
- [ ] I opened the actual output (not only the notes).
- [ ] The tests named in the brief ran, and I saw their output.
- [ ] It meets the Rulebook rows the brief cites.
- [ ] Before/after compared where something visible changed.
- [ ] No owner quote outside the rule above.
- [ ] Gaps and failures are listed, not hidden.
- [ ] The card is updated (column, last_progress, running cleared).
