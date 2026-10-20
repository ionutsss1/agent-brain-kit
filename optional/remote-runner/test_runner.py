#!/usr/bin/env python3
"""End-to-end test of the remote runner on one machine: a temp spool, a temp key, the real daemon and client.
  python3 optional/remote-runner/test_runner.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import ws_proto as P  # noqa: E402


def main():
    tmp = tempfile.mkdtemp(prefix="ws-test-")
    spool, key = os.path.join(tmp, "spool"), os.path.join(tmp, "ws.key")
    for sub in ("inbox", "jobs", "rejected", "state"):
        os.makedirs(os.path.join(spool, sub))
    P.write_new_key(key)
    assert oct(os.stat(key).st_mode & 0o777) == "0o600", "key file must be private"
    cfg = os.path.join(tmp, "daemon.json")
    with open(cfg, "w") as f:
        json.dump({"classes": {"light": {"slots": 2, "pausable": False, "killable": True},
                               "heavy": {"slots": 1, "pausable": True, "killable": True},
                               "build": {"slots": 1, "pausable": True, "killable": False}}}, f)
    daemon = subprocess.Popen([sys.executable, os.path.join(HERE, "ws_daemon.py"), "--spool", spool, "--key", key,
                               "--config", cfg, "--exit-after", "60"], stdout=subprocess.DEVNULL)
    env = dict(os.environ, KIT_WS_SPOOL=spool, KIT_WS_KEY=key)

    def ws(*args, timeout=30):
        r = subprocess.run([sys.executable, os.path.join(HERE, "ws")] + list(args), capture_output=True, text=True,
                           env=env, timeout=timeout)
        return r.returncode, r.stdout, r.stderr

    try:
        time.sleep(0.8)
        rc, out, err = ws("ping")
        assert rc == 0 and "pong" in out, (rc, out, err)
        rc, out, err = ws("run", "--", "echo hello; echo $KIT_GREETING", "--env", "KIT_GREETING=hi")
        assert rc == 0 and "hello" in out, (rc, out, err)
        rc, out, err = ws("run", "--env", "KIT_GREETING=hi", "--", "echo $KIT_GREETING")
        assert rc == 0 and "hi" in out, (rc, out, err)
        rc, out, err = ws("run", "--", "exit 3")
        assert rc == 3, (rc, out, err)
        rc, out, err = ws("run", "--env", "PATH=/evil", "--", "true")
        assert rc == 126 and "env key not allowed" in err, (rc, out, err)
        rc, out, err = ws("run", "--class", "nope", "--", "true")
        assert rc == 126 and "unknown class" in err, (rc, out, err)
        # a request signed with the wrong key is refused
        bad = P.make_request(bytes(32), "run", cmd="true")
        P.write_atomic(os.path.join(spool, "inbox", bad["id"] + ".json"), json.dumps(bad))
        time.sleep(1)
        assert "bad signature" in (P.read_json(os.path.join(spool, "rejected", bad["id"] + ".json")) or {}).get("reason", "")
        # a replayed request (same nonce) is refused
        good = P.make_request(P.load_key(key), "ping")
        P.write_atomic(os.path.join(spool, "inbox", good["id"] + ".json"), json.dumps(good))
        time.sleep(0.8)
        P.write_atomic(os.path.join(spool, "inbox", good["id"] + "-again.json"), json.dumps(good))
        time.sleep(0.8)
        assert (P.read_json(os.path.join(spool, "rejected", good["id"] + "-again.json")) or {}).get("reason") == \
            "nonce reused", "a replayed request must be refused"
        # pause holds heavy jobs, light still runs; resume releases them
        assert ws("pause")[0] == 0
        rc, heavy, _ = ws("run", "--detach", "--class", "heavy", "--", "echo heavy-done")
        heavy = heavy.strip()
        assert ws("run", "--", "echo light-ok")[1].strip().endswith("light-ok")
        time.sleep(0.8)
        assert (P.read_json(os.path.join(spool, "jobs", heavy, "status.json")) or {}).get("state") == "held"
        assert ws("resume")[0] == 0
        rc, out, err = ws("wait", heavy, "--timeout", "10")
        assert rc == 0 and "heavy-done" in out, (rc, out, err)
        # the owner's PAUSE switch is never cleared by the client
        open(os.path.join(spool, "state", "PAUSE"), "w").close()
        ws("resume")
        assert os.path.exists(os.path.join(spool, "state", "PAUSE"))
        os.remove(os.path.join(spool, "state", "PAUSE"))
        # kill a running job; a build job cannot be killed
        rc, sleeper, _ = ws("run", "--detach", "--", "sleep 30")
        sleeper = sleeper.strip()
        time.sleep(1)
        assert ws("kill", sleeper)[0] == 0
        rc, out, err = ws("wait", sleeper, "--timeout", "10")
        assert rc == 137, (rc, out, err)
        rc, build, _ = ws("run", "--detach", "--class", "build", "--", "sleep 2; echo built")
        build = build.strip()
        time.sleep(0.8)
        assert ws("kill", build)[0] == 1
        rc, out, err = ws("wait", build, "--timeout", "10")
        assert rc == 0 and "built" in out, (rc, out, err)
        # a short wait on a long job returns 124 with the id
        rc, out, err = ws("run", "--timeout", "1", "--", "sleep 3")
        assert rc == 124 and "ws wait" in err, (rc, out, err)
        rc, out, err = ws("status")
        assert rc == 0 and "alive" in out, (rc, out, err)
        assert ws("keygen", key)[0] == 2, "keygen never overwrites"
        print("PASS: ping, run + output + exit codes, KIT_ env only, unknown class, bad signature, nonce replay, "
              "pause/resume (owner switch untouched), kill (build not killable), 124 timeout, status, keygen.")
        return 0
    finally:
        daemon.terminate()
        try:
            daemon.wait(timeout=10)
        except subprocess.TimeoutExpired:
            daemon.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
