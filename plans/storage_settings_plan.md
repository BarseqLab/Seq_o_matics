# Plan: lab-specific AWS and storage-server settings in storage.json, with connection tests

Branch `feature/configurable-aws-bucket` (worktree `.worktrees/configurable-aws-bucket`), based on main `9f8e7d2`.
Status: APPROVED v3 + both storage.json errors and connection failures BLOCK experiment creation (user decision). Implementing.

## Goal
Another lab with a different AWS bucket and a different storage server folder can run the package by editing
`code/config_file/storage.json` only. This lab's values are shipped in that file, so its behavior does not
change. An automatic connection test runs when an experiment is created.

## Decisions (from review)
- Flat keys, in a separate file `code/config_file/storage.json`. One file per install.
- **Missing `storage.json` is an error**, not a silent default. Likewise for missing or unknown keys.
- The server **user and host** stay in the GUI (they are switched between runs). `storage.json` holds their
  default values, which pre-fill the GUI fields. GUI edits apply to the session only.
- The server **folder**, the AWS bucket and the other AWS settings come from `storage.json` only. The GUI
  shows the bucket and folder **read-only**.
- The AWS account and password fields are unused: blank, grayed out, labeled `unused`, never enabled.
- Connection test: automatic, at experiment creation only (no buttons). It confirms access only (no writes).
- S3 prefix: optional, default empty.

## What is hardcoded today (verified on main)
| Value | Where | Used for |
|---|---|---|
| `bucket = "barseq-acquisition"` | `front_end/panels/status_panel.py` `upload_aws_handler` | S3 upload |
| `INTELLIGENT_TIERING`, `max_retries = 3` | same function | S3 upload |
| `'/mnt/imagestorage/'` | `status_panel.py` (note upload), `system/imaging/max_projection.py` (`transfer_protocol` ~l.350, `send_to_server` ~l.366) | remote folder |
| `"imagestorage"`, `"10.128.30.152"` | `front_end/Widgets.py` l.343-351, GUI field defaults | `user@host` |
| `"aixin.zhang@alleninstitute.org"` | `Widgets.py` l.358, AWS account field | cosmetic only; no code reads the AWS account or password fields |

## Design
1. `code/config_file/storage.json` (flat). Shipped values equal today's:
   ```
   {"aws_bucket": "barseq-acquisition",
    "aws_prefix": "",
    "aws_storage_class": "INTELLIGENT_TIERING",
    "aws_upload_retries": 3,
    "server_user": "imagestorage",
    "server_host": "10.128.30.152",
    "server_root": "/mnt/imagestorage/"}
   ```
2. `code/system/storage_settings.py`: frozen dataclass `StorageSettings` with `load(path)`. It raises
   `StorageSettingsError` (a clear message listing every problem) when: the file is missing or not valid
   JSON, a key is missing, a key is unknown (typo guard), or a value is invalid (empty string, retries < 1,
   `server_root` not ending in `/`, `aws_prefix` with a leading `/`). No built-in defaults for the lab values,
   so nothing can silently fall back to this lab's bucket.
3. Call sites read the settings:
   - `upload_aws_handler`: bucket, prefix, storage class, retries.
   - the three `/mnt/imagestorage/` sites: `server_root`, through one shared path helper.
   - GUI: server user/host pre-filled from the file; bucket and folder shown read-only.
4. Fixed in code: SHA256 checksum, zstd level 3.
5. No credentials in `storage.json`. The AWS CLI uses its own profile; ssh uses keys (no password prompt is
   possible in the unattended end-of-run upload).
6. GUI cleanup: AWS account and password fields are blank, grayed out, and show the text `unused`; the
   checkbox no longer enables them. The personal email default is removed.
7. README section "Setting up another lab".

## Experiment-creation flow (new)
At experiment creation (`create_exp_auto` / `create_exp_manual`, before the scope is built):
1. Load `storage.json`. On any `StorageSettingsError`, show an error dialog and the same text in the main log.
2. Run the connection tests (below). Results go to the main log.
Whether either step stops the experiment from being created is open (Q1).

## Connection test
Module `code/system/connection_check.py`, with no GUI code, unit-tested with a fake command runner. Each check
returns `(ok, short reason, stderr)`, never raises, and runs in a background thread with a timeout, so the GUI
stays responsive.
- **AWS** (only if "upload to AWS" is ticked): `aws --version`; `aws sts get-caller-identity`;
  `aws s3api head-bucket --bucket <bucket>`. Confirms the CLI, valid credentials and bucket visibility.
  It does not prove write permission.
- **Server** (only if the server option is used): `ssh -o BatchMode=yes -o ConnectTimeout=10 user@host
  "test -d <root> && test -w <root>"`. Reports: unreachable, key authentication failed, folder missing, folder
  not writable, or OK.

## Assumptions
- A1. The GUI can read `storage.json` from `config_file/` the same way `scope.json` is read. Not yet verified
  for GUI startup (the working directory at that point). To be checked first in implementation.
- A2. "Read-only" fields means disabled Entry widgets showing the value.
- A3. The pre-fill of user/host happens at GUI startup. If `storage.json` is bad at that point, the fields stay
  empty and the error appears at experiment creation (and at startup in the log).
- A4. `ssh` and `aws` are on PATH of the microscope PC (same as the existing upload).

## Open questions
- Q1. When settings loading fails, or a connection test fails, should experiment creation be **blocked**
  (no experiment until fixed) or only show an error and let you continue? My recommendation: block on a
  `storage.json` error (the upload would fail or go to the wrong place anyway); do not block on a failed
  connection test (imaging can run offline, and the end-of-run upload keeps the local data), but show it
  clearly. If you want both blocked, say so.
- Q2. Should an "AWS upload" failure of the test only matter when the AWS box is ticked? (planned: yes.)

## Implementation steps
1. `StorageSettings` + unit tests (valid, missing file, bad JSON, missing/unknown/invalid keys, all errors listed).
2. `connection_check` + unit tests (ok, timeout, CLI missing, no credentials, bucket missing, ssh refused,
   key auth failed, folder missing, folder not writable).
3. Add `storage.json` with the current values.
4. Switch `upload_aws_handler` and the three server-path sites.
5. GUI: pre-fill, read-only bucket/folder, `unused` AWS fields, experiment-creation load + test + messages.
6. README section.
7. Commit in small steps.

## Validation (design validation run, per project rules)
- Unit tests as above.
- Dry run with the existing `dryrun/` harness with the shipped `storage.json`: the `aws s3 cp`, `scp` and `ssh`
  commands are identical to main (record command traces on main and on the branch, then diff).
- Dry run with overridden values (fake bucket, prefix, host, user, folder): every command uses the new values;
  none contains `barseq-acquisition`, `10.128.30.152`, `imagestorage` or `/mnt/imagestorage/`.
- Dry run with `storage.json` removed, with a typo key, and with a missing key: the error appears at
  experiment creation and nothing is uploaded.
- Grep gate: no hardcoded occurrences remain outside `storage.json` (and the tests).
- GUI test with fake runners: test success, failure, and timeout; the GUI stays responsive.
- Not testable here: a real S3 upload, a real scp, and the connection tests against your real AWS account and
  server. You test those on the microscope PC.

## Risks
- Removing the built-in defaults means an existing install that updates the code without the new file gets an
  error at experiment creation. Intended (your decision); the README and the shipped file cover it.
- `feature/manual-aws-upload` also hardcodes the bucket in two places. It must adopt these settings when
  rebased onto main; not part of this branch.
- The tests touch the network; timeouts and the background thread keep the GUI responsive.
