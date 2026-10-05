# Plan: make the refactored code behave exactly like the Elm reference

**Branch:** `reference-parity` (from `main` @ `5e5adf0`)
**Status:** plan only. Nothing below has been started.
**Recorded:** 2026-10-05

## Goal

The refactored code on `main` (committed 2026-04-01, "Commit to production level") cannot finish an automated run and differs from the validated Elm setup in many places. This branch should behave **exactly** like the reference folder that is known to run correctly on Elm:

- Fix every regression the refactor introduced.
- Keep the refactor's structure (panels, `system/imaging/*`, logging, `constants.py`).
- Keep the bug fixes `main` already has over the reference, each one reviewed.

Each change must be verified by a hardware-free dry run before the code goes on the scope.

## Where things are (Elm PC)

| What | Path | Notes |
|---|---|---|
| **Reference (the spec)** | `C:\Users\SVC_barseq\Seq_o_matics_2.5\` | Known good on Elm. **Never modify it.** It is not in git. |
| Production snapshot | `C:\Users\SVC_barseq\Seq_o_matics_2.5_production\` | Its `code/` is the same as `main` except for config values, which match the reference. |
| Existing bug report | `C:\Users\SVC_barseq\Seq_o_matics_2.5_production\BUG_REPORT_vs_reference.md` | 18 regressions of `main` vs the reference. This is the starting list for Step 1. |
| Clone of this repo | `C:\Users\SVC_barseq\Seq_o_matics_github\` | |
| Worktree for this branch | `C:\Users\SVC_barseq\Seq_o_matics_github\.claude\worktrees\reference-parity\` | |
| Python env used on Elm | `C:\Users\SVC_barseq\.conda\envs\seq_o_matic\` | Python 3.10.13, pycromanager 0.29.9, ndtiff 3.1.0, nidaqmx 0.9.0, pyserial 3.5, tifffile 2025.2.18, opencv 4.6.0, zstandard 0.25.0. No pytest. |
| Micro-Manager | `C:\Program Files\Micro-Manager-2.0\` | `MMConfig_demo.cfg` is available for the Step 4 demo run. |
| Elm past data | `D:\*_maxprojection\` | Real inputs for image-maths tests. |

## Decisions already made

1. **Configs:** the branch carries Elm's configs:
   - `ElveflowMuxDevice_selector.json`: COM11 / COM10
   - `Heat_stage.json`: `Dev3`
   - `scope.json`: `maxproject_drive` `D:\`
   - Calibration and protocol files come from the reference too: `pump_speed_calibration.txt` = 1.58, the strip protocol with its PBST washes, the gasket folder names, and the slide and chamber coordinates.
2. Every difference between the reference and `main` goes into one of four groups. **Each item is reviewed with the user before it is acted on.**
   - **A. Fixes in `main` that the reference lacks** → keep, after review.
   - **B. Regressions in `main`** (the reference is right) → fix back to reference behavior, after review.
   - **C. Neutral refactor changes** (logging, type hints, module split, constants) → keep, as long as behavior is unchanged.
   - **D. Bugs both versions share** → list them only. Do not fix without explicit approval, because the goal is exact reference behavior.
3. **The plaintext AWS password** in the reference (`front_end/Widgets.py:319`) is never copied anywhere: not into code, docs, tests or commits. The AWS CLI's own credentials are used, as in the reference.
4. **Tests use the stdlib `unittest`**, so nothing is installed into the `seq_o_matic` env.

### Known group-A items (to review)
1. **Cancel stops the heater.** Reference `front_end/Widgets.py:1078` has `self.fluidics.Heatingdevice.cancel==1`, a comparison, so Cancel never stops the heater. `main` uses `= 1`. This changes behavior on purpose: with the fix, Cancel actually stops the heaters.
2. **Tissue-scanner image save.** Reference `front_end/tissue_scanner.py:260` calls `tiff.imsave`. The tifffile installed on Elm (2025.2.18) has no `imsave`, so this line fails on Elm. `main` uses `tiff.imwrite`.
3. **Unknown protocol name.** In the reference, `find_protocol` crashes later with `UnboundLocalError`. `main` raises `FileNotFoundError`.
4. **`recipe_builder.py` typo.** Reference has `def __int__` instead of `__init__`. This is cosmetic.

### Known group-B items (to review)
- **Items 1–18** of `BUG_REPORT_vs_reference.md`. Highlights:
  - fluidics-done events are never set, so automation hangs;
  - the prime/wash flush never runs;
  - focus images are written to the working directory, so alignment always aborts;
  - `reshape(80, …)` with a ±40 sweep (the reference uses `reshape(-1, …)` and ±30);
  - the heater `status[i] = 0` reset is missing;
  - the AWS upload is a stub;
  - the upload checkboxes are ignored and `send_protocol` is re-enabled;
  - manual live view needs `process_cycle`;
  - the pump starts at 1.2 mL/min instead of 1.5;
  - the default server is `jackw-ux1`;
  - tissue-scanner tiles are flipped and get CLAHE;
  - focus-step details changed;
  - max projection's cancel path is missing `stop_stage_sequence`;
  - protocol lookup order changed;
  - the Ismatec `dispenseRate` print;
  - `zstandard` and the AWS CLI are not listed as dependencies.
- **Bundled packages shadow the env.** `code/mainwindow.py` puts `code/supplementary/package` first on `sys.path`, so the refactor imports bundled copies of pycromanager (0.29.9, lightly patched) and **ndtiff 2.2.1**. The reference imports the env's packages (ndtiff 3.1.0). For parity, the env's packages must win.
- **Configs** (see decision 1).

## Step 1: Behavior inventory (checkpoint 1)

1. Map every reference function to its counterpart in the refactor. Examples:
   - `front_end/Widgets.py` → `front_end/panels/*`, `front_end/automation_controller.py`, `front_end/Widgets.py`
   - `system/image_acquisition_and_analysis_system.py` → `system/imaging/*`
   - `system/fluidics_exchange_system.py` → the same file plus `system/fluidics/*`
   - `device/*`, `driver/*`, `front_end/tissue_scanner.py`, `recipe_builder.py`, `logwindow.py`, `experiment_profile.py`, `mainwindow.py`
2. Read each pair side by side and record every behavior change, with `file:line` on both sides. Cover:
   - device commands and their order;
   - timings, sleeps and timeouts;
   - default values;
   - file and folder paths, and whether they are relative or absolute;
   - thread and event signalling;
   - error handling and cancel paths;
   - GUI defaults and checkbox semantics;
   - uploads.
3. Put each change in group A, B, C or D and propose an action.
4. Also compare the non-code files: configs, `reagent_sequence_file/**`, `device/tissue_scanner/**`, `pump_speed_calibration.txt`.
5. **Deliverable:** `docs/parity_inventory.md` on this branch. It has one row per item: ID, group, reference location, refactor location, description, proposed action, and a user decision column (keep / fix / discuss).
6. **Checkpoint 1:** the user reviews every row. No code changes until this is done.

## Step 2: Dry-run harness, no hardware (checkpoint 2)

Run the real program, GUI included, with every hardware boundary replaced by a fake that records what it was told to do. Then run the reference and the branch through the same scenarios and compare what each one did.

### Fakes
They are installed into `sys.modules` before any program code is imported.

| Real | Fake |
|---|---|
| `serial` (Ismatec pump `driver/ismatec_ipc.py`, Elveflow MUX `device/Selector.py`, KMtronic relay `driver/kmtronic_relay.py`) | Port objects that parse each device's command protocol, reply the way the real device does, and log `(sim_time, device, port, command)`. |
| `nidaqmx`, `nidaqmx.system` (`device/Heatingstage.py`: AO setpoint, DO mode lines, AI temperature) | A first-order heater model. Temperature moves toward the setpoint over simulated time, so the heat-and-wait loops run for real. Every write and read is logged. |
| `pycromanager.Core` | Records `set_position`, `set_xy_position`, `stop_stage_sequence`, `wait_for_device`, `set_shutter_open`, and so on. |
| `pycromanager.Acquisition` | Records the events it receives, and writes `<dir>/<name>_1/<name>_NDTiffStack.tif` in the same layout the code reads back. The images are **synthetic, with a known best-focus plane and a known XY shift per cycle**. This lets the tests check that focus picks the right plane and that alignment recovers the right offset. |
| `multi_d_acquisition_events` | The real function. It is pure Python. |
| `os.system`, `subprocess.run` / `Popen` (scp/ssh to the server, `aws s3 cp`) | Recorded, never executed. |
| `time.sleep` (and `time.time` where it is used for timing) | A virtual clock. Sleeps advance simulated time and take almost no real time. |
| `tkinter.messagebox`, `filedialog` | Recorded, and answered from the scenario script. |

### Launcher
`dryrun/run.py --tree <folder> --scenario <name> --out <trace dir>`

1. **Copy the tree to a scratch folder first.** Neither the reference nor the branch is ever run in place, because the program writes into its own folder (temp files, `aixintest.csv`, tissue-scanner files). Running the reference must leave `C:\Users\SVC_barseq\Seq_o_matics_2.5\` untouched.
2. Use a test `scope.json`: the same values as Elm, with `maxproject_drive` and the experiment path pointing into the scratch folder.
3. Install the fakes, start the real Tk GUI (hidden), and drive it by calling the button handlers in the order a user would: create experiment → start automation. Wait on the simulated clock until the run finishes or a timeout is reached.
4. Use the `seq_o_matic` env as-is.

### Scenarios
- **Short automated run:** fill → geneseq01 → imaging → geneseq02+ → imaging → strip.
- **Prime/wash.**
- **Cancel** during fluidics, during heating, during focus and during max projection.
- **Upload settings:** AWS on/off × server on/off.
- **Manual imaging (Step 4 of the GUI)**, including live view.

Use 1–2 positions per run. A full-size frame is 3200 × 3200 × 16-bit ≈ 20 MB, and a focus stack is 40 planes (reference) or 54 (`main`).

### Trace and comparison
Each run writes:
- each device's command list, in order, with simulated time;
- the files and folders created, with images summarized as shape, dtype and a hash or summary statistics;
- the focus plane chosen and the alignment offset for each position;
- the upload and copy commands;
- the order of the main phases and the GUI log lines.

The comparison:
- Compare **each device's command list separately** and the **order of the main phases**. A single global interleaving is not stable because the reference polls and the refactor uses events.
- Ignore wall-clock timestamps and the log lines that only the refactor adds.
- **Pass** = the reference and the branch traces are identical, except for approved group-A items. Those must appear as expected, labelled differences.

### Unit checks on the image maths
Feed the same inputs to the reference and to the branch and require equal outputs. The inputs are synthetic stacks plus real data from `D:\*_maxprojection`. Cover:
- focus-plane selection;
- sharpness;
- alignment / offset;
- max projection;
- tiling and position generation;
- protocol lookup for every process name.

### Checkpoint 2
Run the harness on the **unchanged** branch. It must catch the known regressions:
- the branch stops after the first fluidics step;
- `dicfocus*` folders are empty;
- the pump starts at 1.2 mL/min;
- the uploads are wrong.

If it misses a known one, improve the harness before fixing anything. Show the user the results.

## Step 3: Fix loop (checkpoint 3)

1. Take one approved inventory item at a time:
   1. Fix it.
   2. Re-run the scenarios.
   3. Confirm that this difference is gone and nothing else changed.
   4. Commit.
2. Make **one commit per inventory item** (or a tightly related group), with the item ID in the message, so each one can be reviewed or reverted.
3. Port configs and data files from the reference in their own commit.
4. Done when every scenario trace matches the reference, apart from the approved group-A differences.
5. **Checkpoint 3:** the user reviews the commits one by one.
6. Commit to `reference-parity` only. Never commit to `main` or merge into it.

## Step 4: Before the scope (checkpoint 4)

1. **Micro-Manager demo run.** Load `MMConfig_demo.cfg` and run the branch with the real pycromanager `Core` and `Acquisition` (demo camera and stages), with the fluidics and heater still faked. This catches problems the fakes cannot, such as real `Acquisition` behavior, the ndtiff on-disk layout, and the Java bridge.
2. **On Elm:** a short run with water and no sample, followed by a real run.
3. **Checkpoint 4:** the user decides when the branch is ready for samples.

## Ground rules
- **Never write to** `C:\Users\SVC_barseq\Seq_o_matics_2.5\`. Read it only.
- **Never reproduce the plaintext AWS password** from the reference.
- The reference is the spec. A difference from it is a bug unless it is an approved group-A item.
- **Group-D (shared) bugs** are listed, not fixed, unless the user approves.

## Open question
Whether this line of work stays a branch of `BarseqLab/Seq_o_matics` or moves to a fork or a separate repo, so that it stays permanently separate from `main`.
