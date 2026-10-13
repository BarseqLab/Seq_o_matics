# storage.json work: record and Elm test checklist

**Last updated:** 2026-10-13
**Branch:** `feature/configurable-aws-bucket` (from main `9f8e7d2`, the fork's `main` brought into this repo). Plan: `plans/storage_settings_plan.md`.
**State:** implemented and unit-tested on the dev PC. **Not yet run on Elm. The full-GUI dry run has not been run.**

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
- Full-GUI dry run (`dryrun/`, needs the Elm Python env and reference tree). Expected: with the shipped `storage.json`, the `aws s3 cp`, `scp` and `ssh` commands are identical to `main`. New connection-test commands (`aws --version`, `aws sts ...`, `aws s3api head-bucket`, `ssh -o BatchMode=yes ...`) appear only when the AWS or server box is ticked.
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
