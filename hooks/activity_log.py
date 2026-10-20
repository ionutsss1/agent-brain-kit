#!/usr/bin/env python3
"""Activity log: one JSON line per hand-off, so every session sees what the others sent and got back.

Claude Code hook. Writes to <paths.activity> from the kit config:
  - PreToolUse  Agent/Task, Workflow, SendMessage, and Bash commands that call codex, cca, apijob or the
                remote runner                                                                -> "send"
  - PostToolUse the same tools                                                                -> "back"
  - SessionStart: prints the recent activity (last 40 lines) as context for the new session, so no
    session misses what another session did.
Never blocks, never prints on tool events, always exits 0. Reads only the hook's own stdin payload.
Secrets: the log keeps only short summaries; the path guard refuses commands that name secrets.
"""
import fcntl
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin"))
import kitconfig as K  # noqa: E402

CFG = K.load()
LOG = os.environ.get("KIT_ACTIVITY") or K.path("activity", CFG)
LOG_DIR = os.path.dirname(LOG)
ACCOUNTS = K.account_names(CFG, None)
RUNNER = re.escape((CFG.get("runner") or {}).get("name", "ws"))
PROJECT = CFG.get("project", "project")


def acct():
    return K.account_from_env(CFG) or "?"


def short(s, n=160):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def resp_text(r):
    if r is None:
        return ""
    if isinstance(r, str):
        return r
    if isinstance(r, dict):
        for k in ("result", "content", "stdout", "output", "message", "summary"):
            if k in r and r[k]:
                v = r[k]
                if isinstance(v, list):
                    v = " ".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in v)
                return str(v)
        return json.dumps(r)[:400]
    if isinstance(r, list):
        return " ".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in r)
    return str(r)


def classify_bash(cmd):
    c = cmd.strip()
    m = re.search(r"(?:^|[\s;&|(])(?:\S*/)?" + RUNNER + r"\s+(?:--target\s+(\S+)\s+)?(run|wait|kill|pause|resume)\b(.*)", c)
    if m:
        seat, verb, rest = m.group(1) or "default", m.group(2), m.group(3)
        klass = re.search(r"--class\s+(\w+)", rest)
        body = re.search(r"--\s+'([^']*)'", rest) or re.search(r'--\s+"([^"]*)"', rest)
        what = body.group(1) if body else rest
        return "seat:" + seat, "runner %s%s" % (verb, (" " + klass.group(1)) if klass else ""), short(what, 140)
    m = re.search(r"(?:^|[\s;&|(])(?:\S*/)?codex\b(.*)", c)
    if m:
        rest = m.group(1)
        pf = re.search(r"<\s*(\S+)", rest)
        out = re.search(r">\s*(\S+\.md)", rest)
        what = ("prompt " + os.path.basename(pf.group(1))) if pf else short(rest, 120)
        if out:
            what += " -> " + os.path.basename(out.group(1))
        return "codex", "codex exec", what, (os.path.expanduser(out.group(1)) if out else None)
    m = re.search(r"(?:^|[\s;&|(])(?:\S*/)?apijob\s+(\S+)(.*)", c)
    if m:
        return "api", "apijob", short(m.group(1) + " " + m.group(2), 160)
    if ACCOUNTS:
        names = "|".join(re.escape(a) for a in sorted(ACCOUNTS, key=len, reverse=True))
        m = re.search(r"(?:^|[\s;&|(])(?:\S*/)?cca\s+(" + names + r")\b(.*)", c)
        if m:
            rest = m.group(2)
            res = re.search(r"--resume\s+(\S+)", rest)
            p = re.search(r"-p\s+\"([^\"]{0,200})", rest) or re.search(r"-p\s+'([^']{0,200})", rest)
            what = (("resume " + res.group(1)[:8] + ": ") if res else "") + (p.group(1) if p else short(rest, 100))
            return "claude:" + m.group(1), "cca -p", short(what, 160)
    return None


def write(rec):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fcntl.flock(fh, fcntl.LOCK_UN)


