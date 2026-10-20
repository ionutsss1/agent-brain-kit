#!/bin/bash
# selftest.sh - offline checks for the whole kit. Uses a throw-away kit home; touches nothing else.
#   bash tools/selftest.sh          run everything (node is needed for the board tests)
# Exit 0 when every check passes. bash 3.2 compatible.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd -P)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/kit-selftest.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
export AGENT_KIT_HOME="$TMP/kithome"
export AGENT_KIT_CONFIG="$REPO/config/kit.example.json"
export KIT_BRAIN_DIR="$TMP/kithome/team/brain"
unset CLAUDE_CONFIG_DIR CLAUDE_CODE_SESSION_ID CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SESSION_ATTENDED KIT_WORKER
FAIL=0
ok()   { echo "PASS  $1"; }
bad()  { echo "FAIL  $1"; FAIL=1; }
check() {  # check <name> <command...>: passes when the command exits 0
  local name="$1"; shift
  if out="$("$@" 2>&1)"; then ok "$name"; else bad "$name"; echo "$out" | tail -5 | sed 's/^/      /'; fi
}
expect() {  # expect <name> <pattern> <command...>: passes when the output matches the pattern
  local name="$1" pat="$2"; shift 2
  out="$("$@" 2>&1)"
  if echo "$out" | grep -E -q -- "$pat"; then ok "$name"; else bad "$name"; echo "$out" | tail -5 | sed 's/^/      /'; fi
}
mkdir -p "$AGENT_KIT_HOME/accounts/main" "$AGENT_KIT_HOME/accounts/second" "$AGENT_KIT_HOME/ledger"

echo "== shell syntax"
for f in "$REPO/setup.sh" "$REPO/bin/cca" "$REPO/tools/selftest.sh"; do
  check "bash -n $(basename "$f")" bash -n "$f"
done

echo "== setup.sh (into a temp home)"
expect "setup.sh --help" "never overwrites" bash "$REPO/setup.sh" --help
expect "setup.sh --dry-run" "\[dry-run\]" env -u AGENT_KIT_CONFIG bash "$REPO/setup.sh" --dry-run --home "$TMP/sethome"
check "setup.sh real run" env -u AGENT_KIT_CONFIG bash "$REPO/setup.sh" --home "$TMP/sethome"
check "setup.sh filled the settings" python3 -c '
import json, sys
for p in sys.argv[1:]:
    t = open(p).read(); assert "__KIT" not in t, p; json.loads(t)' \
  "$TMP/sethome/accounts/main/settings.json" "$TMP/sethome/team/.claude/settings.json" "$TMP/sethome/config/kit.json"
check "setup.sh second run keeps files" env -u AGENT_KIT_CONFIG bash "$REPO/setup.sh" --home "$TMP/sethome"
expect "setup.sh --print-launchd" "StartInterval" bash "$REPO/setup.sh" --print-launchd --home "$TMP/sethome"
expect "secrets folder is private" "^700$" python3 -c 'import os, sys; print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])' "$TMP/sethome/secrets"

