#!/bin/bash
# setup.sh - prepare a kit home for Agent Brain Kit. Safe to run again: it never overwrites a file you changed.
#
#   ./setup.sh [--home DIR] [--dry-run]     create the folders, config, settings and team files
#   ./setup.sh --print-launchd              print a macOS LaunchAgent that runs brainwatch every 2 minutes
#   ./setup.sh --help
#
# It NEVER creates, reads or stores keys or passwords. Keys go in your OS keychain or in a file you create
# yourself under <home>/secrets (mode 600); the scripts only read them.
# bash 3.2 compatible (macOS /bin/bash) and Linux.
set -u

REPO="$(cd "$(dirname "$0")" && pwd -P)"
HOME_DIR="${AGENT_KIT_HOME:-$HOME/agent-brain-kit-home}"
DRY=0
MODE=setup

while [ $# -gt 0 ]; do
  case "$1" in
    --home) HOME_DIR="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --print-launchd) MODE=launchd; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "setup.sh: unknown option $1 (see --help)" >&2; exit 2 ;;
  esac
done

if [ "$MODE" = launchd ]; then
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>agent-brain-kit.brainwatch</string>
  <key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>$REPO/bin/brainwatch</string></array>
  <key>EnvironmentVariables</key><dict><key>AGENT_KIT_HOME</key><string>$HOME_DIR</string></dict>
  <key>StartInterval</key><integer>120</integer>
  <key>StandardOutPath</key><string>$HOME_DIR/logs/brainwatch.log</string>
  <key>StandardErrorPath</key><string>$HOME_DIR/logs/brainwatch.log</string>
</dict></plist>
EOF
  echo "<!-- save as ~/Library/LaunchAgents/agent-brain-kit.brainwatch.plist, then: launchctl load <that file> -->" >&2
  exit 0
fi

say() { echo "$@"; }
run() { if [ "$DRY" = 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }
command -v python3 >/dev/null 2>&1 || { echo "setup.sh: python3 is missing (install Python 3.9+)" >&2; exit 1; }

# 1. config: <home>/config/kit.json from the example, kit_home pointing at <home>
CONFIG="$HOME_DIR/config/kit.json"
run mkdir -p "$HOME_DIR/config"
if [ -f "$CONFIG" ]; then
  say "config kept: $CONFIG"
elif [ "$DRY" = 1 ]; then
  echo "[dry-run] write $CONFIG from config/kit.example.json"
else
  python3 - "$REPO/config/kit.example.json" "$CONFIG" "$HOME_DIR" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
cfg["kit_home"] = sys.argv[3]
cfg["_comment"] = "Edit accounts, caps, guard rules. No keys or passwords in this file."
with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY
  say "config written: $CONFIG (edit the accounts and caps)"
fi
export AGENT_KIT_HOME="$HOME_DIR"
[ -f "$CONFIG" ] && export AGENT_KIT_CONFIG="$CONFIG"

# 2. folders
ACCOUNTS="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import kitconfig as K; print(" ".join(K.account_names(K.load(), None)))' "$REPO/bin" 2>/dev/null)"
[ -n "$ACCOUNTS" ] || ACCOUNTS="main second shared api"
for d in team team/brain team/activity team/board/briefs team/jobs team/.claude ledger logs; do
  run mkdir -p "$HOME_DIR/$d"
done
run mkdir -p "$HOME_DIR/secrets" && run chmod 700 "$HOME_DIR/secrets"
for a in $ACCOUNTS; do run mkdir -p "$HOME_DIR/accounts/$a" && run chmod 700 "$HOME_DIR/accounts/$a"; done
say "folders ready in $HOME_DIR (accounts: $ACCOUNTS)"

# 3. settings: per account (status line + path guard) and the team folder (activity + brain hooks)
fill() {  # fill <template> <target>: replace placeholders; never overwrite a different existing file
  local src="$1" dst="$2" tmp
  tmp="$(mktemp)"
  python3 - "$src" "$tmp" "$REPO" "$HOME_DIR" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
home = sys.argv[4].rstrip("/")
text = text.replace("__KIT_REPO__", sys.argv[3]).replace("__KIT_HOME_NOSLASH__", home.lstrip("/")).replace("__KIT_HOME__", home)
open(sys.argv[2], "w", encoding="utf-8").write(text)
PY
  if [ ! -f "$dst" ]; then
    run cp "$tmp" "$dst" && say "installed $dst"
  elif cmp -s "$tmp" "$dst"; then
    :
  else
    run cp "$tmp" "$dst.kit" && say "kept your $dst; the kit version is $dst.kit (merge by hand)"
  fi
  rm -f "$tmp"
}
for a in $ACCOUNTS; do fill "$REPO/settings/account.settings.example.json" "$HOME_DIR/accounts/$a/settings.json"; done
fill "$REPO/settings/team.settings.example.json" "$HOME_DIR/team/.claude/settings.json"

# 4. team files from the templates (only when missing)
copy_new() { if [ ! -f "$2" ]; then run cp "$1" "$2" && say "installed $2"; fi; }
copy_new "$REPO/templates/CLAUDE.md.template" "$HOME_DIR/team/CLAUDE.md"
copy_new "$REPO/templates/brain_state.template.md" "$HOME_DIR/team/brain_state.md"
copy_new "$REPO/templates/TAKEOVER.template.md" "$HOME_DIR/team/brain/TAKEOVER.md"
copy_new "$REPO/templates/TREE_LOCK.template.md" "$HOME_DIR/team/TREE_LOCK.md"
copy_new "$REPO/templates/RULEBOOK.template.md" "$HOME_DIR/team/RULEBOOK.md"
copy_new "$REPO/board/example/board.config.json" "$HOME_DIR/team/board/board.config.json"
copy_new "$REPO/board/example/tasks.json" "$HOME_DIR/team/board/tasks.json"

cat <<EOF

Next steps
1. Put the tools on PATH (add to ~/.zshrc or ~/.bashrc):
     export AGENT_KIT_HOME="$HOME_DIR"
     export PATH="$REPO/bin:\$PATH"            # cca, brainlease, brainwatch, apijob
     export PATH="$REPO/optional/remote-runner:\$PATH"   # ws, only if you use the remote runner
2. Edit $CONFIG: accounts (names, caps, reset days), API budget, guard rules.
3. Fill the {{PLACEHOLDERS}} in $HOME_DIR/team/CLAUDE.md, TAKEOVER.md and brain_state.md.
4. Sign in each account once: cca <account>, then /login. (The API-key account: sign in with your
   key the way Claude Code documents it; never paste keys into files in this repo.)
5. Schedule brainwatch every 2 minutes: ./setup.sh --print-launchd (macOS) or a cron line (docs/ARCHITECTURE.md).
6. Build and publish the Task Board: board/PUBLISH.md.
7. Check everything offline: bash tools/selftest.sh
EOF
