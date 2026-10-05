"""Record (never run) external commands: ssh/scp to the storage server, aws s3 cp."""

import os
import subprocess

from dryrun import trace

_REAL_RUN = subprocess.run
_REAL_POPEN = subprocess.Popen
_REAL_SYSTEM = os.system


def _system(cmd):
    trace.record("command", via="os.system", cmd=str(cmd))
    return 0


def _run(args, *a, **kw):
    cmd = args if isinstance(args, str) else " ".join(map(str, args))
    trace.record("command", via="subprocess.run", cmd=cmd)
    stdout = b"" if not kw.get("text") else ""
    return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=stdout)


class _Popen:
    def __init__(self, args, *a, **kw):
        cmd = args if isinstance(args, str) else " ".join(map(str, args))
        trace.record("command", via="subprocess.Popen", cmd=cmd)
        self.args = args
        self.pid = 0
        self.returncode = 0

    def wait(self, timeout=None):
        return 0

    def communicate(self, *a, **kw):
        return b"", b""

    def poll(self):
        return 0


def install():
    os.system = _system
    subprocess.run = _run
    subprocess.Popen = _Popen
