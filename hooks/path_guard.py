#!/usr/bin/env python3
"""PreToolUse path, secret and command guard. Every rule comes from the "guard" section of the kit config.

File tools (Read, Write, Edit, MultiEdit, NotebookEdit, Glob, Grep):
  - path_map: [{"prefix": "X:/project", "mount": "/mnt/project"}] rewrites paths written for a remote
    machine to the local mount (hookSpecificOutput.updatedInput sends back the whole input with only the
    path fields changed). Optional; empty by default.
  - mount_sentinel: a file under a mount that must exist; when it is missing the call is refused
    ("share not mounted") instead of tools reporting missing files.
  - secret_paths (folders or files) and secret_basename_patterns (regexes on the file name) are never
    read, written or searched.
  - no_write_paths: never written by agents (for example the owner's own working copy).
  - max_search_depth_on_mount: recursive Grep/Glob closer to a mount root than this is refused (slow over
    a network share); run such searches on the remote machine through the runner instead.
Bash:
  - secret_words (regexes): a command that names a secret is refused.
  - forbidden_commands: [{"regex", "reason"}] refused with the reason (git writes, force stops, raw builds...).
  - remote_only_prefixes: a command that names one of these prefixes must start with the runner
    (runner.name, default "ws"): it only exists on the remote machine.
  - recursive scans (find, rg, grep -r, du, ls -R, cp -r) of a mount root are refused like Grep/Glob.

Standard library only, Python 3.9+. Reads the hook JSON on stdin, prints JSON or nothing. Exit 0 always
(a deny is a JSON decision, not an exit code).
"""
import json
import os
import posixpath
import re
import shlex
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin"))
import kitconfig as K  # noqa: E402

CFG = K.load()
G = CFG.get("guard", {})
RUNNER = (CFG.get("runner") or {}).get("name", "ws")
FILE_TOOLS = ("Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep")
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
PATH_KEYS = ("file_path", "notebook_path", "path")


def _norm(p):
    return posixpath.normpath(os.path.expanduser(p)).rstrip("/") if p else ""


def _lower_prefix(p):
    return p.replace("\\", "/").rstrip("/").lower()


PATH_MAP = [(_lower_prefix(m["prefix"]), _norm(m["mount"])) for m in G.get("path_map", [])
            if isinstance(m, dict) and m.get("prefix") and m.get("mount")]
MOUNTS = [m for _, m in PATH_MAP]
SENTINEL = G.get("mount_sentinel") or ""
SECRET_PATHS = [_norm(p) for p in G.get("secret_paths", []) if p]
SECRET_BASENAMES = [re.compile(r, re.I) for r in G.get("secret_basename_patterns", [])]
NO_WRITE = [_norm(p) for p in G.get("no_write_paths", []) if p]
SECRET_WORDS = re.compile("|".join("(?:%s)" % r for r in G.get("secret_words", [])), re.I) \
    if G.get("secret_words") else None
FORBIDDEN = [(re.compile(f["regex"], re.I), f.get("reason", "Refused by the guard config."))
             for f in G.get("forbidden_commands", []) if isinstance(f, dict) and f.get("regex")]
REMOTE_ONLY = [_lower_prefix(p) for p in G.get("remote_only_prefixes", []) if p]
MAX_DEPTH = int(G.get("max_search_depth_on_mount", 2))
SECRET_PATH_WORDS = [p for p in SECRET_PATHS if p]


def emit(decision=None, reason=None, updated=None, context=None):
    hso = {"hookEventName": "PreToolUse"}
    if decision:
        hso["permissionDecision"] = decision
    if reason:
        hso["permissionDecisionReason"] = reason
    if updated is not None:
        hso["updatedInput"] = updated
    if context:
        hso["additionalContext"] = context
    sys.stdout.write(json.dumps({"hookSpecificOutput": hso}))
    sys.stdout.flush()
    sys.exit(0)


def deny(reason):
    emit("deny", reason)


def mounted(timeout=3.0):
    """Sentinel check in a thread so a hung network mount cannot hang the tool call."""
    if not SENTINEL:
        return True
    box = []
    t = threading.Thread(target=lambda: box.append(os.path.isfile(os.path.expanduser(SENTINEL))))
    t.daemon = True
    t.start()
    t.join(timeout)
    return bool(box and box[0])


