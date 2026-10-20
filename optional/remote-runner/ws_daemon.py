#!/usr/bin/env python3
"""ws_daemon - runs signed jobs from a shared spool folder on the remote machine (the "workshop").

  python3 ws_daemon.py --spool <spool folder> --key <key file> [--config daemon.json] [--exit-after S]

The client (ws) on the planning machine writes signed requests into <spool>/inbox; this daemon checks each
one (signature, timestamp, nonce, kind, class, env names), then runs it with the configured shell and
writes <spool>/jobs/<id>/status.json and out.log. It keeps <spool>/state/heartbeat.json fresh (every 5 s).

Classes (daemon.json "classes"): how many jobs of each class run at once ("slots"), whether the pause
switches hold it ("pausable") and whether `ws kill` may stop it ("killable"). Default:
  light 4 slots, never paused; heavy 1, build 1 (not killable), film 2: paused.
Pause switches: <spool>/state/PAUSE is the owner's, PAUSE_HQ is the brain's (ws pause / ws resume). While
either exists, new jobs of pausable classes wait (state "held"); running jobs continue.
Old job folders are removed after "keep_days" (default 7). Standard library only, Python 3.9+.
"""
import argparse
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import ws_proto as P  # noqa: E402

DEFAULTS = {
    "shell": ["bash", "-lc"],
    "default_cwd": None,
    "keep_days": 7,
    "classes": {
        "light": {"slots": 4, "pausable": False, "killable": True},
        "heavy": {"slots": 1, "pausable": True, "killable": True},
        "build": {"slots": 1, "pausable": True, "killable": False},
        "film": {"slots": 2, "pausable": True, "killable": True},
    },
}