echo "== python compile"
for f in "$REPO"/bin/kitconfig.py "$REPO"/bin/brainlib.py "$REPO"/bin/brainlease "$REPO"/bin/brainwatch \
         "$REPO"/bin/apijob "$REPO"/hooks/*.py "$REPO"/board/*.py "$REPO"/tools/*.py \
         "$REPO"/optional/remote-runner/ws "$REPO"/optional/remote-runner/*.py \
         "$REPO"/optional/mcp-policy-server/*.py; do
  [ -f "$f" ] || continue
  check "compile $(basename "$f")" python3 -c 'import sys; compile(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1], "exec")' "$f"
done

echo "== --help / dry runs"
expect "brainlease --help" "acquire" python3 "$REPO/bin/brainlease" --help
expect "brainlease who (no lease)" "no brain lease holder" python3 "$REPO/bin/brainlease" who
expect "brainlease status" '"accounts"' python3 "$REPO/bin/brainlease" status
expect "brainlease acquire" "acquired by main" python3 "$REPO/bin/brainlease" acquire --account main --session s-one
expect "brainlease refuses a second holder" "refused" python3 "$REPO/bin/brainlease" acquire --account second --session s-two
expect "brainwatch --help" "one pass" python3 "$REPO/bin/brainwatch" --help
expect "brainwatch --explain (fresh lease)" "ok: main" python3 "$REPO/bin/brainwatch" --explain
expect "brainwatch stale -> takeover pick" "takeover due main -> second" env KIT_NOW=$(( $(date +%s) + 3600 )) KIT_ALIVE=none python3 "$REPO/bin/brainwatch" --dry-run
expect "brainlease release" "released by main" python3 "$REPO/bin/brainlease" release --session s-one
expect "apijob --help" "max-budget-usd" python3 "$REPO/bin/apijob" --help
expect "apijob --total" 'spent \$0.00 of \$100' env KIT_LEDGER="$TMP/kithome/ledger" python3 "$REPO/bin/apijob" --total
expect "apijob --dry-run" "dry run: would run" env KIT_LEDGER="$TMP/kithome/ledger" python3 "$REPO/bin/apijob" --dry-run t1 "$TMP/t1.jsonl" "say ok"
echo '{"cost_usd": 95}' > "$TMP/kithome/ledger/api_spend.jsonl"
expect "apijob refuses over the total cap" "REFUSED" env KIT_LEDGER="$TMP/kithome/ledger" python3 "$REPO/bin/apijob" --dry-run t2 "$TMP/t2.jsonl" "say ok"
expect "cca help" "cca <account>" bash "$REPO/bin/cca" help
expect "cca list" "main" bash "$REPO/bin/cca" list
expect "cca unknown account" "unknown account" bash "$REPO/bin/cca" nobody
expect "statusline" "main \| 5h 12%" env CLAUDE_CONFIG_DIR="$AGENT_KIT_HOME/accounts/main" python3 "$REPO/hooks/statusline.py" <<'EOF'
{"rate_limits": {"five_hour": {"used_percentage": 12, "resets_at": 4102444800}, "seven_day": {"used_percentage": 30, "resets_at": 4102444800}}}
EOF
expect "brain_hook SessionStart" "BRAIN LEASE" python3 "$REPO/hooks/brain_hook.py" <<'EOF'
{"hook_event_name": "SessionStart", "session_id": "s-three"}
EOF
python3 "$REPO/bin/brainlease" acquire --account main --session s-one >/dev/null 2>&1
expect "brain_hook guard warns a non-brain launcher" "NOT the brain" python3 "$REPO/hooks/brain_hook.py" --guard <<'EOF'
{"hook_event_name": "PreToolUse", "session_id": "s-other", "tool_name": "Bash", "tool_input": {"command": "cca second -p 'do it'"}}
EOF
expect "activity_log writes a send line" "^$" env KIT_ACTIVITY="$TMP/act.jsonl" CLAUDE_CONFIG_DIR="$AGENT_KIT_HOME/accounts/main" python3 "$REPO/hooks/activity_log.py" <<'EOF'
{"hook_event_name": "PreToolUse", "session_id": "s-one", "tool_name": "Bash", "tool_input": {"command": "cca second -p \"review the plan\""}}
EOF
expect "activity_log line content" '"to": "claude:second"' cat "$TMP/act.jsonl"
expect "activity_log SessionStart replay" "RECENT" env KIT_ACTIVITY="$TMP/act.jsonl" python3 "$REPO/hooks/activity_log.py" <<'EOF'
{"hook_event_name": "SessionStart", "session_id": "s-four"}
EOF
expect "path_guard denies git push" '"deny"' python3 "$REPO/hooks/path_guard.py" <<'EOF'
{"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}
EOF
expect "path_guard denies a .env read" '"deny"' python3 "$REPO/hooks/path_guard.py" <<'EOF'
{"tool_name": "Read", "tool_input": {"file_path": "/tmp/project/.env"}}
EOF
expect "path_guard allows a normal read" "^$" python3 "$REPO/hooks/path_guard.py" <<'EOF'
{"tool_name": "Read", "tool_input": {"file_path": "/tmp/project/README.md"}}
EOF
expect "path_guard --help" "secret_paths" python3 "$REPO/hooks/path_guard.py" --help

if [ -d "$REPO/optional/remote-runner" ]; then
  echo "== optional: remote runner"
  check "remote runner tests" python3 "$REPO/optional/remote-runner/test_runner.py"
  expect "ws --help" "ws run" python3 "$REPO/optional/remote-runner/ws" --help
  expect "ws_daemon --help" "spool" python3 "$REPO/optional/remote-runner/ws_daemon.py" --help
fi
if [ -d "$REPO/optional/mcp-policy-server" ]; then
  echo "== optional: MCP policy server"
  check "mcp policy server tests" python3 -B -m unittest discover -s "$REPO/optional/mcp-policy-server/tests" -q
fi

echo "== board"
if command -v node >/dev/null 2>&1; then
  for t in "$REPO"/board/tests/test_*.cjs; do check "node $(basename "$t")" node "$t"; done
else
  bad "node is not installed: board tests skipped"
fi
check "board build (example)" python3 "$REPO/board/build.py" --config "$REPO/board/example/board.config.json" \
  --tasks "$REPO/board/example/tasks.json" --briefs "$REPO/board/example/briefs" \
  --goals "$REPO/board/example/goals.json" --out "$TMP/dist"
check "board seed has 5 cards" python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert len(d)==5, len(d)' "$TMP/dist/seed.json"
check "board dist embeds the config" grep -q '"focusTrack": "Platform"' "$TMP/dist/board.html"
check "briefs bundle has EX01" python3 -c 'import json,sys; assert "briefs/EX01.md" in json.load(open(sys.argv[1]))' "$TMP/dist/briefs.json"
expect "make_brief_stub" "5 stubs written" python3 "$REPO/board/make_brief_stub.py" "$REPO/board/example/tasks.json" --briefs "$TMP/stubs"
expect "make_brief_stub keeps existing briefs" "0 stubs written" python3 "$REPO/board/make_brief_stub.py" "$REPO/board/example/tasks.json" --briefs "$TMP/stubs"
expect "make_seed --help" "tasks.json" python3 "$REPO/board/make_seed.py" --help
check "dist board still passes the page tests" node -e '
const fs=require("fs"),vm=require("vm");const p=fs.readFileSync(process.argv[1],"utf8");
new vm.Script(p.match(/<script>([\s\S]*?)<\/script>/)[1]);' "$TMP/dist/board.html"

echo "== white-label scrub"
mkdir -p "$TMP/dirty"
python3 - "$TMP/dirty/sample.md" <<'PY'
import codecs, sys
# planted hits, written ROT13 here so this script stays clean: a denylist term, an e-mail, a home folder, a key
lines = ["zrgva2 freire", "pbagnpg: wbr(NG)rknzcyr.pbz", "/Hfref/wbr/cebwrpg", "fx-nag-nov123qrs456tuv789"]
open(sys.argv[1], "w").write("\n".join(codecs.decode(l, "rot13").replace("(AT)", chr(64)) for l in lines) + "\n")
PY
expect "scrub_check finds planted hits" "scrub_check: 4 hits" python3 "$REPO/tools/scrub_check.py" "$TMP/dirty"
check "scrub_check: 0 hits" python3 "$REPO/tools/scrub_check.py" "$REPO"

echo
[ "$FAIL" = 0 ] && echo "ALL PASS" || echo "SOME CHECKS FAILED"
exit "$FAIL"
