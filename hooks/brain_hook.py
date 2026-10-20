#!/usr/bin/env python3
"""Brain lease hook (team/.claude/settings.json). One brain at a time.

  --renew  (PreToolUse, every tool, async): the lease holder's tool use renews its heartbeat (at most every 30 s).
  --guard  (PreToolUse on Workflow|TaskStop|CronCreate|Artifact|Bash, sync, never blocks): a main-thread session
           that is NOT the holder and is about to launch, stop or schedule work gets a reminder in its context
           (at most once per 10 min per session). Never denies anything.
  (no flag) SessionStart: tells every new session who holds the lease and what that means for it.
Always exits 0; prints nothing except hook JSON; reads only its stdin payload and the lease.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin"))
import brainlib as B  # noqa: E402


def _job_bash():
    runner = B.CFG.get("runner") or {}
    verbs = "|".join(re.escape(v) for v in runner.get("verbs", ["run", "kill", "pause", "resume"]))
    parts = [re.escape(runner.get("name", "ws")) + r"\s+(?:--target\s+\S+\s+)?(?:" + verbs + r")\b"]
    names = B.K.account_names(B.CFG, None)
    if names:
        parts.append(r"cca\s+(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b")
    parts.append(r"screen\s+-dm")
    parts += [p for p in B.BRAIN.get("job_command_patterns", []) if isinstance(p, str)]
    return re.compile(r"(?:^|[\s;&|(])(?:\S*/)?(?:" + "|".join(parts) + ")")


JOB_BASH = _job_bash()
NOT_BRAIN = ("You are NOT the brain: do not launch, resume, stop or restart any job (workflows, remote runner "
             "run/kill/pause/resume, cca -p workers, apijob, crons, service restarts, page republishes); inspect "
             "and answer only, unless the owner tells you to take over (then `brainlease acquire --force --reason "
             "\"owner\"`). If you are a worker started by the brain for one task (cca -p job, workflow or "
             "subagent), do that task as told; this rule is about main sessions.")


def is_worker():
    ep = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "")
    return ep.startswith("sdk") or os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0" or \
        os.environ.get("KIT_WORKER") == "1"


def emit(event, text):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def session_start(data):
    sid = data.get("session_id") or ""
    acct = B.account_from_env()
    lease = B.read_lease()
    st, age, _ = B.lease_state(lease)
    desc = B.describe(lease)
    takeover = os.path.join(B.BRAIN_DIR, "TAKEOVER.md")
    if st in ("fresh", "idle", "stale") and lease.get("session_id") == sid:
        txt = ("BRAIN LEASE: you (%s, session %s) are the brain. %s. Your tool use renews the heartbeat; "
               "brainwatch hands the brain to another account if this session goes quiet with its process gone, "
               "or its account hits its cap. If you stop being the brain on purpose: `brainlease release`."
               % (lease.get("account"), sid[:8], desc))
    elif st in ("fresh", "idle"):
        txt = "BRAIN LEASE: %s. This session (%s, %s) is not the brain. %s" % (desc, acct, sid[:8], NOT_BRAIN)
        prev = (lease or {}).get("previous") or {}
        if prev.get("session_id") == sid:
            txt += (" You WERE the brain until %s and lost the lease (%s): delete your session crons "
                    "(CronList, CronDelete) and stop launching." % (B.hm(prev.get("until")),
                                                                   lease.get("reason") or "handover"))
    elif st == "stale":
        txt = ("BRAIN LEASE: %s. The holder looks gone; brainwatch (if installed) names a takeover account within "
               "minutes. %s" % (desc, NOT_BRAIN))
    else:
        txt = ("BRAIN LEASE: %s. Nobody is the brain right now. If the owner makes this session the brain: "
               "`brainlease acquire --reason \"owner\"`, then follow %s. Until then: %s" % (desc, takeover, NOT_BRAIN))
    if os.path.exists(B.PAUSED):
        txt += " PAUSED: every account reached its cap (%s); resume only on the owner's command." % B.PAUSED
    emit("SessionStart", txt)


def renew(data):
    sid = data.get("session_id") or ""
    if sid:
        B.renew(sid, min_gap=30)


def guard(data):
    sid = data.get("session_id") or ""
    renew(data)
    if not sid or data.get("agent_id") or is_worker():
        return
    tool = data.get("tool_name", "")
    if tool == "Bash" and not JOB_BASH.search(str((data.get("tool_input") or {}).get("command", ""))):
        return
    lease = B.read_lease()
    st, _, _ = B.lease_state(lease)
    if st == "none" or (lease or {}).get("session_id") == sid:
        return
    mark = os.path.join(B.BRAIN_DIR, "guard", sid[:36] + ".t")
    try:
        if time.time() - os.path.getmtime(mark) < 600:
            return
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(mark), exist_ok=True)
        open(mark, "w").close()
    except OSError:
        pass
    txt = "BRAIN LEASE CHECK before %s: %s. %s" % (tool, B.describe(lease), NOT_BRAIN)
    prev = (lease or {}).get("previous") or {}
    if prev.get("session_id") == sid:
        txt += (" You WERE the brain and lost the lease at %s (%s): delete your session crons (CronList, "
                "CronDelete), launch nothing, and tell the owner only if they talk to you."
                % (B.hm(prev.get("until")), (lease or {}).get("reason") or "handover"))
    emit("PreToolUse", txt)


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--renew":
        renew(data)
    elif mode == "--guard":
        guard(data)
    elif data.get("hook_event_name") == "SessionStart":
        session_start(data)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
