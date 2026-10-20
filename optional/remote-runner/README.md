# Remote runner (optional)

Use it when some work must run on another machine (a build box, a GPU box, a machine with a test setup),
while the agents run on the planning machine. The two machines share one folder (a network share). The
client `ws` writes signed requests into it; `ws_daemon.py` on the remote machine runs them and writes back
the status and output.

```
planning machine                       shared folder (spool)                remote machine
ws run -- 'make test'  --signed-->     inbox/<id>.json          <--poll--   ws_daemon.py
ws wait <id>           <--read--       jobs/<id>/status.json    <--write--  runs it, logs out.log
                                       state/heartbeat.json, PAUSE (owner), PAUSE_HQ (brain)
```

## Safety
- Every request is HMAC-signed with a shared key, time-stamped (5 min skew) and has a one-time nonce.
- Requests may only set environment variables named `KIT_*`.
- Classes cap how many jobs run at once (`build` 1, `heavy` 1, `film` 2, `light` 4 by default).
- Two pause switches: `PAUSE` is the owner's, `PAUSE_HQ` the brain's (`ws pause` / `ws resume`). The client
  never touches the owner's switch. Paused classes wait; running jobs finish.
- `build` jobs cannot be killed by default (a killed compiler can corrupt a tree).
- The key is never printed. `ws keygen <path>` writes a new key with mode 600 and refuses to overwrite.
  Copy it to the remote machine yourself, and keep it out of the shared folder.

## Set up
1. On the remote machine: Python 3.9+, and `bash` (on Windows use Git Bash, or set `"shell": ["cmd", "/c"]`
   in `daemon.json`). Copy `ws_daemon.py`, `ws_proto.py` and `daemon.example.json` (as `daemon.json`).
2. Create the key once: `ws keygen ~/.config/agent-kit/ws.key`, then copy the file to the remote machine
   over a channel you trust. Both sides use the same file.
3. Start the daemon (keep it running with launchd, systemd or a Windows scheduled task):
   `python3 ws_daemon.py --spool <share>/ws/spool --key <key file> --config daemon.json`
4. On the planning machine, add to `config/kit.json`:
   ```json
   "remote": {"key_file": "{kit_home}/secrets/ws.key", "default_target": "box",
              "targets": {"box": {"spool": "/mnt/share/ws/spool"}}, "wait_seconds": 540}
   ```
   and to `brain.pause_command`: `["<kit>/optional/remote-runner/ws", "pause"]` so `brainwatch` pauses the
   remote jobs when every account is at its cap.
5. `ws ping` must answer `pong`. Then `ws run -- 'echo ok'`.

## Use
```
ws run -- 'rg -n TODO src | head -40'          # light job, output streamed, exit code passed through
ws run --class build --detach -- './build.sh'  # prints the id at once
ws wait <id>                                   # last 40 lines when it ends; 124 if still running
ws status                                      # daemon heartbeat, running, queued/held, pause switches
ws --target other status                       # another machine's spool
```
A tool call ends at 10 minutes: `ws run` returns 124 after `wait_seconds` (default 9 min) with the id;
continue with `ws wait <id>`.

## Test
`python3 optional/remote-runner/test_runner.py` runs the real daemon and client on one machine with a
temporary spool and key.
