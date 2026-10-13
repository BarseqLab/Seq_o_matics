"""Connection checks for the AWS bucket and the storage server, run when an experiment is created.

Access only: nothing is written to the bucket or the server. Each check returns a CheckResult and never raises.
"""

import subprocess
from dataclasses import dataclass

TIMEOUT_S = 20


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str

    def __str__(self):
        return f"{self.name}: {'OK' if self.ok else 'FAILED'} - {self.message}"


def run_command(args, timeout=TIMEOUT_S):
    """Run ``args`` and return (returncode, stdout, stderr); the fake runners in the tests have this signature."""
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def _tail(text):
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return lines[-1] if lines else "no error text"


def _run(args, runner, timeout=TIMEOUT_S):
    """Returns (result, None) or (None, failure message)."""
    try:
        return runner(args, timeout), None
    except FileNotFoundError:
        return None, f"'{args[0]}' not found on PATH"
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout} s"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def check_aws(settings, runner=None):
    """AWS CLI present, credentials valid, bucket visible to them. Does not prove write permission."""
    runner = runner or run_command
    name = f"AWS bucket {settings.aws_bucket}"
    steps = (
        (["aws", "--version"], "AWS CLI not usable"),
        (["aws", "sts", "get-caller-identity"], "AWS credentials not configured or invalid"),
        (["aws", "s3api", "head-bucket", "--bucket", settings.aws_bucket], "bucket not accessible"),
    )
    for args, what in steps:
        res, err = _run(args, runner)
        if err:
            return CheckResult(name, False, f"{what}: {err}")
        rc, _out, stderr = res
        if rc != 0:
            return CheckResult(name, False, f"{what}: {_tail(stderr)}")
    return CheckResult(name, True, "CLI, credentials and bucket access confirmed (write access not tested)")


def check_server(settings, server=None, runner=None):
    """Key-based ssh login works and server_root exists and is writable. ``server`` overrides user@host (GUI edits)."""
    runner = runner or run_command
    server = server or settings.server
    name = f"server {server}"
    root = settings.server_root
    probe = (f"test -d '{root}' || {{ echo MISSING; exit 3; }}; "
             f"test -w '{root}' || {{ echo NOTWRITABLE; exit 4; }}")
    args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", server, probe]
    res, err = _run(args, runner)
    if err:
        return CheckResult(name, False, err)
    rc, _out, stderr = res
    if rc == 0:
        return CheckResult(name, True, f"login OK, {root} exists and is writable")
    if rc == 3:
        return CheckResult(name, False, f"folder {root} does not exist on the server")
    if rc == 4:
        return CheckResult(name, False, f"folder {root} is not writable by this user")
    if rc == 255:
        return CheckResult(name, False, f"cannot connect or key login failed: {_tail(stderr)}")
    return CheckResult(name, False, f"ssh exited with {rc}: {_tail(stderr)}")


def check_all(settings, server, check_aws_too, check_server_too, runner=None):
    """Run the requested checks and return a list of CheckResult."""
    results = []
    runner = runner or run_command
    if check_aws_too:
        results.append(check_aws(settings, runner))
    if check_server_too:
        results.append(check_server(settings, server, runner))
    return results
