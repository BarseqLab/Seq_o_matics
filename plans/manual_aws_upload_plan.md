# Plan: Manual "Upload to AWS" of a Previous Experiment

## Problem
When an experiment terminates mid-run and is restarted in a new folder, the
resumed run's AWS upload only covers the newly generated files. The preceding
folder is never uploaded. We need a manual way to point the GUI at a previous
experiment folder and upload it.

## Requirements (from request)
1. A **text input box** + a **button labeled "manual upload to AWS"** in the GUI.
2. User types the path of a previous experiment; pressing the button uploads it.
3. **Default root = the max-projection drive.** A bare folder name
   (`example_folder` or `"example_folder"`) should resolve against that drive.
4. A full path (`D:/example_folder`) should also work as-is.
5. Keep the overall architecture intact (reuse existing upload routine).

## Current architecture (verified)
- `Widgets.upload_aws_handler()` (code/front_end/Widgets.py:737) is the upload
  engine. It derives **everything** from two attributes:
  - `self.scope.maxprojection_drive`  (root drive, from scope config)
  - `self.pos_path`                    (acquisition/protocol folder)
- It computes `base_dir = os.path.join(maxprojection_drive, pos_path[3:] + "_maxprojection")`,
  then:
  1. For each per-cycle subfolder in `base_dir`: tar + zstd-compress, then
     `aws s3 cp <archive> s3://barseq-acquisition/<folder>/<name>.tar.zst`
     with retries; delete local archive on success.
  2. Builds `protocol.tar.zst` from json/txt/csv files in `self.pos_path` and
     uploads it.
- Called from `automation_controller.py:61` inside a worker thread (non-blocking).
- AWS GUI widgets are in `frame3` (auto) / `frame3_3` (manual), laid out in
  `mainwindow.py` (rows 72-82).

## NEW REQUIREMENT (2026-06-26): uploads must survive GUI exit
Any AWS upload (auto or manual) must **keep running even if the GUI is closed**,
and must remain **traceable**. A worker Thread inside the GUI process dies (or
blocks `quit`) when the GUI exits, so threading is insufficient. The upload must
run as a **detached OS process** that outlives the GUI, writing a persistent log
file the GUI (or the user) can inspect.

## Design (proposed) — detached worker process

### 1. Extract the upload engine into a standalone CLI worker
Move the tar+zstd+`aws s3 cp` logic out of `Widgets.upload_aws_handler` into a
new self-contained module **`code/aws_upload_worker.py`** with a `__main__`:

```
python aws_upload_worker.py \
    --base-dir   <*_maxprojection folder> \
    --folder     <S3 key prefix> \
    --protocol-src <folder for json/txt/csv | "" to skip> \
    --bucket     barseq-acquisition \
    --log-file   <path to this job's log>
```

The worker:
- imports nothing from Tk (no GUI deps) — only `os, tarfile, zstandard,
  subprocess, argparse, logging`.
- performs the exact same per-cycle tar+zstd compression, retried `aws s3 cp`,
  and protocol-bundle steps as the current handler.
- logs every step (start, each archive, each upload attempt, success/fail,
  finish) to `--log-file` **and** stdout, with timestamps. Writes a final
  `STATUS: SUCCESS|PARTIAL|FAILED` line.

This is a pure relocation of existing logic — **same behavior, same S3 naming**.

### 2. Launch it detached from the GUI
A helper in `Widgets.py` builds the arg list and launches the worker so it
**outlives the GUI**:

```python
subprocess.Popen(
    [sys.executable, worker_path, "--base-dir", ..., "--log-file", log_file],
    creationflags=subprocess.DETACHED_PROCESS
                  | subprocess.CREATE_NEW_PROCESS_GROUP,   # Windows
    close_fds=True,
    stdout=open(log_file, "a"), stderr=subprocess.STDOUT,
    cwd=<code dir>,
)
```

The GUI does **not** wait on the process; it returns immediately. Closing the
GUI no longer kills the upload.

### 3. Traceability
- **Per-job log file**: `<aws_jobs_dir>/aws_upload_<folder>_<timestamp>.log`.
  Default `aws_jobs_dir` = a `aws_upload_logs` folder on the maxprojection
  drive (visible to the operator, survives GUI restarts).
- **Job registry**: append one line per job to
  `<aws_jobs_dir>/aws_upload_jobs.tsv` (timestamp, folder, pid, log path).
  The GUI reads this to list past/ongoing jobs.
