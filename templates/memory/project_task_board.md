---
name: project-task-board
description: The Task Board Artifact is the project's ticketing - keep every card current, running jobs tagged, new work from the top of the owner's To do column
metadata:
  type: project
---
The Task Board (an Artifact page with a shared database) is where the owner sets priorities and starts work ("Assign and start"). Its link and the account that published it are in team/brain/TAKEOVER.md.

**Why:** the owner follows the work from their phone; the board is the one place that shows what runs, who does it and what waits on them.

**How to apply:** every job start, result and decision updates its card (read first, update with if_version, never overwrite the owner's column, order or note). A running job's card has running, progress, progress_at and account. Every tick checks for start requests. Related: [[feedback-review-before-sending]], [[feedback-workers-foreground-helpers]].
