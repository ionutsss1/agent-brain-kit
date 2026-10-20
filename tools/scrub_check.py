#!/usr/bin/env python3
"""scrub_check - white-label check: no secrets, personal data or source-project terms in the repo.

  python3 tools/scrub_check.py [REPO] [--extra-terms FILE] [--show]

Scans every text file and every path name under REPO (default: this repo) for:
  - the built-in denylist: names and terms of the project this kit came from. The list is stored ROT13-encoded
    so this file does not contain the words it looks for (and can scan itself).
  - secrets: API keys and tokens (Anthropic, OpenAI-style, GitHub, AWS, Slack), private key blocks,
    64-character hex strings
  - personal data: e-mail addresses, home folders (/Users/<name>, /home/<name>, C:\\Users\\<name>)
  - addresses: IPv4 addresses, artifact share links, GitHub user links, *.local host names
  - --extra-terms FILE: one more term per line (company names, people, products), plain text, case-insensitive.
Exit 0 with "0 hits" when clean, 1 with the hits listed by file, line and rule (the term itself is shown only
with --show).
"""
import argparse
import codecs
import os
import re
import sys

DENY_ROT13 = [
    "zrgva2", "z2qri", "envqrem", "bphyhf", "jneevbe", "urnil fjbeq", "urnil-fjbeq", "tboyva", "tneevfba",
    "pynhqrrlr", "vbahg", "vbahț", "fynohvbahg", "z2ud", "z2yno", "z2jf", "z2oenva", "sbepr2", "s2ncv", "s2wbo",
    "pyvrag-yvfgra", "pyvrag-yvsr", "rlr_cevingr", "rlr_ybtva", "jngresbeq", "ylxbf", "66qr4sq1", "r9o27p29",
]
DENY_WORD_ROT13 = ["p9"]   # matched as a whole word only
PATTERNS = [
    ("anthropic-key", r"sk-ant-[A-Za-z0-9_-]{10,}"),
    ("api-key", r"\bsk-[A-Za-z0-9]{20,}"),
    ("github-token", r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    ("aws-key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("slack-token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    ("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("hex-64", r"\b[0-9a-f]{64}\b"),
    ("email", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("home-folder", r"/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|[A-Za-z]:\\\\?Users\\\\?[A-Za-z0-9._-]+"),
    ("ipv4", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    ("artifact-link", r"claude\.ai/(?:artifact|public/artifacts)/[A-Za-z0-9-]+"),
    ("github-user-link", r"github\.com/[A-Za-z0-9-]+"),
    ("local-host", r"\b[A-Za-z0-9-]+\.local\b"),
]
SKIP_DIRS = {".git", "node_modules", "__pycache__", "dist"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".glb", ".zip", ".gz", ".pyc", ".ico"}


def rules(extra_terms):
    out = []
    for i, t in enumerate(DENY_ROT13):
        out.append(("denylist#%d" % (i + 1), re.compile(re.escape(codecs.decode(t, "rot13")), re.I)))
    for i, t in enumerate(DENY_WORD_ROT13):
        out.append(("denylist-word#%d" % (i + 1), re.compile(r"\b%s\b" % re.escape(codecs.decode(t, "rot13")), re.I)))
    for i, t in enumerate(extra_terms):
        out.append(("extra#%d" % (i + 1), re.compile(re.escape(t), re.I)))
    out += [(name, re.compile(rx)) for name, rx in PATTERNS]
    return out


def scan(root, extra_terms, show=False):
    hits = []
    rs = rules(extra_terms)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            for rname, rx in rs:
                m = rx.search(rel)
                if m:
                    hits.append((rel, 0, rname, m.group(0) if show else ""))
            if os.path.splitext(name)[1].lower() in BINARY_EXT:
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except (UnicodeDecodeError, OSError):
                hits.append((rel, 0, "unreadable-or-binary", ""))
                continue
            for no, line in enumerate(lines, 1):
                for rname, rx in rs:
                    m = rx.search(line)
                    if m:
                        hits.append((rel, no, rname, m.group(0) if show else ""))
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    ap.add_argument("--extra-terms", help="file with one extra term per line")
    ap.add_argument("--show", action="store_true", help="print the matched text too")
    a = ap.parse_args()
    extra = []
    if a.extra_terms:
        with open(a.extra_terms, encoding="utf-8") as f:
            extra = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    hits = scan(a.root, extra, a.show)
    files = sum(len(fs) for _, _, fs in os.walk(a.root))
    for rel, no, rname, text in hits:
        print("%s:%d: %s%s" % (rel, no, rname, (" [%s]" % text) if text else ""))
    print("scrub_check: %d hits in %d files (%d denylist terms, %d patterns, %d extra terms)"
          % (len(hits), files, len(DENY_ROT13) + len(DENY_WORD_ROT13), len(PATTERNS), len(extra)))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