- **GUI status view (lightweight)**: the GUI logs "launched detached AWS upload
  job, see <log file>" to the existing log window so the operator knows where to
  look. (Optionally a small "view AWS jobs" button that tails the latest log —
  see Q6.)
- Since the worker process is independent, the GUI shows *that it was launched*,
  not live progress; progress lives in the log file (tailable any time, even
  after GUI restart).

### 4. Auto path uses the same detached worker
`upload_aws_handler()` (called from `automation_controller`) is rewritten to
build args (`base_dir`/`folder` as today, `protocol_src=self.pos_path`) and
launch the **same** detached worker, instead of doing the work inline.
Implication: the automation sequence no longer blocks on the AWS upload — it
fires-and-continues. See Q7.

### 2. Path-resolution logic for the manual input
Given the raw text `user_input`:
1. Strip surrounding quotes and whitespace.
2. Normalize separators.
3. If `os.path.isabs(user_input)` (e.g. `D:/example_folder`) -> use as the
   candidate folder directly.
4. Else (bare name) -> `os.path.join(maxprojection_drive, user_input)`.
5. Resolve which folder is the `*_maxprojection` base_dir (see Q2 below).
6. Validate the folder exists and contains at least one subdirectory; otherwise
   write an error to the GUI log and abort.

`folder` (the S3 key prefix) = `os.path.basename(base_dir.rstrip("/\\"))`,
preserving the existing convention that the S3 prefix is the maxprojection
folder name.

### 3. New GUI elements
- `self.manual_aws_path` = `StringVar()` ; `self.manual_aws_path_field` =
  `Entry(self.frame3_3, width=40, textvariable=self.manual_aws_path)`.
- `self.manual_aws_btn` = `Button(self.frame3_3, text="manual upload to AWS",
  command=self.manual_upload_to_aws)`.
- Grid them in `mainwindow.py` in the manual-tab AWS frame (new row, e.g. row 1
  of `frame3_3`) so the existing layout is untouched.
- (Open question Q4: auto tab too, or manual tab only?)

### 4. New handler `manual_upload_to_aws(tab)` in Widgets.py
- Read + resolve the path (section 2) from the auto or manual field.
- Validate folder exists and contains >=1 subdir; else log a GUI error, abort.
- `protocol_src = base_dir` (look inside the maxprojection folder for protocol
  files, per decision Q3).
- **Launch the detached worker** (section 2), not a Thread.
- Log to the GUI: "launched detached AWS upload of <folder>, log: <path>".

## Sanity checks / risks
- **AWS CLI dependency**: same `aws s3 cp` path as existing code -> no new deps.
- **Disk space**: archives are written into `base_dir` then deleted on success,
  same as today.
- **Idempotency**: re-uploading overwrites the same S3 keys (acceptable; same as
  current behavior on re-run).
- **Threading**: must not block Tk mainloop -> use a Thread, do not call
  directly in the button callback.
- **No protocol files**: helper already handles "no protocol files" gracefully.

## DECISIONS (confirmed by user 2026-06-26)
- **Q1 Target folder**: User points **directly at the `*_maxprojection` folder**.
  No suffix auto-append needed (Q2 moot).
- **Q3 Protocol bundle**: **Look inside the maxprojection folder** for
  json/txt/csv; if present, bundle and upload them; otherwise skip with a log
  note. (`protocol_src = base_dir` for manual uploads.)
- **Q4 Placement**: **Both auto and manual tabs** get the Entry + button.
- **Q5 Credentials**: reuse machine-configured AWS CLI credentials (same as
  existing handler; no key passing).

### Implications
- Path resolution simplifies: `base_dir` = the resolved input path itself
  (absolute -> as-is; bare name -> joined with `maxprojection_drive`).
  `folder` (S3 prefix) = `os.path.basename(base_dir)`.
- `_do_aws_upload(base_dir, folder, protocol_src=base_dir)` for manual; existing
  wrapper still passes `protocol_src=self.pos_path` for auto (unchanged).
- Two new widget sets: `frame3` (auto) and `frame3_3` (manual); two grid blocks
  in `mainwindow.py`. Handler `manual_upload_to_aws(tab)` reads the right field.

## Original open design questions (now resolved above)