def session_start():
    try:
        with open(LOG, encoding="utf-8") as f:
            lines = f.read().splitlines()[-40:]
    except OSError:
        return
    out = []
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        out.append("%s %-8s %-4s %-14s %s%s" % (r.get("t", "")[11:16], r.get("from", ""), r.get("dir", ""),
                                                r.get("to", ""), r.get("what", ""),
                                                (" => " + r["result"]) if r.get("result") else ""))
    if out:
        ctx = ("RECENT %s ACTIVITY (all sessions and accounts, newest last; from %s). Check it before restarting "
               "or launching anything: another session may own that job.\n" % (PROJECT.upper(), LOG) + "\n".join(out))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    ev = data.get("hook_event_name", "")
    if ev == "SessionStart":
        session_start()
        return
    tool = data.get("tool_name", "")
    ti = data.get("tool_input") or {}
    pre = ev == "PreToolUse"
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "from": acct(), "dir": "send" if pre else "back",
           "sid": (data.get("session_id") or "")[:8]}
    if data.get("agent_id") or data.get("agent_type"):
        rec["by"] = short(data.get("agent_type") or data.get("agent_id"), 40)
    if tool in ("Agent", "Task"):
        rec.update(to="agent", kind=ti.get("subagent_type") or "agent",
                   what=short(ti.get("description") or ti.get("prompt"), 120))
        if ti.get("run_in_background"):
            rec["bg"] = True
    elif tool == "Workflow":
        name = ti.get("scriptPath") or ti.get("name") or "inline script"
        rec.update(to="workflow", kind="workflow", what=short(os.path.basename(str(name)) +
                   ((" resume " + ti["resumeFromRunId"]) if ti.get("resumeFromRunId") else ""), 120))
    elif tool == "SendMessage":
        rec.update(to="msg:" + short(ti.get("to"), 30), kind="message",
                   what=short(str(ti.get("message", "")).split("\n")[0], 140))
    elif tool == "Bash":
        cl = classify_bash(ti.get("command", ""))
        if not cl:
            return
        rec.update(to=cl[0], kind=cl[1], what=cl[2])
        # Codex runs in the background write their answer into a file: a detached watcher logs the result
        # when no process holds that file open any more.
        if pre and cl[0] == "codex" and len(cl) > 3 and cl[3]:
            outf = cl[3]
            if not os.path.isabs(outf):
                outf = os.path.join(data.get("cwd") or os.getcwd(), outf)
            subprocess.Popen([sys.executable, os.path.abspath(__file__), "--codex-watch", outf, rec["from"],
                              rec["sid"], rec["what"]], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        return
    if not pre:
        txt = resp_text(data.get("tool_response"))
        lines = [ln for ln in str(txt).splitlines() if ln.strip()]
        rec["result"] = short(lines[-1] if (tool == "Bash" and lines) else (lines[0] if lines else txt), 180)
    write(rec)


def codex_watch(outf, frm, sid, what):
    t0 = time.time()
    seen_open = False
    while time.time() - t0 < 6 * 3600:
        time.sleep(10)
        if not os.path.exists(outf):
            if time.time() - t0 > 600:
                break
            continue
        held = subprocess.run(["lsof", "-t", outf], capture_output=True, text=True).stdout.strip()
        if held:
            seen_open = True
            continue
        if seen_open or time.time() - t0 > 120:
            break
    size = os.path.getsize(outf) if os.path.exists(outf) else 0
    head = ""
    if size:
        with open(outf, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip().strip("#*>_` ").strip()
                if line:
                    head = line
                    break
    mins = int((time.time() - t0) / 60)
    res = ("%s (%d KB, ~%d min): %s" % (os.path.basename(outf), size // 1024, mins, head)) if size else \
          ("no answer in %s after ~%d min (empty or missing: check the codex log)" % (os.path.basename(outf), mins))
    write({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "from": frm, "dir": "back", "sid": sid, "to": "codex",
           "kind": "codex exec", "what": what, "result": short(res, 220)})


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--codex-watch":
        try:
            codex_watch(*sys.argv[2:6])
        except Exception:
            pass
        sys.exit(0)
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