def map_path(value):
    """(mapped value, changed) for one path string written with a remote prefix."""
    if not isinstance(value, str):
        return value, False
    low = _lower_prefix(value.strip())
    for prefix, mount in PATH_MAP:
        if low == prefix or low.startswith(prefix + "/"):
            rest = value.strip().replace("\\", "/")[len(prefix):]
            return posixpath.normpath(mount + "/" + rest.lstrip("/")) if rest.strip("/") else mount, True
    return value, False


def under(path, root):
    return path == root or path.startswith(root + "/")


def mount_rel(path):
    """(mount, path relative to it) when the path is on a mount, else (None, None)."""
    if not isinstance(path, str) or not path.startswith(("/", "~")):
        return None, None
    p = _norm(path)
    for m in MOUNTS:
        if under(p.lower(), m.lower()):
            return m, p[len(m) + 1:] if len(p) > len(m) else ""
    return None, None


def is_secret(path):
    if not isinstance(path, str) or not path:
        return False
    p = _norm(path)
    if any(under(p, s) for s in SECRET_PATHS):
        return True
    base = posixpath.basename(p)
    return any(r.search(base) for r in SECRET_BASENAMES)


def holds_secret(root):
    """True when a recursive search rooted here would reach a configured secret path."""
    r = _norm(root)
    return any(under(s, r) for s in SECRET_PATHS)


def depth(rel):
    return 0 if not rel else rel.count("/") + 1


def glob_root(pattern):
    parts = []
    for seg in pattern.split("/"):
        if any(c in seg for c in "*?[{"):
            break
        parts.append(seg)
    return "/".join(parts) or "/"


# ---------------------------------------------------------------- file tools

def check_file_tool(tool, ti, data):
    updated, changed = dict(ti), []
    for k in PATH_KEYS:
        if k in ti:
            new, ch = map_path(ti[k])
            if ch:
                updated[k] = new
                changed.append("%s -> %s" % (ti[k], new))
    if tool == "Glob" and isinstance(ti.get("pattern"), str):
        new, ch = map_path(ti["pattern"])
        if ch:
            updated["pattern"] = new
            changed.append("%s -> %s" % (ti["pattern"], new))
    paths = [updated[k] for k in PATH_KEYS if isinstance(updated.get(k), str)]
    roots = list(paths)
    if tool in ("Glob", "Grep") and "path" not in updated:
        roots.append(data.get("cwd") or "")
    if tool == "Glob" and isinstance(updated.get("pattern"), str) and updated["pattern"].startswith("/"):
        roots.append(glob_root(updated["pattern"]))
        paths.append(updated["pattern"])

    if any(mount_rel(p)[0] for p in paths + roots) and not mounted():
        deny("The shared folder is not mounted (%s is missing), so this file is not reachable. Ask the owner "
             "to mount it; do not guess file contents." % SENTINEL)
    for p in paths:
        if is_secret(p):
            deny("That path holds secrets (owner rule: never open, print or copy them). Work around it.")
    if tool in WRITE_TOOLS:
        for p in paths:
            if any(under(_norm(p), n) for n in NO_WRITE):
                deny("That folder is never changed by agents (guard.no_write_paths).")
    if tool in ("Glob", "Grep"):
        for r in roots:
            if not r:
                continue
            if is_secret(r):
                deny("That folder holds secrets (owner rule). Search somewhere else.")
            if tool == "Grep" and holds_secret(r):
                deny("A search of %s would read secret files. Point it at a narrower folder." % r)
            m, rel = mount_rel(r)
            pattern = updated.get("pattern") if tool == "Glob" else None
            recursive = tool == "Grep" or (isinstance(pattern, str) and "**" in pattern)
            if m and recursive and depth(rel) <= MAX_DEPTH and not os.path.isfile(r):
                deny("%s is too big to search over the network. Run the search on the remote machine: "
                     "%s run -- 'rg -n PATTERN <folder>'." % (r, RUNNER))
    if changed:
        mode = data.get("permission_mode")
        decision = "ask" if (tool in WRITE_TOOLS and mode == "plan") else "allow"
        emit(decision, "remote path mapped to the mount" if decision == "ask" else None, updated,
             "Path mapped: " + "; ".join(changed))


# ---------------------------------------------------------------- Bash

