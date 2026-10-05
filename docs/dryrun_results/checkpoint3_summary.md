# Checkpoint 3: branch after the fix loop vs the Elm reference

**Date:** 2026-10-05
**Branch:** `reference-parity` @ `6a283f9`
**Run:** `python -m dryrun.run --trees ref,branch --scenarios all --jobs 4 --fresh-trees` (12 scenarios × 2 trees, 100× speed, about 9 min)
**Full generated report:** `docs/dryrun_results/checkpoint3_report.md`

## Result
The branch now behaves like the reference in every scenario. The only differences left are the approved deviations, a few text/timing differences that do not affect the run, and bugs that are present in both trees.

### Scenarios with no fluidics/imaging difference

`auto_full`, `imaging_only`, `imaging_uploads`, `imaging_two_channels`, `prime_wash` and `heater_fault`.

In all six, these channels are identical to the reference:
- pump commands and dispensed volumes;
- every valve move on both selectors;
- every DAQ write per heater channel;
- every acquisition (frames, channels, z range, exposures);
- external commands (ssh/scp/aws);
- the files written to the experiment folder and the max-projection drive;
- focus results, which are also equal to the true best plane in every cycle.

Remaining differences in these scenarios:

| Difference | Why | Status |
|---|---|---|
| Piezo parked at 200 instead of 185 before each focus stack | Approved (H3). The stack planes are unchanged. | deviation |
| Extra GUI panel messages (step i/n, reagent → port, heater start/end, configuration) | Approved (Q4) | deviation |
| `log.txt`: the protocol-load line reads `load Fluidics_sequence_X.json protocol!` (the reference: `load Fluidics_sequence_X protocol` + `!` on the next line) | C07, kept | text only |
| `log.txt`: heater temperature readings differ in number and value | Timing of the simulated heater; differs between any two runs | noise |
| Live-view thread still running at the end of `auto_full` / `imaging_two_channels` | D22. Happens in **both** trees at 100× speed. | shared bug |

### Cancel scenarios (approved deviation: Cancel stops and releases everything)

| Check | ref | branch |
|---|---|---|
| Pump stops when Cancel is pressed (`cancel_restart`, `prime_cancel`) | no: the dispense runs to its end | **yes** |
| No PBST flush / further pumping after Cancel during Prime | no: 3.8 mL pumped after Cancel | **yes** |
| Serial ports and heater DAQ released after Cancel (all cancel scenarios) | no | **yes** |
| Start / Prime again after Cancel works | no: `COM11: Access is denied` | **yes** |
| No program thread left waiting after Cancel during focus / max projection | yes | yes |

### Pump-speed field (approved deviation)
| Check | ref | branch |
|---|---|---|
| Field pre-filled at start-up | no: blank | yes: `1.58` |
| Prime with an empty field | crashes with `ValueError` | asks for a value |
| Value saved by Start | `1.58` + blank line | one clean line |

### Shared bugs still present (both trees, not changed)
- **D02 + heater error handler** (`heater_fault`):
  - Both trees put the failed stage back in image mode at once and report the heat step as failed, so P08/P09 are fixed.
  - Both trees then raise `UnboundLocalError: name` in the handler's queue line.
  - The run then waits forever ("Heater is wrong", no signal).
- **D23** (`cancel_focus`): after Cancel during focus with "Skip alignment", the mock alignment raises `FileNotFoundError`. The automation thread ends, with no hang and no device effect. The "focus picks the sharpest plane" and "dicfocus holds 4 images" checks fail there in both trees, as expected after a Cancel.
- **D22:** see above.

## The new scenarios catch the old bugs
Run against the code before the fixes (`3393477`):
- `heater_fault`: the stage stays in heat mode for about 500 s after the error, and the step is reported as heated (P08/P09).
- `imaging_two_channels`: focus never completes (`reshape(80)`), and the run hangs (P07).

Checkpoint 2 showed the original scenarios catching P01–P03, P06, P10–P13 and P16 on the unchanged branch.

## Next
Step 4 of the plan:
- run with the Micro-Manager demo config;
- then the Elm water test, including Cancel mid-pump and Start again, and confirming the pump really stops.

Open decisions for the user:
- whether to fix the shared bugs D02 (heat failure waits forever) and the heater handler's `UnboundLocalError`;
- whether to fix D22 and D23.
