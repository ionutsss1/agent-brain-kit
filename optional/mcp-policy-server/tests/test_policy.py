"""Tests for the example MCP policy server: python3 -B -m unittest discover -s optional/mcp-policy-server/tests"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from policy import Policy, Refusal  # noqa: E402
import server as S  # noqa: E402


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.notes = os.path.join(self.tmp, "team")
        self.secrets = os.path.join(self.tmp, "secrets")
        os.makedirs(self.notes)
        os.makedirs(self.secrets)
        with open(os.path.join(self.notes, "plan.md"), "w") as f:
            f.write("# Plan\nship it\n")
        with open(os.path.join(self.notes, ".env"), "w") as f:
            f.write("TOKEN=x\n")
        with open(os.path.join(self.secrets, "k.txt"), "w") as f:
            f.write("x\n")
        self.cfg = {"paths": {"logs": os.path.join(self.tmp, "logs"), "activity": os.path.join(self.tmp, "a.jsonl"),
                              "ledger": self.tmp, "accounts": self.tmp, "brain": self.tmp, "team": self.notes,
                              "secrets": self.secrets},
                    "mcp": {"allowed_read_roots": [self.tmp], "forbidden_words": ["owner-account"],
                            "checks": {"echo": [sys.executable, "-c", "print('check ok')"]}},
                    "guard": {"secret_paths": [self.secrets], "secret_basename_patterns": [r"^\.env$"]}}
        self.server = S.Server(self.cfg)

    def call(self, name, args, ident=1):
        return self.server.dispatch({"jsonrpc": "2.0", "id": ident, "method": "tools/call",
                                     "params": {"name": name, "arguments": args}})["result"]

    def test_lifecycle(self):
        r = self.server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-03-26")
        self.assertIsNone(self.server.dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        names = [t["name"] for t in self.server.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]]
        self.assertEqual(names, ["kit_status", "activity_tail", "read_note", "run_check"])
        self.assertEqual(self.server.dispatch({"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"], -32601)

    def test_read_note_allowed_and_refused(self):
        self.assertIn("ship it", self.call("read_note", {"path": os.path.join(self.notes, "plan.md")})["content"][0]["text"])
        for path, rule in ((os.path.join(self.notes, ".env"), "SECRET_PATH"),
                           (os.path.join(self.secrets, "k.txt"), "SECRET_PATH"),
                           (os.path.join(self.notes, "..", "team", "plan.md"), "TRAVERSAL"),
                           ("/etc/hosts", "OUTSIDE_ROOTS")):
            r = self.call("read_note", {"path": path})
            self.assertTrue(r.get("isError"), path)
            self.assertIn(rule, r["content"][0]["text"])

    def test_forbidden_word_and_unknown_args(self):
        r = self.call("activity_tail", {"filter": "owner-account"})
        self.assertIn("FORBIDDEN_WORD", r["content"][0]["text"])
        r = self.call("activity_tail", {"n": 5, "shell": "rm"})
        self.assertIn("UNKNOWN_ARGUMENT", r["content"][0]["text"])
        r = self.call("activity_tail", {"n": 999})
        self.assertIn("RANGE", r["content"][0]["text"])

    def test_checks_and_dry_run(self):
        self.assertIn("check ok", self.call("run_check", {"name": "echo"})["content"][0]["text"])
        self.assertIn("UNKNOWN_CHECK", self.call("run_check", {"name": "rm -rf /"})["content"][0]["text"])
        self.assertIn("dry run", self.call("run_check", {"name": "echo", "dry_run": True})["content"][0]["text"])
        with open(self.server.audit_path) as f:
            outcomes = [json.loads(line)["outcome"] for line in f]
        self.assertIn("refused UNKNOWN_CHECK", outcomes)

    def test_policy_direct(self):
        p = Policy(self.cfg)
        with self.assertRaises(Refusal):
            p.text(123)
        self.assertEqual(p.number(5, 1, 10, "n"), 5)


if __name__ == "__main__":
    unittest.main()
