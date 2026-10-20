"""Policy for the example MCP server: every tool argument passes through here before anything runs.

The rules come from the kit config: "mcp" (allowed_read_roots, forbidden_words, checks) and "guard"
(secret_paths, secret_basename_patterns). A refusal names its rule, so the agent knows why.
Dependency-free; the tests exercise it directly.
"""
import os
import re


class Refusal(ValueError):
    def __init__(self, rule, detail):
        self.rule = rule
        super().__init__("%s: %s" % (rule, detail))


def refuse(rule, detail):
    raise Refusal(rule, detail)


class Policy(object):
    def __init__(self, cfg):
        mcp, guard = cfg.get("mcp") or {}, cfg.get("guard") or {}
        self.roots = [os.path.realpath(os.path.expanduser(r)) for r in mcp.get("allowed_read_roots", [])]
        self.words = [w.lower() for w in mcp.get("forbidden_words", []) if w]
        self.checks = {k: list(v) for k, v in (mcp.get("checks") or {}).items() if isinstance(v, list) and v}
        self.secret_paths = [os.path.realpath(os.path.expanduser(p)) for p in guard.get("secret_paths", []) if p]
        self.secret_names = [re.compile(r, re.I) for r in guard.get("secret_basename_patterns", [])]

    def text(self, value, what="argument"):
        if not isinstance(value, str):
            refuse("TYPE", "%s must be text" % what)
        if len(value) > 4000:
            refuse("SIZE", "%s is too long" % what)
        low = value.lower()
        for w in self.words:
            if re.search(r"(?:^|[^a-z0-9_])%s(?:$|[^a-z0-9_])" % re.escape(w), low):
                refuse("FORBIDDEN_WORD", "%s names %r, which this server never touches" % (what, w))
        return value

    def number(self, value, lo, hi, what):
        if type(value) is not int or not lo <= value <= hi:
            refuse("RANGE", "%s must be an integer from %d to %d" % (what, lo, hi))
        return value

    def read_path(self, value):
        self.text(value, "path")
        if "\x00" in value or any(part == ".." for part in re.split(r"[\\/]", value)):
            refuse("TRAVERSAL", "no '..' in paths")
        real = os.path.realpath(os.path.expanduser(value))
        if any(real == s or real.startswith(s + os.sep) for s in self.secret_paths) or \
                any(r.search(os.path.basename(real)) for r in self.secret_names):
            refuse("SECRET_PATH", "secret paths are never read or returned")
        if not any(real == r or real.startswith(r + os.sep) for r in self.roots):
            refuse("OUTSIDE_ROOTS", "only files under the allowed read roots")
        return real

    def check_name(self, value):
        self.text(value, "check")
        if value not in self.checks:
            refuse("UNKNOWN_CHECK", "allowed checks: %s" % (", ".join(sorted(self.checks)) or "none"))
        return self.checks[value]
