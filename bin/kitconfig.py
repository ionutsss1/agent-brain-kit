"""kitconfig - reads the one kit config file (config/kit.json) for every script and hook.

Where the config is found, first match wins:
  1. $AGENT_KIT_CONFIG
  2. $AGENT_KIT_HOME/config/kit.json
  3. <this repo>/config/kit.json
  4. <this repo>/config/kit.example.json   (so --help and dry runs work before setup)

Strings may use {kit_home}; a leading ~ is expanded. $AGENT_KIT_HOME overrides "kit_home".
Plain Python 3 standard library. Never reads or prints keys.
"""
import datetime
import json
import os

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
_CACHE = {}


def config_path():
    env = os.environ.get("AGENT_KIT_CONFIG")
    if env:
        return os.path.expanduser(env)
    cands = []
    home = os.environ.get("AGENT_KIT_HOME")
    if home:
        cands.append(os.path.join(os.path.expanduser(home), "config", "kit.json"))
    cands += [os.path.join(REPO, "config", "kit.json"), os.path.join(REPO, "config", "kit.example.json")]
    for c in cands:
        if os.path.isfile(c):
            return c
    return cands[-1]


def _expand(value, kit_home):
    if isinstance(value, str):
        return os.path.expanduser(value.replace("{kit_home}", kit_home))
    if isinstance(value, list):
        return [_expand(v, kit_home) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v, kit_home) for k, v in value.items()}
    return value


def load(path=None):
    path = path or config_path()
    if path in _CACHE:
        return _CACHE[path]
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise SystemExit("kit config %s is missing or not valid JSON: %s" % (path, e))
    kit_home = os.path.expanduser(os.environ.get("AGENT_KIT_HOME") or raw.get("kit_home") or "~/agent-brain-kit-home")
    cfg = _expand(raw, kit_home)
    cfg["kit_home"] = kit_home
    cfg["_path"] = path
    paths = cfg.setdefault("paths", {})
    defaults = {"team": "team", "brain": "team/brain", "activity": "team/activity/activity.jsonl",
                "accounts": "accounts", "ledger": "ledger", "logs": "logs", "secrets": "secrets"}
    for k, rel in defaults.items():
        paths.setdefault(k, os.path.join(kit_home, rel))
    _CACHE[path] = cfg
    return cfg


def path(name, cfg=None):
    return (cfg or load())["paths"][name]


def accounts(cfg=None, kind="claude"):
    """Account dicts of one kind ("claude" plan logins by default; "api-key" for paid keys; None = all)."""
    out = []
    for a in (cfg or load()).get("accounts", []):
        if isinstance(a, dict) and a.get("name") and (kind is None or a.get("kind", "claude") == kind):
            out.append(a)
    return out


def account_names(cfg=None, kind="claude"):
    return [a["name"] for a in accounts(cfg, kind)]


def account(name, cfg=None):
    for a in accounts(cfg, None):
        if a["name"] == name:
            return a
    return None


def cap(name, t, cfg=None):
    """Week cap in percent for an account at time t. A cap_schedule ([{until, cap}], first match wins)
    holds dated owner limits; after the last date, cap_percent applies."""
    a = account(name, cfg) or {}
    for step in a.get("cap_schedule") or []:
        try:
            until = datetime.datetime.strptime(step["until"], "%Y-%m-%dT%H:%M").timestamp()
        except (KeyError, ValueError, TypeError):
            continue
        if t < until:
            return float(step.get("cap", a.get("cap_percent", 95)))
    return float(a.get("cap_percent", 95))


def account_from_env(cfg=None):
    """The account a session runs as: the folder name of CLAUDE_CONFIG_DIR under the accounts folder."""
    d = os.environ.get("CLAUDE_CONFIG_DIR", "").rstrip("/")
    if not d:
        return ""
    try:
        root = os.path.realpath(path("accounts", cfg))
        real = os.path.realpath(d)
        if real.startswith(root + os.sep):
            return real[len(root) + 1:].split(os.sep)[0]
    except SystemExit:
        pass
    return os.path.basename(d)
