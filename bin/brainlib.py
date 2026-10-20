"""brainlib - shared code for the brain lease (brainlease, brainwatch, hooks/brain_hook.py).

One brain at a time. When the brain's account runs out, another account takes over.

Lease file <paths.brain>/lease.json: {account, session_id, since, heartbeat, ...}.
  fresh    heartbeat younger than brain.stale_minutes (default 15)
  idle     heartbeat older, but the holder's claude process is still alive (waiting for the owner)
  stale    heartbeat older and the holder's process is gone (or cannot be found)
  released the holder gave it up (brainlease release)

Accounts, caps and paths come from the kit config (kitconfig.py). Test overrides: KIT_BRAIN_DIR,
KIT_LEDGER, KIT_LOGS, KIT_ACCOUNTS, KIT_ACTIVITY move the folders; KIT_NOW fakes the clock;
KIT_ALIVE="sid1,sid2" (or "none") fakes which sessions are alive. Plain Python 3 standard library.
"""
import fcntl
import glob
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import kitconfig as K  # noqa: E402

CFG = K.load()
BRAIN_DIR = os.environ.get("KIT_BRAIN_DIR") or K.path("brain", CFG)
LEASE = os.path.join(BRAIN_DIR, "lease.json")
STATE = os.path.join(BRAIN_DIR, "watch_state.json")
PAUSED = os.path.join(BRAIN_DIR, "PAUSED.md")
LEDGER_DIR = os.environ.get("KIT_LEDGER") or K.path("ledger", CFG)
LOGS_DIR = os.environ.get("KIT_LOGS") or K.path("logs", CFG)
ACCOUNTS_DIR = os.environ.get("KIT_ACCOUNTS") or K.path("accounts", CFG)
ACTIVITY = os.environ.get("KIT_ACTIVITY") or K.path("activity", CFG)

BRAIN = CFG.get("brain", {})
ACCOUNTS = K.account_names(CFG)
STALE_S = 60 * float(BRAIN.get("stale_minutes", 15))
FIVE_HOUR_LIMIT = float(BRAIN.get("five_hour_limit", 98))
WEEK_S = 7 * 86400


def now():
    v = os.environ.get("KIT_NOW")
    return float(v) if v else time.time()


def hm(ts):
    if not isinstance(ts, (int, float)):
        return "?"
    fmt = "%H:%M" if abs(ts - now()) < 20 * 3600 else "%a %H:%M"
    return time.strftime(fmt, time.localtime(ts))


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))


def account_from_env():
    return K.account_from_env(CFG)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


class Locked(object):
    """Exclusive lock on <path>.lock for a read-modify-write of the lease or the watch state."""

    def __init__(self, path):
        self.path = path + ".lock"

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, "a")
        fcntl.flock(self.f.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        try:
            fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        finally:
            self.f.close()


# ---------------------------------------------------------------- sessions alive?

def session_record(session_id):
    """The claude process record (<accounts>/*/sessions/<pid>.json) for this session, or None."""
    for p in glob.glob(os.path.join(ACCOUNTS_DIR, "*", "sessions", "*.json")):
        d = load_json(p)
        if d and d.get("sessionId") == session_id:
            return d
    return None


def session_alive(session_id):
    fake = os.environ.get("KIT_ALIVE")
    if fake is not None:
        return session_id in [s.strip() for s in fake.split(",") if s.strip()]
    if not session_id:
        return False
    rec = session_record(session_id)
    if not rec or not isinstance(rec.get("pid"), int):
        return False
    pid = rec["pid"]
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    if rec.get("procStart"):   # pid reuse guard: the record's start time is UTC, C locale
        try:
            env = dict(os.environ, LC_ALL="C", TZ="UTC")
            out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True,
                                 env=env, timeout=5).stdout.strip()
            if out and " ".join(out.split()) != " ".join(rec["procStart"].split()):
                return False
        except (OSError, subprocess.SubprocessError):
            pass
    return True


# ---------------------------------------------------------------- lease

def read_lease():
    return load_json(LEASE)


