# storage.json work: record and Elm test checklist

**Last updated:** 2026-10-16
**Branch:** `feature/configurable-aws-bucket` (from main `9f8e7d2`, the fork's `main` brought into this repo). Plan: `plans/storage_settings_plan.md`.
**State:** implemented, reviewed four times, unit-tested and dry-run on the dev PC. **Not yet run on Elm.**

## Update 2026-10-15/16: reviews, fixes, dry run
- **Fixes after code review:** see `plans/storage_settings_review_fixes_plan.md` (decisions D1/D2, items 1-8,
  R1-R8, B1-B6, with reasons). In short:
  - A failed connection check still blocks Create (D1). The dialog now says which box to untick.
  - Manual Create runs no connection checks (D2); a bad storage.json still blocks.
  - While the check runs, a modal "Please wait" window shows "Checking connections...", then "Creating
    experiment..." until Create finishes. Create on both tabs, the upload boxes and the server user/host fields
    are grayed out meanwhile, so the values used are the values checked and Create cannot run twice.
  - A crashed or incomplete check blocks. `storage.json` is read as UTF-8 (BOM allowed). Validation is stricter
    (storage-class allowlist, no leading `-`, no spaces/quotes in `server_root`, retries 1-10).
  - User/host fields refresh from the file when empty or still showing the last-loaded value; typed values kept.
    A failed check no longer changes the settings an earlier experiment uploads with.
  - Connection-check commands get no console input and their output is decoded leniently.
- **Tests:** 51 storage tests (was 25). In the new env, all 80 tests in `dryrun/tests` pass.
- **AWS check on the dev PC:** passes with IAM user `data_upload` (1.5 s). Elm's credentials still to confirm.
- **Python env for tests and the dry run:** `c:\barseq_envs\seqomatic-dryrun`, made with the existing Anaconda
  (`C:\Users\xiaoyin.chen\AppData\Local\anaconda3\Scripts\conda.exe env create -f environment.yml -n seqomatic-dryrun`):
  Python 3.10.13, numpy 1.26.0, pandas 1.5.3, matplotlib 3.5.3, scikit-image 0.20.0, zstandard 0.25. Note:
  `opencv>=4.5` resolved to OpenCV 5.0.0 (Elm probably 4.x).
- **Full-GUI dry run (2026-10-16), branch vs origin/main** (plan and method: `plans/dryrun_env_plan.md`; in the
  reports `ref` = origin/main 9f8e7d2, not the Elm reference). Reports in `figs/dryrun_report_*.md`, traces in
  `figs/dryrun_traces/` (scratch, 50 GB, deleted). All 15 runs completed (rc 0): imaging_uploads (x2),
  imaging_only, prime_wash, cancel_restart, auto_full (x2), and imaging_thick_46/100 (branch only, all checks PASS).
  - **External commands:** with uploads ticked, main's commands are unchanged; the branch adds exactly the four
    connection-check commands at Create. With uploads off, no new commands. The connection check passes (fake rc 0)
    and the run goes on.
  - **All device channels identical to main** (pumps, dispenses, selectors, serial ports, DAQ, acquisitions,
    files, messageboxes, exceptions) in every scenario.
  - **Differences, all explained:** GUI text has the new "Testing connections...", the two OK lines and the
    "AWS upload to s3://..." line. Other text and Z-drive differences come from timing (temperatures sampled,
    durations, free disk space) and from the harness seeding image noise with the run folder.
  - **Focus check FAILs on both main and branch** (a plane 3 um off at 1-5 positions per run, varying between
    repeats). Same on main, so not this branch; probably the harness's per-folder noise seed, maybe OpenCV 5.
    Worth a separate look at the harness.
  - **Leftover `plot_live_view_thread` at the end of `auto_full`** appeared once on branch (r2) and once on main
    (r3): a race with the 5 s live-view poll, present on main. `cancel_restart` leaves the same two threads on both.

## Context of this session (2026-10-11 to 2026-10-13)
1. Kept the old main for reverting: branch `legacy/main-pre-fork-merge` and tag `v-pre-fork-merge`, both at `11c4505`, pushed to `origin`.
   Note: `origin/main` had one more README-only commit, `5e5adf0`, at the time of the merge. It is contained in the fork, so nothing was lost, but `11c4505` is main from just before it.
2. Main was fast-forwarded to the fork's `main` (`9f8e7d2`, 110 files changed). The fork's two tags were not pushed. `feature/manual-aws-upload` was left on the old main (it needs a rebase later).
3. This branch makes the lab-specific AWS and storage-server settings configurable (below).

## What changed
| Area | Change |
|---|---|
| `code/config_file/storage.json` (new) | Flat keys `aws_bucket`, `aws_prefix`, `aws_storage_class`, `aws_upload_retries`, `server_user`, `server_host`, `server_root`. Shipped values equal the old hardcoded ones (`barseq-acquisition`, `""`, `INTELLIGENT_TIERING`, 3, `imagestorage`, `10.128.30.152`, `/mnt/imagestorage/`). |
| `code/system/storage_settings.py` (new) | Loader and validation. **No defaults**: missing file, bad JSON, missing key, unknown key (typo) or invalid value raises `StorageSettingsError` listing every problem. Helpers for the remote path and the S3 URI. |
| `code/system/connection_check.py` (new) | AWS: `aws --version`, `aws sts get-caller-identity`, `aws s3api head-bucket`. Server: `ssh -o BatchMode=yes -o ConnectTimeout=10 user@host` testing that `server_root` exists and is writable. Access only, nothing is written. Never raises. |
| `front_end/panels/workspace_panel.py` | `_storage_ok()` runs in `create_exp_auto` and `create_exp_manual`: load `storage.json`, then run the checks for the boxes that are ticked (AWS box, "Send to storage server" box), using the user@host from the GUI fields. **Any error or failed check shows a dialog, writes to the warning panel, and stops the experiment from being created.** |
| `front_end/panels/status_panel.py` | `upload_aws_handler` uses bucket, prefix, storage class and retries from the settings, and logs the S3 destination first. The note upload uses `server_root`. If settings are not loaded, the note is saved locally only. |
| `system/imaging/max_projection.py`, `imaging_system.py` | `ImagingSystem(..., storage=None)`; `send_protocol` and `send_to_server` use `storage.remote_path()`. The six `scope(...)` calls pass `storage=self.app.storage`. |
| `front_end/Widgets.py`, `mainwindow.py` | Server user/host fields pre-filled from `storage.json` (still editable, per session). Bucket and server folder shown read-only. AWS account and password fields show `unused`, stay disabled, personal email removed. |
| `front_end/panels/experiment_config_panel.py` | The "upload to AWS" checkbox no longer enables the unused AWS account/password fields. |
| `README.md` | Section "Setting up another lab (storage.json)". |
| `dryrun/tests/` | `test_storage_settings.py`, `test_storage_callsites.py`: 25 tests, all passing on the dev PC. Includes a scan that no old lab value remains in `code/` outside `storage.json`. |

Fixed in code, not configurable: SHA256 checksum, zstd level 3.

## Decisions made with the user
- Flat keys, separate `storage.json`, one file per install.
- Missing `storage.json` is an error. Missing or unknown keys are errors.
- Server user/host stay in the GUI (they are switched between runs); folder and bucket come from the file only and are read-only in the GUI.
- AWS account/password fields: unused, grayed out, labeled `unused`.
- Test runs automatically at experiment creation only (no buttons), confirms access only (no write test).
- **Both a `storage.json` error and a connection failure block experiment creation.**
- Optional S3 prefix is supported (default empty).

## Assumptions still to be verified
- Key login: the server test uses `BatchMode`, so it fails if the server needs a password. The end-of-run upload cannot ask for one, so ssh keys are assumed on Elm.
- `aws` and `ssh` are on PATH of the process that runs the program.
- The GUI reads `config_file/storage.json` relative to the working directory, like `scope.json` (the program is started from `code/`).
- Layout: the new rows (bucket under the AWS row, server folder under the server row) have not been looked at in a real window.

## Not tested yet
- ~~Full-GUI dry run~~ Done 2026-10-16 against origin/main (see the update above); as expected. Not done against the Elm reference tree.
- The "Please wait" window and the grayed-out widgets in a real, visible window (the dry run hides all windows).
- A real S3 upload, a real `scp`/`ssh`, and the connection tests against the real account and server.
- The AWS test does not prove write permission to the bucket.

## Elm test checklist
Setup: check out `feature/configurable-aws-bucket` in a **separate folder** from the Elm reference (`C:\Users\SVC_barseq\Seq_o_matics_2.5\` is read-only reference; never write to it, and never copy secrets from it). Start the program from the `code` folder.

0. Dry run first, if possible: `python -m dryrun.run --trees main,branch --scenarios imaging_uploads` and `imaging_only`, then compare the command traces for main and branch.
1. **Window:** both tabs show the server user/host pre-filled, a read-only server folder row, a read-only bucket, and `unused` in the grayed AWS account/password fields. Nothing is cut off.
2. **Happy path, both boxes ticked:** create an experiment. The log shows "Testing connections..." then two `OK` lines. The experiment is created.
3. **Nothing ticked:** the experiment is created and no connection test runs.
4. **Block, bad file:** rename `storage.json`, create an experiment. Expect a dialog naming the file and no experiment. Restore the file.
5. **Block, typo:** change `aws_bucket` to `aws_bucked`. Expect a dialog naming the missing and the unknown key. Restore.
6. **Block, bad bucket:** set a nonexistent bucket with the AWS box ticked. Expect "bucket not accessible" and no experiment. Restore.
7. **Block, bad server:** change the server host in the GUI to an unreachable address (and separately a wrong `server_root`) with the server box ticked. Expect a failure message and no experiment.
8. **Real run, short:** a one-cycle run with both uploads ticked. Check that the files arrive in `s3://<bucket>/[<prefix>/]<experiment>_maxprojection/<cycle>.tar.zst` and in `<server_root><experiment>_maxprojection` on the server. Compare with what main did for the same data (same names, same locations).
9. **Another lab (when available):** edit only `storage.json` (bucket, server user/host/folder) and repeat steps 2 and 8.
10. Record results (pass/fail, log text for any failure) in this file.

## Open items
- `feature/manual-aws-upload` hardcodes the bucket in two places (`aws_upload_worker.py`, `Widgets.py`). Rebase it onto the new main and make it use `storage.json` after this branch is accepted.
- The Start button's confirmation window re-reads `scope.json` but not `storage.json`; edits to `storage.json` take effect at the next experiment creation.
- Optional later: a write-permission test for the bucket and the server folder (declined for now).
