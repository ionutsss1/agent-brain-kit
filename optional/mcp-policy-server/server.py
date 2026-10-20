#!/usr/bin/env python3
"""Example MCP server (stdio, newline-delimited JSON-RPC) with a policy in front of every tool.

It shows the pattern: give agents a few bounded tools instead of a raw shell, and refuse forbidden
accounts, folders and actions in one place (policy.py). Tools (every one accepts dry_run):
  kit_status      the brain lease and each account's usage line (read-only)
  activity_tail   the last n activity-log lines, optional literal filter
  read_note       one text file under mcp.allowed_read_roots (secrets refused), at most 200 KB
  run_check       one named command from mcp.checks (argv list, no shell, 60 s timeout)
Every call is written to <paths.logs>/mcp_audit.jsonl. Standard library only, Python 3.9+.

Register it (project .mcp.json):
  {"mcpServers": {"kit-policy": {"command": "python3", "args": ["<kit repo>/optional/mcp-policy-server/server.py"]}}}
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "bin"))
import kitconfig as K  # noqa: E402
from policy import Policy, Refusal  # noqa: E402

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")


def schema(props, required=()):
    props = dict(props, dry_run={"type": "boolean", "default": False})
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


TOOLS = [
    {"name": "kit_status", "description": "Brain lease holder and each account's usage, cap and headroom.",
     "inputSchema": schema({})},
    {"name": "activity_tail", "description": "Last n lines of the activity log (hand-offs between sessions).",
     "inputSchema": schema({"n": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20},
                            "filter": {"type": "string", "default": ""}})},
    {"name": "read_note", "description": "Read one text file under the allowed roots. Secrets are refused.",
     "inputSchema": schema({"path": {"type": "string"}}, ["path"])},
    {"name": "run_check", "description": "Run one named, pre-approved check command (no shell).",
     "inputSchema": schema({"name": {"type": "string"}}, ["name"])},
]


class Server(object):
    def __init__(self, cfg=None):
        self.cfg = cfg or K.load()
        self.policy = Policy(self.cfg)
        self.audit_path = os.path.join(os.environ.get("KIT_LOGS") or K.path("logs", self.cfg), "mcp_audit.jsonl")

    def audit(self, name, args, outcome):
        try:
            os.makedirs(os.path.dirname(self.audit_path), exist_ok=True)
            with open(self.audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": name,
                                    "args": {k: (v if len(str(v)) < 200 else str(v)[:200]) for k, v in args.items()},
                                    "outcome": outcome}) + "\n")
        except OSError:
            pass

    def call(self, name, args):
        if not isinstance(args, dict):
            raise Refusal("TYPE", "arguments must be an object")
        tool = next((t for t in TOOLS if t["name"] == name), None)
        if not tool:
            raise Refusal("UNKNOWN_TOOL", name)
        allowed = set(tool["inputSchema"]["properties"])
        extra = set(args) - allowed
        if extra:
            raise Refusal("UNKNOWN_ARGUMENT", ", ".join(sorted(extra)))
        dry = args.get("dry_run", False) is True
        if name == "kit_status":
            if dry:
                return "dry run: would read the lease and the usage ledger"
            import brainlib as B
            lines = [B.describe(B.read_lease())]
            for a in B.ACCOUNTS:
                u = B.usage(a)
                lines.append("%s: %s; limit: %s; headroom %.1f" % (a, B.summary(u), B.at_limit(u) or "none",
                                                                   B.headroom(u)))
            return "\n".join(lines)
        if name == "activity_tail":
            n = self.policy.number(args.get("n", 20), 1, 200, "n")
            flt = self.policy.text(args.get("filter", ""), "filter")
            if dry:
                return "dry run: would return up to %d lines" % n
            try:
                with open(os.environ.get("KIT_ACTIVITY") or K.path("activity", self.cfg), encoding="utf-8") as f:
                    lines = [ln.rstrip("\n") for ln in f if flt in ln]
            except OSError:
                return "no activity log yet"
            return "\n".join(lines[-n:]) or "no matching lines"
        if name == "read_note":
            real = self.policy.read_path(args.get("path"))
            if dry:
                return "dry run: would read %s" % real
            if os.path.getsize(real) > 200 * 1024:
                raise Refusal("SIZE", "file is larger than 200 KB")
            with open(real, encoding="utf-8", errors="replace") as f:
                return f.read()
        if name == "run_check":
            argv = self.policy.check_name(args.get("name"))
            if dry:
                return "dry run: would run %s" % " ".join(argv)
            r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            return ("exit %d\n%s%s" % (r.returncode, r.stdout, r.stderr))[-8000:]
        raise Refusal("UNKNOWN_TOOL", name)

    def dispatch(self, msg):
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            return {"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) else None,
                    "error": {"code": -32600, "message": "Invalid request"}}
        method, ident, params = msg["method"], msg.get("id"), msg.get("params") or {}
        if ident is None:   # a notification: no answer
            return None
        if method == "initialize":
            requested = params.get("protocolVersion")
            return {"jsonrpc": "2.0", "id": ident, "result": {
                "protocolVersion": requested if requested in PROTOCOLS else PROTOCOLS[0],
                "capabilities": {"tools": {}}, "serverInfo": {"name": "kit-policy", "version": "1.0.0"}}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": ident, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": ident, "result": {"tools": TOOLS}}
        if method == "tools/call":
            name, args = params.get("name"), params.get("arguments") or {}
            try:
                text = self.call(name, args)
                self.audit(name, args, "ok")
                return {"jsonrpc": "2.0", "id": ident, "result": {"content": [{"type": "text", "text": text}]}}
            except Refusal as e:
                self.audit(name, args if isinstance(args, dict) else {}, "refused " + e.rule)
                return {"jsonrpc": "2.0", "id": ident, "result": {"isError": True,
                        "content": [{"type": "text", "text": "REFUSED " + str(e)}]}}
            except (OSError, subprocess.SubprocessError) as e:
                self.audit(name, args if isinstance(args, dict) else {}, "error")
                return {"jsonrpc": "2.0", "id": ident, "result": {"isError": True,
                        "content": [{"type": "text", "text": "ERROR " + e.__class__.__name__}]}}
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "Method not found"}}


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    server = Server()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            reply = server.dispatch(json.loads(line))
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