def lease_state(lease, t=None):
    """(state, heartbeat age in seconds, alive)"""
    t = now() if t is None else t
    if not lease or not lease.get("account"):
        return "none", None, False
    if lease.get("released"):
        return "released", t - float(lease.get("heartbeat") or 0), False
    age = t - float(lease.get("heartbeat") or 0)
    if age < STALE_S:
        return "fresh", age, True
    alive = session_alive(lease.get("session_id"))
    return ("idle" if alive else "stale"), age, alive


def describe(lease, t=None):
    t = now() if t is None else t
    st, age, _ = lease_state(lease, t)
    if st == "none":
        return "no brain lease holder"
    mins = int(age // 60) if age is not None else 0
    who = "%s (session %s)" % (lease.get("account"), str(lease.get("session_id", ""))[:8])
    if st == "released":
        return "lease released by %s %d min ago: no brain" % (who, mins)
    return "%s holds the brain lease since %s; %s, last heartbeat %d min ago" % (
        who, hm(lease.get("since")), st, mins)


def acquire(account, session, force=False, t=None, **extra):
    """Returns (ok, message, lease)."""
    t = now() if t is None else t
    with Locked(LEASE):
        cur = read_lease()
        st, age, _ = lease_state(cur, t)
        same = cur and cur.get("session_id") == session and cur.get("account") == account and st != "released"
        if same:
            cur["heartbeat"] = t
            cur["heartbeat_iso"] = iso(t)
            save_json(LEASE, cur)
            return True, "already the holder; heartbeat renewed", cur
        if st in ("fresh", "idle") and not force:
            return False, "refused: " + describe(cur, t) + " (use --force only when the owner says so)", cur
        new = {"account": account, "session_id": session, "since": t, "since_iso": iso(t),
               "heartbeat": t, "heartbeat_iso": iso(t)}
        new.update({k: v for k, v in extra.items() if v is not None})
        if cur and cur.get("account"):
            new["previous"] = {"account": cur.get("account"), "session_id": cur.get("session_id"),
                               "state": st, "until": t}
        save_json(LEASE, new)
        how = "forced over a %s holder" % st if (cur and st in ("fresh", "idle")) else (
            "took over a %s lease" % st if st in ("stale", "released") else "new lease")
        return True, "acquired by %s (session %s): %s" % (account, session[:8], how), new


def renew(session, t=None, min_gap=0):
    """Heartbeat for the holder. Returns True when this session holds the lease."""
    t = now() if t is None else t
    cur = read_lease()
    if not cur or cur.get("released") or cur.get("session_id") != session:
        return False
    if t - float(cur.get("heartbeat") or 0) < min_gap:
        return True
    with Locked(LEASE):
        cur = read_lease()
        if not cur or cur.get("released") or cur.get("session_id") != session:
            return False
        cur["heartbeat"] = t
        cur["heartbeat_iso"] = iso(t)
        save_json(LEASE, cur)
    return True


def release(session, force=False, t=None):
    t = now() if t is None else t
    with Locked(LEASE):
        cur = read_lease()
        if not cur or not cur.get("account"):
            return False, "no lease"
        if cur.get("session_id") != session and not force:
            return False, "refused: not the holder (" + describe(cur, t) + ")"
        cur["released"] = True
        cur["released_at"] = t
        cur["released_iso"] = iso(t)
        save_json(LEASE, cur)
        return True, "released by %s" % cur.get("account")


# ---------------------------------------------------------------- usage

def _log_reading(acct, after):
    """Newest rate_limit_event of a background `cca <acct> -p` stream log newer than the ledger."""
    try:
        logs = sorted(glob.glob(os.path.join(LOGS_DIR, acct + "_*.jsonl")), key=os.path.getmtime)
        if not logs or os.path.getmtime(logs[-1]) <= after:
            return None
        ev = None
        with open(logs[-1], encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"rate_limit_event"' in line:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        pass
        uw = ((ev or {}).get("rate_limit_info") or {}).get("unifiedWindows") or {}
        if not uw:
            return None
        out = {"updated": os.path.getmtime(logs[-1])}
        for k in ("five_hour", "seven_day"):
            w = uw.get(k) or {}
            if "utilization" in w:
                out[k] = {"used_percentage": 100.0 * w["utilization"], "resets_at": w.get("resetsAt")}
        return out
    except (OSError, ValueError):
        return None


def usage(acct, t=None):
    """What the ledger (and newer -p logs) say about one account, with windows that already reset zeroed."""
    t = now() if t is None else t
    rec = load_json(os.path.join(LEDGER_DIR, acct + ".json")) or {}
    fh, sd = dict(rec.get("five_hour") or {}), dict(rec.get("seven_day") or {})
    updated = rec.get("updated") or 0
    lr = _log_reading(acct, updated)
    if lr:
        fh = lr.get("five_hour") or fh
        sd = lr.get("seven_day") or sd
        updated = lr["updated"]
    u = {"account": acct, "known": bool(fh or sd), "updated": updated}
    u["fh"] = float(fh.get("used_percentage") or 0.0)
    u["fh_reset"] = fh.get("resets_at")
    if isinstance(u["fh_reset"], (int, float)) and u["fh_reset"] <= t:
        u["fh"], u["fh_note"] = 0.0, "5h window reset since the last reading"
    u["wk"] = float(sd.get("used_percentage") or 0.0)
    u["wk_reset"] = sd.get("resets_at")
    est = rec.get("week_est") if isinstance(rec.get("week_est"), dict) else {}
    u["spent"] = float(est.get("spent") or 0.0) if est.get("resets_at") == u["wk_reset"] else 0.0
    if isinstance(u["wk_reset"], (int, float)) and u["wk_reset"] <= t:
        u["wk"], u["spent"], u["wk_note"] = 0.0, 0.0, "week reset since the last reading"
        u["wk_reset"] = None
    u["pace"] = pace(u["wk_reset"], t)
    u["age_min"] = int((t - updated) // 60) if updated else None
    return u


def pace(week_reset, t=None):
    """Pace = 100 x (time since the account's week started / 7 days)."""
    t = now() if t is None else t
    if not isinstance(week_reset, (int, float)):
        return None
    return max(0.0, min(100.0, 100.0 * (t - (week_reset - WEEK_S)) / WEEK_S))


def cap(acct, t=None):
    return K.cap(acct, now() if t is None else t, CFG)


def at_limit(u, t=None):
    """Why this account may not be the brain now (None = it may)."""
    t = now() if t is None else t
    if u["fh"] >= FIVE_HOUR_LIMIT and isinstance(u["fh_reset"], (int, float)) and u["fh_reset"] - t > 20 * 60:
        return "5-hour window at %d%% (resets %s)" % (round(u["fh"]), hm(u["fh_reset"]))
    c = cap(u["account"], t)
    if u["wk"] >= c:
        return "week at %d%% (cap %d%%)" % (round(u["wk"]), c)
    return None


def headroom(u, t=None):
    """Week points this account may still spend on the project before its cap."""
    return max(0.0, cap(u["account"], t) - u["wk"])


def daily_allowance(u, t=None):
    """What is left under the cap divided by the days to the reset (CLAUDE.md pacing rule)."""
    t = now() if t is None else t
    if not isinstance(u.get("wk_reset"), (int, float)):
        return None
    days = (u["wk_reset"] - t) / 86400.0
    return headroom(u, t) if days < 1 else headroom(u, t) / days   # last day: all that is left


def summary(u):
    bits = ["5h %d%%" % round(u["fh"]), "week %d%%/%d" % (round(u["wk"]), cap(u["account"]))]
    if u["pace"] is not None:
        bits.append("pace %d%%" % round(u["pace"]))
    if u.get("age_min") is not None:
        bits.append("reading %d min old" % u["age_min"])
    elif not u["known"]:
        bits.append("no reading")
    return ", ".join(bits)


# ---------------------------------------------------------------- activity log

def activity(rec):
    try:
        os.makedirs(os.path.dirname(ACTIVITY), exist_ok=True)
        rec = dict({"t": iso(now()), "from": "brainwatch"}, **rec)
        with open(ACTIVITY, "a", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fcntl.flock(fh, fcntl.LOCK_UN)
    except OSError:
        pass
