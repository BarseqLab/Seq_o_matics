# Plan: bring README.md in line with the current code

**Date:** 2026-10-16. **Branch:** `feature/configurable-aws-bucket`. **Status (2026-10-16):** items 1-10 done in README.md. Item 10 (Q1): user chose to remove Option B (`pip install -e .`); I also removed the same command from Option A's optional step 4, and Option C is now Option B. Q2 done:
`docs/config_files.md` fixed (`maxproject_drive` is the local output drive, shipped `D:\`; new `storage.json`
section; intro notes storage.json is an object). Q3: `docs/docs/` deleted (accidental copies; nothing referred to
it). `docs/dryrun_results/` deleted too (user, 2026-10-16); its references in `docs/parity_inventory.md` and
`plans/STATUS.md` now point to git history (`23559b8`, `9011677`), and the `dryrun/run.py` usage example no longer writes there.

Checked against the code in this worktree (button labels in `front_end/Widgets.py`, operator order in
`dryrun/scenarios.py`, file tree, class names, `logging_config.py`, `automation_controller.py`, `scope.json`,
`storage_settings.py`, `workspace_panel.py`). Format kept: same sections, tables, code blocks and `--` style.

## Inconsistencies found, and the proposed edit

| # | README section | README says | Code does | Proposed edit |
|---|---|---|---|---|
| 1 | Quick Start, step 4 | **Automation** tab; buttons **Exp**, **Config Device**, **Prime**, **Start**; no Create step | Tab is **Auto System**. Buttons: **Browse**, **Fill experiment detail**, **Create Protocol**, **Assign Heaters**, **Create Your Experiment**, **Devices configuration**, **Prime lines**, **Start Automation process** (asks to confirm the pump speed). Create must come before Devices configuration and Start. | Rewrite the list in the real order with the real labels; add the Create step and a one-line pointer to the upload boxes and the connection check. Mention the **Manual System** tab in one line. |
| 2 | Experiment Workflow, 1. SETUP | Configure devices -> work directory -> metadata -> protocol | work directory -> metadata -> protocol -> Create experiment (loads storage.json, tests ticked uploads) -> configure devices | Reorder; add the Create step. |
| 3 | Experiment Workflow, 4. UPLOAD | "Copy max-projection images to network drive (M:\\)"; "Upload protocols and data to server via SCP" | Max projections are written during imaging to `maxproject_drive` (shipped `D:\`). At the end of an auto run, only if ticked at Create: server (`ssh mkdir -p`, `scp -r` of `<experiment>_maxprojection` to `server_root`) and AWS (one `<cycle>.tar.zst` per cycle, `aws s3 cp`). The protocol-file upload is disabled. | Replace with the real two optional uploads. |
| 4 | Project Structure | Old tree | Missing: `config_file/storage.json`, `system/storage_settings.py`, `system/connection_check.py`, `system/imaging/autofocus.py`, `ndtiff_stack.py`, `zstack_settings.py`, `code/logo/`, `device/pump_speed_calibration.txt`, `device/tissue_scanner/`, top-level `dryrun/` and `plans/`, `docs/hardcoded_values.md`, `docs/parity_inventory.md`. Renamed: `original_sequence/` is now `original_sequence_250um_gasket/`, `2IRM_and_2CRM/` is now `2IRM_and_2CRM_750um_gasket/`. | Add/rename those entries with one-line comments, same layout. Leave out `docs/docs/` and `docs/dryrun_results/` (see question Q3). |
| 5 | Configuration, `scope.json` bullet | No z-stack keys | `scope.json` has the z-stack thickness and focus keys (`z_stack_thickness_um`, `z_step_um`, ...), documented in `docs/config_files.md` "Z-stack thickness keys" | Add them to the bullet with a link. |
| 6 | storage.json table and text | Retries "at least 1"; `server_root` "must end with `/`"; GUI fields "can be changed per run"; a failed test blocks Create | Retries 1-10; storage class must be one of the 8 AWS classes; `server_root` must start and end with `/`, no spaces, quotes or `//`; user/host/bucket may not start with `-`. The user/host fields can be edited after ticking the server box. Checks run only in auto mode and only for ticked boxes; manual Create checks the file only. A modal "Please wait" window shows during the check; the error says which box to untick. User/host fields refresh when `storage.json` is edited. UTF-8 file (BOM allowed). | Update the table rows and the paragraph under it. |
| 7 | For Developers, Logging | "log.txt: Timestamped structured entries (via `FileHandler`)" | `setup_logging()` is called without a file, and `update_log_file` is never called, so the logging module writes to the console and GUI only. `log.txt` holds the program's own `write_log` lines. | Correct the log.txt bullet. |
| 8 | For Developers, Key Classes | No storage classes | `StorageSettings` (`system/storage_settings.py`), `check_all` / `check_aws` / `check_server` (`system/connection_check.py`) | Add two rows to the System Layer table. |
| 9 | For Developers | No word on tests or the dry run | `dryrun/tests` (80 unit tests), the dry-run harness `dryrun/` with its own README | New subsection "Tests and Dry Run": the unittest command, the conda env from `environment.yml`, a pointer to `dryrun/README.md`, and the note that a full scenario set writes ~50 GB of scratch. |
| 10 | Installation, Option B | `pip install -e .` installs "the package and all dependencies" | `pyproject.toml` dependencies lack `zstandard` (needed for the AWS upload) and the vendored pycromanager deps (`pyzmq`, `dask`, ...) that `requirements.txt` lists | See Q1. |

Not changed (cannot verify from code, or not README facts): hardware models, Micro-Manager version, author line,
the AI-assistant note (incl. its spelling), architecture diagram (still correct at this level).

## Questions
- **Q1.** Option B (`pip install -e .`) misses `zstandard` and the pycromanager deps. Fix in README only (add a note
  that Options A and C are complete and B also needs `pip install -r requirements.txt`), or also add the missing
  packages to `pyproject.toml`? I recommend the README note now; `pyproject.toml` has other problems (its
  `seq_o_matic` package and `seq-o-matic` script do not exist as such) that deserve their own change.
- **Q2.** `docs/config_files.md` has no `storage.json` section and says `maxproject_drive` is a network drive
  (`"M:\\"`); the shipped value is `D:\`. Fix that file too, or README only?
- **Q3.** `docs/docs/` holds copies of three docs files (`architecture.md` and `reagent_sequences.md` identical,
  `config_files.md` an older version without the z-stack section), and `docs/dryrun_results/` holds old checkpoint
  reports. List them in the tree, or leave them out (I suggest leaving them out; `docs/docs/` looks like an
  accidental copy, worth deleting separately)?
