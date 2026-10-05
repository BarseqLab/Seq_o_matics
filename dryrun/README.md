# Dry-run harness

This harness runs the real Seq-o-Matic program, GUI included, with **every piece of hardware replaced by a fake that records what it was told to do**. Two versions of the program can then be run through the same scenario, and their records ("traces") compared device by device.

It is step 2 of `plans/reference_parity_plan.md`.

## Safety

- **No real hardware can be reached.**
  - `dryrun/guard.py` places the fakes under the real module names (`serial`, `nidaqmx`, `pycromanager`).
  - It also installs an import hook that refuses to load any real module of `serial`, `nidaqmx`, `pycromanager`, `pymmcore`, `zmq` or `ndtiff`.
  - Each trace lists any guard problems; there must be none.
- **The program never runs in place.** Each run copies the tree into a scratch folder, so the Elm reference folder `C:\Users\SVC_barseq\Seq_o_matics_2.5\` is only read, never written.
- **No windows appear and nothing is sent anywhere.** All windows (`Tk` and `Toplevel`) are hidden (`DRYRUN_SHOW_GUI=1` shows them). Message boxes are answered automatically and recorded. `ssh`, `scp` and `aws` commands are recorded, never executed.

## Running

From the worktree root, with the Elm Python env:

```
C:\Users\SVC_barseq\.conda\envs\seq_o_matic\python.exe -m dryrun.run --trees ref,branch,main --scenarios all --jobs 3
C:\Users\SVC_barseq\.conda\envs\seq_o_matic\python.exe -m dryrun.run --trees ref,branch --scenarios imaging_only
C:\Users\SVC_barseq\.conda\envs\seq_o_matic\python.exe -m dryrun.run --trees ref,branch --scenarios all --report-only
C:\Users\SVC_barseq\.conda\envs\seq_o_matic\python.exe -m unittest discover -s dryrun/tests -t .
```

- **Trees:**
  - `ref`: the Elm reference.
  - `branch`: this worktree's `code/`.
  - `main`: upstream `main`, via `git archive`.
  - Or any path to a code folder.
- **Output** goes to `C:\Users\SVC_barseq\Seq_o_matics_dryrun\` (`--scratch`):
  - `runs\<tree>__<scenario>\trace.json`: every recorded event plus the end state.
  - `runs\<tree>__<scenario>\console.log`: the program's printed output.
  - `report.md`, or the path given with `--report`.
- **Disk:** a full `--scenarios all` run on three trees writes a few GB of synthetic images to the scratch folder. Delete it when done.

## Scenarios (`dryrun/scenarios.py`)

| Scenario | What the operator does |
|---|---|
| `auto_full` | Create experiment, configure all device groups, Start. Protocol: geneseq01 fluidics → imagecycle00 → imaging geneseq01 → geneseq02 fluidics → imaging geneseq02 → strip → HYB → imaging hyb01. Uploads off. |
| `imaging_only` | Same setup, imaging steps only (imagecycle00, imaging geneseq01). Uploads off. |
| `imaging_uploads` | As `imaging_only`, with "Send to storage server" and "upload to AWS" ticked. |
| `prime_wash` | Prime (fill all lines + 4 mL PBST in-chamber flush), then Wash. |
| `cancel_restart` | Start, press Cancel during the second pump step of geneseq01, then press Start again. |
| `imaging_thick_46`, `imaging_thick_100` | As `imaging_only`, with `z_stack_thickness_um` 46 or 100 in `scope.json`: 2 or 3 sub-stack projections per tile. Run them on `branch` only; the reference ignores the key. |

All scenarios:
- tick "Skip alignment", as real Elm runs do;
- type pump speed 1.58;
- use one slide, one slice, 4 corner positions, which gives 2 tiles.

## What the fakes model

| Real | Fake | Notes |
|---|---|---|
| Ismatec pump, COM9 | `fake_serial.IsmatecEmulator` | Answers the IPC protocol and tracks timed dispenses. Each dispense is recorded with its duration, rate and nominal volume. |
| Elveflow MUX, COM11 / COM10 | `fake_serial.MuxEmulator` | Records each valve move. |
| Other ports | COM6 busy (held by Micro-Manager on Elm); COM1/2/4 silent; anything else missing | Matches the ports on this PC. As on Windows, a port can be open only once. As in pyserial, garbage collection closes a port. |
| NI-DAQ heaters, Dev3 | `fake_nidaqmx` | First-order thermal model: the sensor approaches the set-point while in heat mode. Any device other than Dev1/Dev3 is invalid, as on this PC. A task that is not closed stays reserved, as in nidaqmx 0.9. |
| Micro-Manager `Core` | `fake_pycromanager.Core` | Records stage, piezo and shutter calls. `get_property` answers the piezo travel (0–400 µm, as in Elm's config). |
| `Acquisition` | `fake_pycromanager.Acquisition` | Writes real NDTiff datasets (`<name>_1/<name>_NDTiffStack.tif` + `NDTiff.index`) that tifffile reads exactly like Elm data. For example, a channel swept twice collapses to the second sweep. |
| Images | `images.py` | Synthetic sample with a **known best-focus plane** per position, which drifts 1.5 µm per cycle. The report checks that focus picks it. |
| Time | `clock.py` | Everything runs 100× faster (`--speed`). Real thread concurrency is kept. |
| `ssh` / `scp` / `aws` | `fake_os.py` | Recorded only. |

**Test-only config changes**, applied identically to every tree:
- `scope.json` `imwidth` → 1024, for smaller images.
- `maxproject_drive` `D:\` → a scratch folder. Any other drive is left as is, so a wrong drive still fails.

All other config is each tree's own.

## Reading the report

- **Behaviour checks:** absolute pass/fail per tree. For example: no hang, devices released, `dicfocus` folders filled, focus correct, uploads only when ticked.
- **Channel comparison:** each device's record compared with the reference, with diffs. Log and GUI text are compared as sorted lines, because thread pools finish positions in varying order.
- **Hangs:** the watchdog stops a run after 3 virtual hours without progress and records where each program thread was waiting.

## Limits

- The fakes are models: device answers and timings are approximate.
  - CPU-heavy work runs at real speed, so it looks 100× longer in virtual time.
  - Real alignment is not exercised, because the scenarios use "Skip alignment".
  - The Micro-Manager Java side is not involved; step 4 of the plan, with the Micro-Manager demo config, covers it.
- Passing here is necessary, not sufficient. Water tests on Elm remain the final check.
