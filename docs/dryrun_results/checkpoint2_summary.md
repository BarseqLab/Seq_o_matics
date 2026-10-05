# Checkpoint 2: dry-run harness on the unchanged branch

**Date:** 2026-10-05
**Harness:** `dryrun/` (see `dryrun/README.md`)
**Full generated report:** `docs/dryrun_results/checkpoint2_report.md`

## What was run

- **Trees.** Each tree was run through each scenario with every hardware boundary faked: pump, selectors, heaters/DAQ, Micro-Manager, ssh/scp/aws.
  - `ref`: the Elm reference.
  - `branch`: this branch at `c15f832`+, i.e. upstream `main` code with Elm config and data files.
  - `main`: upstream `main` as published.
- **Scenarios:**
  - `auto_full`: 3 fluidics protocols + strip + HYB + 4 imaging cycles.
  - `imaging_only`.
  - `imaging_uploads`: server and AWS boxes ticked.
  - `prime_wash`.
  - `cancel_restart`.
- **Speed:** 100× real time. All 15 runs together took about 6 minutes of wall time.
- **Unit tests:** `python -m unittest discover -s dryrun/tests -t .` gives 9 tests, OK.

**Reference results.** The reference completed every scenario. On every focus run, it chose the true sharpest plane of the synthetic sample. The cycle-to-cycle drift of +1.5 µm was tracked correctly through the `offset*.csv` → `pre_adjusted_pos.pos` loop.

## Known regressions: caught?

| Item | What the harness showed on `branch` (or `main`) | Caught |
|---|---|---|
| **P01** fluidics completion never signalled | `auto_full`: the first fluidics step is identical to `ref` (first 14 dispenses and 18 valve moves match), then the run hangs. Thread stuck at `automation_controller.py:105 start_image_event.wait`. Ports COM9/10/11 and all Dev3 channels are still held. | Yes |
| **P01/P02** Prime/Wash flush | `prime_wash`: Prime fills the lines, then hangs at `fluidics_control_panel.py:86 cycle_done_event.wait()`. No PBST flush, no Wash, devices never released. | Yes |
| **P03** focus images in the wrong folder | `dicfocuscycle00/` and `dicfocusgeneseq01/` are empty. `Pos0..3.tif` are written into the program folder. | Yes |
| **P04** wrong config (`main` only) | `main`: heater config raises `DaqError` (no Dev2 on this PC), and selector config fails (COM6 is busy). Start refuses with "Please config all devis!". | Yes |
| **P06** focus sweep ±40 | 108 frames, z 160–239.5 (ref: 80 frames, 170–228.5). | Yes |
| **P10** AWS upload stub | `imaging_uploads`: `ref` runs `aws s3 cp …geneseq01.tar.zst s3://barseq-acquisition/…`; branch sends nothing. | Yes |
| **P11** upload checkboxes ignored, `send_protocol` re-enabled | `imaging_only` (boxes unticked): branch sends 12 ssh/scp commands, including every json/txt/csv in the experiment folder; `ref` sends none. | Yes |
| **P12** default server | branch commands go to `imagestorage@jackw-ux1`; `ref` uses `10.128.30.152`. | Yes |
| **P13** pump 1.2 mL/min on connect | Pump command `S001142` (1.199 mL/min) instead of `S001428` (1.499). In `prime_wash`, each 1 mL fill delivers 0.758 mL instead of 0.947 mL. | Yes |
| **P16** focus details | No `stop_stage_sequence` before each XY move. Piezo parked at 200 instead of 185 (200 is the value approved for this branch). Worker count is not visible in a trace. | Yes (a, b) |
| **Q4** `log.txt` duplicates and extra panel messages | Every fluidics line appears twice in `log.txt`. The extra INFO lines are listed in the GUI-text diff. | Yes |
| **P05/P21** Elm data files | Already fixed on the branch (commit `3393477`), so no difference. On `main` they are not reached, because the configs fail first. | n/a |

### Not exercised by the current scenarios
Planned additions before or during the fix loop:
- **Fault injection:**
  - P08/P09: heater DAQ error during a heat step.
  - D02: a failed heat step.
- **Cancel during imaging:** P17 (max-projection cancel path), Q2 (`make_tile` and max-projection waits ignore Cancel).
- **Manual imaging tab:** P14 (live view `process_cycle`).
- **Different align and focus channels:** P07 (`reshape(80)`), and the pass-2 rule from Q3.
- **Not planned for now:** P15 (tissue scanner, unused on Elm), P18 (hand-edited protocol names), P19/P20 (rare I/O errors).

## New finding: Cancel leaves devices held, so the next Start fails (both trees)

This answers the question asked on 2026-10-05.

`cancel_restart`: Start → Cancel during the second pump step of geneseq01 → Start again.

| | ref | branch |
|---|---|---|
| Pump stops when Cancel is pressed | no: the current dispense runs to its end (known; change deferred) | same |
| Serial ports released after Cancel | no: COM9, COM10, COM11 still open | same |
| DAQ channels released after Cancel | no: all Dev3 heater channels still reserved | same |
| Start again after Cancel | **fails**: `SerialException: could not open port 'COM11': Access is denied` in `connect_selector` | same |

Why:
- Cancel never calls `disconnect_*`; only normal completion, protocol errors and the end of Prime/Wash do.
- On restart, the pump reconnects, because a new pump object replaces the old one and the old port is closed when Python collects it.
- The selector object is reused, so its old ports are still open, and the restart fails there. Any heater tasks that were open also stay reserved, because nidaqmx does not release a task that is collected without `close()`.
- In practice, after a Cancel the operator has to restart the program.

This is listed as **D21** in `docs/parity_inventory.md`. It touches the deferred "Cancel stops the pump" work, because `disconnect_pump` sends the pump stop command. A proposal belongs with that work.

## Harness caveats
- Device answers and timings are models.
- CPU-heavy work runs at real speed, so it appears 100× longer in virtual time.
- Images are 1024 × 1024 instead of 3200.
- Alignment is skipped, as in real Elm runs.
- The Micro-Manager Java side is not involved; step 4 covers it.