**Q1 — What does the user point at?**
Do they enter the path to the `*_maxprojection` folder itself (the one with
per-cycle subfolders), or the raw acquisition/protocol folder (and we append
`_maxprojection`)? The current convention stores maxprojections under
`<name>_maxprojection`. I lean toward: **user points directly at the
`*_maxprojection` folder** (matches "upload from the max projection drive").
Please confirm.

**Q2 — Suffix handling.**
If the user types a name *without* `_maxprojection`, should we (a) auto-append
`_maxprojection`, (b) use exactly what they typed, or (c) try exact first then
fall back to `+_maxprojection`? (c) is most forgiving.

**Q3 — Protocol bundle for old runs.**
For a previous run, the json/txt/csv protocol files may live in the original
acquisition folder, which may no longer be on disk. Options:
  (a) Skip the protocol bundle for manual uploads (upload maxprojections only).
  (b) Add a second optional text box for the protocol-source folder.
  (c) Look for protocol files inside the maxprojection folder itself if present.
I lean toward (a) for simplicity, with a log note. Please confirm.

**Q4 — Placement.**
Manual tab only, or both auto and manual tabs? (Request implies one box; I
suggest manual tab only.)

**Q5 — Credentials.**
Manual upload reuses whatever AWS CLI credentials are already configured on the
machine (same as the existing handler, which does not pass keys to
`aws s3 cp`). Confirm no separate credential handling is needed.

## DECISIONS — detached-process change (confirmed 2026-06-26)
- **Q7 Auto sequencing**: **Detach auto too** — automation fires the upload and
  continues immediately; upload survives GUI exit. Single code path for both
  auto and manual. (Caveat noted below.)
- **Q6 Monitoring**: **Minimum** — GUI logs the job's log-file path on launch;
  no in-GUI jobs viewer for now.
- **Q8 Log location**: **`aws_upload_logs/` on the maxprojection drive** for both
  per-job logs and the job registry TSV.

### Caveat from detaching the auto path
The automation sequence will no longer wait for the AWS upload to finish before
its next steps (e.g. server upload, disk-space checks). These operate on
different folders, so functionally independent, but multiple uploads may now run
concurrently and share disk/network bandwidth. Acceptable per decision; will
verify in validation step 6.

## Additional open questions (detached-process change)

**Q6 — GUI job-monitoring depth.**
Minimum: GUI just logs the job's log-file path on launch (operator opens the
file). Optional extra: a "view AWS jobs" button that lists jobs from the
registry and tails the latest log. Which do you want? (I lean minimum first.)

**Q7 — Auto upload sequencing.**
Today the automation sequence runs the AWS upload inline (blocking) before the
next step (server upload, disk checks). Detaching it makes the upload
fire-and-continue. Is that acceptable, or must the automation flow still **wait**
for the AWS upload to finish before continuing? (If it must wait, the auto path
keeps a blocking variant while only the *manual* path is detached — please
confirm which.)

**Q8 — Log location.**
OK to put job logs + registry in `aws_upload_logs/` on the maxprojection drive?
Or a different folder (e.g. under the repo, or the experiment folder)?

## Files to change
- `code/aws_upload_worker.py` — **new** standalone detached worker (engine).
- `code/front_end/Widgets.py` — remove inline engine; add detached-launch
  helper, path resolution, `manual_upload_to_aws`, new widgets; rewrite
  `upload_aws_handler` to launch the worker.
- `code/mainwindow.py` — grid the new Entry + Button (both tabs).
- `code/front_end/automation_controller.py` — unchanged call site, but behavior
  now non-blocking (pending Q7).

## Validation plan (after implementation)
1. Dry sanity: resolve-path checks for the 3 input forms
   (`example_folder`, `"example_folder"`, `D:/example_folder`).
2. Worker standalone: run `aws_upload_worker.py` directly on a small test
   `*_maxprojection` folder; confirm tar/zst archives created, uploaded,
   deleted; confirm S3 keys match the auto path's naming; confirm log file +
   final STATUS line.
3. **Survives GUI exit**: launch a manual upload, then close the GUI; confirm
   the worker process keeps running and the log keeps updating to completion.
4. Traceability: confirm job registry line + log file appear and are readable
   after GUI restart.
5. Error cases: nonexistent/empty folder -> clean GUI error, no crash, no
   orphaned process.
6. Regression: auto upload still produces identical S3 output (pending Q7
   decision on blocking vs non-blocking).
