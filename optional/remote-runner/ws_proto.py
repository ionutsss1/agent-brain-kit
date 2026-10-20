"""Protocol helpers shared by the client (ws) and the daemon (ws_daemon.py).

A request is a JSON file signed with HMAC-SHA256 over its canonical form, with a timestamp (max skew
MAX_SKEW_S) and a nonce (the daemon refuses a nonce it has seen in NONCE_TTL_S). The key is a hex file of at
least 32 bytes that both machines hold; it is never printed (only its 8-character fingerprint).
Standard library only, Python 3.9+.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import time

VERSION = 1
KINDS = ("run", "kill", "ping")
DEFAULT_CLASSES = ("light", "heavy", "build", "film")
MAX_SKEW_S = 300
NONCE_TTL_S = 900
ID_RE = re.compile(r"^[0-9A-Za-z._-]{1,64}$")
ENV_RE = re.compile(r"^KIT_[A-Z0-9_]+$")   # requests may only set KIT_* variables


def load_key(path):
    """Read a hex key file and return the raw bytes."""
    with open(path, "r", encoding="ascii") as f:
        raw = bytes.fromhex(f.read().strip())
    if len(raw) < 32:
        raise ValueError("key file too short")
    return raw


def write_new_key(path):
    """Create a new key file readable only by its owner. Refuses to overwrite. Returns the fingerprint."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(secrets.token_hex(32) + "\n")
    return key_fingerprint(load_key(path))


def key_fingerprint(key):
    return hashlib.sha256(key).hexdigest()[:8]


def new_id():
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)


def canonical(obj):
    body = {k: v for k, v in obj.items() if k != "sig"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def sign(obj, key):
    obj = dict(obj)
    obj["sig"] = hmac.new(key, canonical(obj), hashlib.sha256).hexdigest()
    return obj


def make_request(key, kind, cmd=None, cls="light", cwd=None, env=None, target=None, sender="", req_id=None):
    obj = {"v": VERSION, "id": req_id or new_id(), "ts": int(time.time()),
           "nonce": secrets.token_hex(8), "kind": kind, "class": cls, "from": sender}
    if cmd is not None:
        obj["cmd"] = cmd
    if cwd is not None:
        obj["cwd"] = cwd
    if env:
        obj["env"] = dict(env)
    if target is not None:
        obj["target"] = target
    return sign(obj, key)


def check_request(obj, key, classes=DEFAULT_CLASSES, now=None):
    """None when the request is acceptable, else a short reason. Nonce reuse is the daemon's check."""
    if not isinstance(obj, dict):
        return "not an object"
    sig = obj.get("sig")
    if not isinstance(sig, str):
        return "no signature"
    good = hmac.new(key, canonical(obj), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, good):
        return "bad signature"
    if obj.get("v") != VERSION:
        return "bad version"
    if not isinstance(obj.get("id"), str) or not ID_RE.match(obj["id"]):
        return "bad id"
    now = time.time() if now is None else now
    ts = obj.get("ts")
    if not isinstance(ts, (int, float)) or abs(now - ts) > MAX_SKEW_S:
        return "stale or future timestamp"
    if not isinstance(obj.get("nonce"), str) or not re.match(r"^[0-9a-f]{16}$", obj["nonce"]):
        return "bad nonce"
    kind = obj.get("kind")
    if kind not in KINDS:
        return "unknown kind"
    if obj.get("class") not in classes:
        return "unknown class"
    if kind == "run" and not isinstance(obj.get("cmd"), str):
        return "run without cmd"
    if kind == "kill" and (not isinstance(obj.get("target"), str) or not ID_RE.match(obj["target"])):
        return "kill without a valid target"
    env = obj.get("env", {})
    if not isinstance(env, dict) or any(not ENV_RE.match(k) or not isinstance(v, str) for k, v in env.items()):
        return "env key not allowed"
    return None


def write_atomic(path, data):
    """Write bytes or text next to the target, then rename over it."""
    tmp = "%s.%d.tmp" % (path, os.getpid())
    mode = "wb" if isinstance(data, bytes) else "w"
    kw = {} if isinstance(data, bytes) else {"encoding": "utf-8", "newline": "\n"}
    with open(tmp, mode, **kw) as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None
