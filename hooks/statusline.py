#!/usr/bin/env python3
"""Status line for kit sessions: keeps each account's usage ledger and prints one short line.

Reads the status line JSON on stdin. Uses rate_limits.five_hour and rate_limits.seven_day
(used_percentage 0-100, resets_at = Unix epoch seconds; present only for plan logins and only after
the session's first answer; a window may be missing). Writes <paths.ledger>/<account>.json atomically
(account = folder of CLAUDE_CONFIG_DIR) and prints: account | 5h % (reset) | week %/cap (reset).

The ledger also keeps "week_est": the week points this account spent while kit sessions were watching
(sum of rises between updates no more than 10 minutes apart). On an account shared with other work it
also counts that other use made at the same time, so it errs high: the safe side for a cap.

Standard library only, Python 3.9+. Never fails loudly: a broken input prints a short line.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin"))
try:
    import kitconfig as K
    CFG = K.load()
    LEDGER_DIR = os.environ.get("KIT_LEDGER") or K.path("ledger", CFG)
except BaseException:   # the status line must never break the session
    K, CFG, LEDGER_DIR = None, {}, os.path.join(os.path.expanduser("~"), ".agent-kit-ledger")
GAP_S = 600


def cap_for(acct, now):
    try:
        return int(K.cap(acct, now, CFG)) if K and K.account(acct, CFG) else None
    except Exception:
        return None


def account_name():
    try:
        return K.account_from_env(CFG) or "default"
    except Exception:
        cfg = os.environ.get("CLAUDE_CONFIG_DIR", "").rstrip("/\\")
        return os.path.basename(cfg) if cfg else "default"


def window(rl, name):
    w = rl.get(name) if isinstance(rl, dict) else None
    if not isinstance(w, dict):
        return None
    pct, reset = w.get("used_percentage"), w.get("resets_at")
    if not isinstance(pct, (int, float)) or isinstance(pct, bool):
        return None
    out = {"used_percentage": round(float(pct), 1)}
    if isinstance(reset, (int, float)) and not isinstance(reset, bool):
        out["resets_at"] = int(reset)
    return out


def still_valid(w, now):
    return isinstance(w, dict) and (not isinstance(w.get("resets_at"), int) or w["resets_at"] > now)


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_atomic(path, obj):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class Lock(object):
    """Advisory lock so two sessions of one account do not double-count (no-op where fcntl is missing)."""

    def __init__(self, path):
        self.f = None
        try:
            import fcntl
            self.f = open(path, "a")
            fcntl.flock(self.f.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            self.f = None

    def release(self):
        if self.f:
            try:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
            self.f.close()


def update_ledger(acct, data, now):
    rl = data.get("rate_limits") if isinstance(data.get("rate_limits"), dict) else None
    os.makedirs(LEDGER_DIR, exist_ok=True)
    path = os.path.join(LEDGER_DIR, acct + ".json")
    lock = Lock(path + ".lock")
    try:
        old = load(path)
        rec = dict(old)
        rec["account"] = acct
        rec["cap_percent"] = cap_for(acct, now)
        rec["seen"] = int(now)
        model = data.get("model") if isinstance(data.get("model"), dict) else {}
        if model.get("id"):
            rec["model"] = model.get("id")
        if rl is not None:
            fh, sd = window(rl, "five_hour"), window(rl, "seven_day")
            if fh is None and not still_valid(old.get("five_hour"), now):
                rec.pop("five_hour", None)
            if sd is None and not still_valid(old.get("seven_day"), now):
                rec.pop("seven_day", None)
            if fh is not None:
                rec["five_hour"] = fh
            if sd is not None:
                rec["seven_day"] = sd
                est = old.get("week_est") if isinstance(old.get("week_est"), dict) else {}
                prev = old.get("seven_day") if isinstance(old.get("seven_day"), dict) else {}
                same_week = est.get("resets_at") == sd.get("resets_at") and sd.get("resets_at") is not None
                spent = float(est.get("spent", 0.0)) if same_week else 0.0
                last_t = old.get("updated", 0)
                if same_week and isinstance(prev.get("used_percentage"), (int, float)) and \
                        now - last_t <= GAP_S and prev.get("resets_at") == sd.get("resets_at"):
                    rise = sd["used_percentage"] - prev["used_percentage"]
                    if rise > 0:
                        spent += rise
                rec["week_est"] = {"resets_at": sd.get("resets_at"), "spent": round(spent, 1)}
            rec["updated"] = int(now)
            rec["updated_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now))
            if rec != old:
                save_atomic(path, rec)
        elif not old:
            save_atomic(path, rec)   # first sight of this account, before its first answer
        return rec
    finally:
        lock.release()


def when(ts, now):
    if not isinstance(ts, int):
        return "?"
    lt = time.localtime(ts)
    return time.strftime("%H:%M" if ts - now < 20 * 3600 else "%a %H:%M", lt)


def line(acct, rec, now):
    parts = [acct]
    fh, sd = rec.get("five_hour"), rec.get("seven_day")
    parts.append("5h %d%% (%s)" % (round(fh["used_percentage"]), when(fh.get("resets_at"), now))
                 if isinstance(fh, dict) else "5h -")
    if isinstance(sd, dict):
        cap = rec.get("cap_percent")
        wk = "wk %d%%" % round(sd["used_percentage"]) + ("/%d" % cap if cap else "")
        parts.append("%s (%s)" % (wk, when(sd.get("resets_at"), now)))
    else:
        parts.append("wk -")
    return " | ".join(parts)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    acct = account_name()
    now = time.time()
    try:
        data = json.loads(sys.stdin.read() or "{}")
        if not isinstance(data, dict):
            data = {}
    except ValueError:
        data = {}
    try:
        rec = update_ledger(acct, data, now)
    except Exception:  # the status line must never break the session
        rec = {}
    sys.stdout.write(line(acct, rec, now) + "\n")


if __name__ == "__main__":
    main()