def split_segments(cmd):
    """Split a shell line on unquoted ; && || | & and newlines; heredoc bodies stay with the segment that
    opened them. Rough, but quote-aware."""
    segs, cur, quote, heredocs = [], [], None, []
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        if quote:
            cur.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                cur.append(cmd[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            cur.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            cur.append(cmd[i:i + 2])
            i += 2
            continue
        if c == "<" and cmd.startswith("<<", i) and not cmd.startswith("<<<", i):
            m = re.match(r"<<-?\s*(['\"]?)([A-Za-z0-9_]+)\1", cmd[i:])
            if m:
                heredocs.append(m.group(2))
                cur.append(m.group(0))
                i += len(m.group(0))
                continue
        if c == "\n":
            if heredocs:
                j = i + 1
                while heredocs and j <= n:
                    end = cmd.find("\n", j)
                    line = cmd[j:] if end == -1 else cmd[j:end]
                    cur.append("\n" + line)
                    j = n + 1 if end == -1 else end + 1
                    if line.strip() == heredocs[0]:
                        heredocs.pop(0)
                i = j
                continue
            segs.append("".join(cur))
            cur = []
            i += 1
            continue
        if c in ";|&":
            segs.append("".join(cur))
            cur = []
            i += 2 if cmd.startswith(("&&", "||"), i) else 1
            continue
        cur.append(c)
        i += 1
    segs.append("".join(cur))
    return [s.strip() for s in segs if s.strip()]


def words(seg):
    try:
        return shlex.split(seg, comments=False, posix=True)
    except ValueError:
        return seg.split()


def first_word(ws_):
    for w in ws_:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w) or w in ("command", "exec", "time", "nohup", "env"):
            continue
        return w
    return ""


def is_runner(word):
    return word == RUNNER or word.endswith("/" + RUNNER)


def names_remote(seg):
    low = seg.replace("\\", "/").lower()
    return any(p in low for p in REMOTE_ONLY)


def check_bash(cmd):
    if not isinstance(cmd, str) or not cmd.strip():
        return
    if SECRET_WORDS and SECRET_WORDS.search(cmd):
        deny("This command names a secret file (guard.secret_words). Owner rule: never open, print or copy "
             "secrets. Find another way.")
    low = cmd.lower()
    if any(s.lower() in low for s in SECRET_PATH_WORDS):
        deny("This command names a secret folder (guard.secret_paths). Find another way.")
    for rx, reason in FORBIDDEN:
        if rx.search(cmd):
            deny(reason)
    need_mount_check = False
    for seg in split_segments(cmd):
        ws_ = words(seg)
        fw = first_word(ws_)
        if REMOTE_ONLY and names_remote(seg) and not is_runner(fw):
            deny("This command names a path that exists only on the remote machine. Run it there: "
                 "%s run -- '<command>' (quote the whole command when it has pipes, && or globs). File tools: "
                 "use the mounted path." % RUNNER)
        if is_runner(fw):
            continue
        rels = []
        for w in ws_:
            m, rel = mount_rel(w.rstrip("/")) if w.startswith("/") else (None, None)
            if m:
                rels.append((m, rel))
        if rels:
            need_mount_check = True
            base = posixpath.basename(fw)
            recursive = base in ("find", "rg", "du", "tree", "fd") or \
                (base in ("grep", "egrep") and any(re.match(r"^-[A-Za-z]*[rR]", w) or w == "--recursive"
                                                    for w in ws_)) or \
                (base == "ls" and any(re.match(r"^-[A-Za-z]*R", w) for w in ws_)) or \
                (base in ("cp", "rsync") and any(re.match(r"^-[A-Za-z]*[rRa]", w) for w in ws_))
            if recursive:
                for m, rel in rels:
                    if depth(rel) <= MAX_DEPTH or holds_secret(m + "/" + rel):
                        deny("Scanning %s/%s over the network is too slow or reaches secrets. Run it on the "
                             "remote machine: %s run -- '<command>'." % (m, rel, RUNNER))
    if need_mount_check and not mounted():
        deny("The shared folder is not mounted (%s is missing). Ask the owner to mount it." % SENTINEL)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except ValueError:
        sys.stderr.write("path_guard: no JSON on stdin\n")
        sys.exit(1)
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    if not isinstance(ti, dict):
        sys.exit(0)
    if tool in FILE_TOOLS:
        check_file_tool(tool, ti, data)
    elif tool == "Bash":
        check_bash(ti.get("command"))
    sys.exit(0)


if __name__ == "__main__":
    main()
