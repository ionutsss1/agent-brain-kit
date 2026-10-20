---
name: feedback-workers-foreground-helpers
description: A non-interactive (-p) worker that ends its turn kills its background helpers; workers run helpers in the foreground and end with a READY line
metadata:
  type: feedback
---
A worker started with `cca <account> -p` launched its helpers in the background and then finished its turn; the session ended and took the helpers with it. Half the work was lost and the result file was missing.

**Why:** a -p session lives exactly as long as its turn. Background helpers do not keep it alive.

**How to apply:** every worker prompt says "helpers in the FOREGROUND only", asks for dated STATE.txt lines after each part and a final 'READY' line. The brain treats a worker without READY as cut off: read STATE.txt and continue from the last finished part. Related: [[project-task-board]].
