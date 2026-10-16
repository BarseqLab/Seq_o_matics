# Plan: a Python environment on the dev PC for the dry run and the remaining tests

**Date:** 2026-10-16. **Status:** done 2026-10-16 (user approved Q2 and Q3). Results: `plans/storage_settings_STATUS.md`, section
"Update 2026-10-15/16". The scratch grew to 50 GB (not "a few GB") and was deleted; traces kept in `figs/dryrun_traces/`.

## Goal
1. Run the 3 unit tests that cannot run with the dev PC's Python 3.13 (`test_fakes`, `test_zstack` need numpy;
   `test_protocol_lookup` needs pytz).
2. Run the full-GUI dry-run harness (`dryrun/`) on this branch and on `main`, to check the storage.json work in the
   real program with fake hardware. This is the "full-GUI dry run" that `plans/storage_settings_STATUS.md` lists
   as not done.

## What I found
- **Conda: Anaconda3 2024.06 (conda 24.5.0) at `C:\Users\xiaoyin.chen\AppData\Local\anaconda3`**, not on PATH
  (found 2026-10-16 after the user said it exists; the first search missed `AppData\Local`). Its first
  `envs_dirs` entry is `c:\barseq_envs`, where the user's other envs live; channels conda-forge, defaults.
- **The packages need Python 3.10.** `environment.yml` pins `python==3.10.13`, `numpy==1.26.0`, `pandas==1.5.3`,
  `scikit-image==0.20.0`, `matplotlib==3.5.3` (the Elm versions). pandas 1.5.3 and scikit-image 0.20 have no wheels
  for Python 3.13, so a plain `py -m venv` would need newer versions than Elm runs, which weakens the test.
- **The dry run's defaults point at Elm.** `dryrun/run.py` uses `REF_DIR = C:\Users\SVC_barseq\Seq_o_matics_2.5`
  (the Elm reference tree, the `ref` tree) and `--scratch C:\Users\SVC_barseq\Seq_o_matics_dryrun`. Those are
  off-limits and probably absent here. Without `ref`, the harness can still compare `branch` with `main`
  (`main` comes from `git archive`, no Elm access).
- The harness fakes `serial`, `nidaqmx` and `pycromanager`, and records `ssh`/`scp`/`aws` without running them, so
  no hardware or network is touched. `nidaqmx` and the pycromanager deps are therefore not needed.

## Proposed steps
1. ~~Install Miniforge~~ Not needed: use the existing Anaconda, by the full path to its `Scripts\conda.exe`.
2. **Create the environment** from the project's own file, so it matches Elm:
   `conda env create -f environment.yml -n seqomatic-dryrun`, which lands in `c:\barseq_envs\seqomatic-dryrun`
   (this install's default). It downloads the packages from conda-forge and PyPI. This includes `nidaqmx==0.9.0` by pip; harmless
   (the harness blocks the real module), and keeping the file unchanged is simpler than a trimmed copy.
3. **Run the unit tests** in it: `python -m unittest discover -s dryrun/tests -t .` (expect 54 tests, 0 errors).
4. **Dry run, branch vs main**, scratch inside the project.
   *Change found while preparing (2026-10-16):* the `main` tree uses `git archive upstream/main`, but this repo
   has no `upstream` remote (only `origin`, `fork`); and the report's device-by-device comparison is only made
   against the tree named `ref`. Since `run.py` skips preparing a tree whose folder already exists, I put
   `origin/main` (9f8e7d2) code into `figs\dryrun_scratch\trees\ref` and run `--trees ref,branch`: in this report
   **`ref` means origin/main, not the Elm reference**. No harness edits. Command:
   `python -m dryrun.run --trees ref,branch --scenarios ... --scratch figs\dryrun_scratch --report figs\dryrun_report.md`.
   Originally planned:
   `python -m dryrun.run --trees branch,main --scenarios imaging_uploads,imaging_only,prime_wash,cancel_restart,auto_full --scratch figs\dryrun_scratch --report figs\dryrun_report.md`
   then `imaging_thick_46,imaging_thick_100` on `branch` only.
   Size: "a few GB" of synthetic images for all scenarios; delete `figs\dryrun_scratch` afterwards.
5. **Read the report** and check, for each scenario, that branch and main match except for what the storage work
   should change:
   - `imaging_uploads`: the same `aws s3 cp`, `scp`, `ssh mkdir` commands as main, plus exactly four new
     connection-check commands at Create (`aws --version`, `aws sts get-caller-identity`,
     `aws s3api head-bucket --bucket barseq-acquisition`, `ssh -o BatchMode=yes ...`). The fake `subprocess.run`
     returns rc 0, so the check passes and the run goes on.
   - All other scenarios (uploads off): no new commands, same device traces as main.
   - The new "Please wait" window appears only in `imaging_uploads` (the harness hides all windows; it records them).
   - No hang, no guard problems.
6. Record the results in `plans/storage_settings_STATUS.md`.

## Assumptions and risks
- The harness was written on Elm; it may assume Elm paths in places besides `REF_DIR`/`--scratch` (it says the fake
  COM ports "match the ports on this PC"). If it fails for that reason I will stop and report, not patch the harness.
- The `main` tree comes from `git archive` of upstream `main`; `git fetch` was run on 2026-10-15.
- Without the `ref` tree, this checks branch against main only, not against the Elm reference program.
- A dry run proves the program logic with fake devices. It does not test the real AWS/ssh, the window layout, or
  hardware timing.

## Questions for you
- **Q1.** Resolved: use the existing Anaconda.
- **Q2.** Approved: `c:\barseq_envs\seqomatic-dryrun`.
- **Q3.** Approved: dry-run scratch in `figs\dryrun_scratch`, deleted afterwards.