class Daemon(object):
    def __init__(self, spool, key, cfg):
        self.spool, self.key, self.cfg = spool, key, cfg
        self.classes = cfg["classes"]
        for sub in ("inbox", "jobs", "rejected", "state"):
            os.makedirs(os.path.join(spool, sub), exist_ok=True)
        self.queue = []      # requests waiting to start, oldest first
        self.running = {}    # id -> (Popen, class, log file)
        self.nonces = {}     # nonce -> time seen
        self.held = set()    # queued ids already marked "held"
        self.last_beat = 0.0
        self.last_clean = 0.0

    # ------------------------------------------------------------ files
    def job_dir(self, job_id):
        return os.path.join(self.spool, "jobs", job_id)

    def set_status(self, job_id, **fields):
        os.makedirs(self.job_dir(job_id), exist_ok=True)
        path = os.path.join(self.job_dir(job_id), "status.json")
        st = P.read_json(path) or {"id": job_id}
        st.update(fields)
        st["updated"] = time.time()
        P.write_atomic(path, json.dumps(st, indent=1, sort_keys=True) + "\n")

    def reject(self, name, reason):
        job_id = name[:-5] if name.endswith(".json") else name
        P.write_atomic(os.path.join(self.spool, "rejected", job_id + ".json"),
                       json.dumps({"id": job_id, "reason": reason, "t": time.time()}) + "\n")

    def paused(self):
        st = os.path.join(self.spool, "state")
        return {"owner": os.path.exists(os.path.join(st, "PAUSE")), "hq": os.path.exists(os.path.join(st, "PAUSE_HQ"))}

    def heartbeat(self, force=False):
        now = time.time()
        if not force and now - self.last_beat < 5:
            return
        self.last_beat = now
        P.write_atomic(os.path.join(self.spool, "state", "heartbeat.json"), json.dumps({
            "t": now, "pid": os.getpid(), "host": socket.gethostname(), "key": P.key_fingerprint(self.key),
            "running": sorted(self.running), "queued": [r["id"] for r in self.queue], "pause": self.paused(),
            "classes": self.classes}, indent=1, sort_keys=True) + "\n")

    # ------------------------------------------------------------ requests
    def take_inbox(self):
        inbox = os.path.join(self.spool, "inbox")
        now = time.time()
        self.nonces = {n: t for n, t in self.nonces.items() if now - t < P.NONCE_TTL_S}
        for name in sorted(os.listdir(inbox)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(inbox, name)
            req = P.read_json(path)
            try:
                os.remove(path)
            except OSError:
                continue
            reason = P.check_request(req, self.key, classes=tuple(self.classes))
            if not reason and req["nonce"] in self.nonces:
                reason = "nonce reused"
            if not reason and os.path.exists(self.job_dir(req["id"])):
                reason = "id already used"
            if reason:
                self.reject(name, reason)
                continue
            self.nonces[req["nonce"]] = now
            os.makedirs(self.job_dir(req["id"]), exist_ok=True)
            P.write_atomic(os.path.join(self.job_dir(req["id"]), "request.json"), json.dumps(req, indent=1) + "\n")
            if req["kind"] == "ping":
                self.set_status(req["id"], state="done", code=0, note="pong", started=now, ended=now)
            elif req["kind"] == "kill":
                self.kill(req)
            else:
                self.queue.append(req)
                self.set_status(req["id"], state="queued", cls=req["class"], queued=now)

    def kill(self, req):
        target = req["target"]
        now = time.time()
        if target in self.running:
            proc, cls, _ = self.running[target]
            if not self.classes.get(cls, {}).get("killable", True):
                self.set_status(req["id"], state="done", code=1, note="class %s cannot be killed" % cls,
                                started=now, ended=now)
                return
            self.stop_tree(proc)
            self.set_status(target, state="killed", killed_by=req["id"])
            self.set_status(req["id"], state="done", code=0, note="killed %s" % target, started=now, ended=now)
            return
        for r in list(self.queue):
            if r["id"] == target:
                self.queue.remove(r)
                self.set_status(target, state="killed", code=137, killed_by=req["id"], ended=now)
                self.set_status(req["id"], state="done", code=0, note="removed %s from the queue" % target,
                                started=now, ended=now)
                return
        self.set_status(req["id"], state="done", code=1, note="no such running or queued job", started=now, ended=now)

    @staticmethod
    def stop_tree(proc):
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30)
            else:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            pass

    # ------------------------------------------------------------ running
    def schedule(self):
        pause = self.paused()
        held = pause["owner"] or pause["hq"]
        for req in list(self.queue):
            cls = req["class"]
            spec = self.classes.get(cls, {})
            if held and spec.get("pausable", True):
                if req["id"] not in self.held:
                    self.held.add(req["id"])
                    self.set_status(req["id"], state="held",
                                    note="paused (%s)" % ", ".join(k for k, v in pause.items() if v))
                continue
            busy = sum(1 for _, c, _ in self.running.values() if c == cls)
            if busy >= int(spec.get("slots", 1)):
                continue
            self.queue.remove(req)
            self.held.discard(req["id"])
            self.start(req)

    def start(self, req):
        job_id = req["id"]
        log = open(os.path.join(self.job_dir(job_id), "out.log"), "wb")
        env = dict(os.environ)
        env.update(req.get("env") or {})
        env["KIT_JOB_ID"] = job_id
        cwd = req.get("cwd") or self.cfg.get("default_cwd") or None
        kw = {}
        if platform.system() != "Windows":
            kw["start_new_session"] = True
        else:
            kw["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            proc = subprocess.Popen(list(self.cfg["shell"]) + [req["cmd"]], stdout=log, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, cwd=cwd, env=env, **kw)
        except OSError as e:
            log.write(("ws_daemon: could not start: %s\n" % e).encode())
            log.close()
            self.set_status(job_id, state="failed", code=127, note=str(e), ended=time.time())
            return
        self.running[job_id] = (proc, req["class"], log)
        self.set_status(job_id, state="running", pid=proc.pid, started=time.time())

    def reap(self):
        for job_id, (proc, cls, log) in list(self.running.items()):
            code = proc.poll()
            if code is None:
                continue
            log.close()
            del self.running[job_id]
            st = P.read_json(os.path.join(self.job_dir(job_id), "status.json")) or {}
            if st.get("state") == "killed":
                self.set_status(job_id, code=137, ended=time.time())
            else:
                self.set_status(job_id, state="done" if code == 0 else "failed", code=code, ended=time.time())

    def clean(self):
        now = time.time()
        if now - self.last_clean < 3600:
            return
        self.last_clean = now
        keep = float(self.cfg.get("keep_days", 7)) * 86400
        for sub in ("jobs", "rejected"):
            root = os.path.join(self.spool, sub)
            for name in os.listdir(root):
                path = os.path.join(root, name)
                if name in self.running:
                    continue
                try:
                    if now - os.path.getmtime(path) > keep:
                        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
                except OSError:
                    pass

    def loop(self, exit_after=None):
        t0 = time.time()
        self.heartbeat(force=True)
        while exit_after is None or time.time() - t0 < exit_after:
            self.take_inbox()
            self.schedule()
            self.reap()
            self.heartbeat()
            self.clean()
            time.sleep(0.3)
        for proc, _, _ in self.running.values():
            self.stop_tree(proc)
        self.reap()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spool", required=True)
    ap.add_argument("--key", required=True, help="hex key file (the same key the client reads)")
    ap.add_argument("--config", help="daemon.json (classes, shell, default_cwd, keep_days)")
    ap.add_argument("--exit-after", type=float, default=None, help="stop after this many seconds (tests)")
    a = ap.parse_args()
    cfg = json.loads(json.dumps(DEFAULTS))
    if a.config:
        with open(a.config, encoding="utf-8") as f:
            user = json.load(f)
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
    key = P.load_key(a.key)
    print("ws_daemon: spool %s, key %s, classes %s" % (a.spool, P.key_fingerprint(key), ", ".join(cfg["classes"])),
          flush=True)
    Daemon(a.spool, key, cfg).loop(a.exit_after)
    return 0


if __name__ == "__main__":
    sys.exit(main())
