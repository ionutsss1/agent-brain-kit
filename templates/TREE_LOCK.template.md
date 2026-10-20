# Tree locks: one code worker per shared tree

A worker that edits a shared tree holds its line here; nobody else edits that tree until the line is gone.
The brain checks this file before starting a code worker. Newest change first.

| Tree | Holder (job, account, session) | Since | Card |
|---|---|---|---|
| {{service/}} | free | | |
| {{data/}} | {{JOB}} ({{account}}, {{session}}) | {{date time}} | {{card id}} |

Rules:
- Take the line before the first edit; release it in the same message that writes RESULT.md.
- A crashed worker's line stays until the brain checks its process and logs, then clears it with a dated note.
- Reviews and read-only jobs need no lock.
