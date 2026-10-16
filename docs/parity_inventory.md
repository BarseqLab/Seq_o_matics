# Reference-parity inventory (Step 1, checkpoint 1)

**Compares:** REF = `C:\Users\SVC_barseq\Seq_o_matics_2.5\` (Elm, known good) and NEW = this branch's `code/` (equal to upstream `main` @ `5e5adf0`).
**Method:** static reading only. Nothing was run on hardware. Five reviewers each covered one area, recorded every behavior difference with `file:line` on both sides, and listed every REF function with its NEW counterpart (coverage tables). I then merged their results and re-checked the key claims against the code.
**Detailed evidence:** `docs/parity_inventory/inventory_{F,I,GA,GB,N}.md`:
- F = fluidics, devices, drivers
- I = imaging
- GA = GUI setup/config/prime/wash
- GB = GUI automation/uploads/tissue scanner/recipe builder
- N = data files, constants, environment

Reviewer IDs (e.g. `F01`, `GB14`) refer to those files.
**Also used:** `C:\Users\SVC_barseq\Seq_o_matics_2.5_production\BUG_REPORT_vs_reference.md` ("BR#"). Its code is identical to NEW, but its **config is not** (see §6).

## How to review

Every row has a **Decision** column. Please fill it in with one of:
- **fix**: change NEW to match REF (the default for group B);
- **keep**: leave NEW as is (the default for groups A and C);
- **leave**: shared bug, do not fix (the default for group D);
- **discuss**.

No code changes until this is reviewed.

| Group | Meaning | Default action | Rows |
|---|---|---|---|
| **B** | Regression: REF is right, NEW differs | Fix NEW to match REF | 21 (§1) |
| **A** | NEW fixes a real REF bug | Keep NEW | 6 (§2) |
| **?** | Needs your decision | (open) | 8 (§3) |
| **D** | Bug in **both** trees | List only, do not fix | 23 (§4) |
| **C** | Neutral or cosmetic difference | Keep NEW unless noted | 13 (§5) |

## Review decisions (2026-10-05)

Context from the user: **Elm currently runs on REF.** No other version has been proven to run. Real runs always use **"skip alignment"**.

| Item | Decision |
|---|---|
| All group-B rows (P01-P21) | **fix**, with the changes below |
| P04, P05, P21 (Elm config and data) | **Done** in commit `3393477`. Every file under `config_file/`, `device/pump_speed_calibration.txt`, `device/tissue_scanner/**` and `reagent_sequence_file/**` is now byte-identical to REF, including folder names; `slide.pos~` was removed. Elm-specific values that are hard-coded in Python come in through the code fixes: default server (P12), pump 1.5 (P13), focus ±30 (P06), piezo 185 (P16). |
| P03 (focus image path) | **fix**, required. With "skip alignment", real runs don't hang, but the DIC best-focus images are not kept in `dicfocus<cycle>/`; they are overwritten in the launch folder. **Confirmed new in the refactor:**<br>- REF does `os.chdir(pos_path/focus<cycle>)` before saving (`system/image_acquisition_and_analysis_system.py:435`).<br>- The pre-refactor upstream commit `f30ab9a` (2025-09-30) does the same (`:342`).<br>- The refactor commit `dc55b5a` (2026-04-01) removed the chdir but kept the relative save (`system/imaging/focus.py:212-214`).<br>- Real REF data has the images where they belong, e.g. `E:\20260928_Dennis_STARmap_Test3\dicfocusgeneseq03\Pos0.tif` (48 per cycle). |
| Hard-coded per-microscope values | Compared in `docs/hardcoded_values.md`. Only 6 differ (H1-H6). **Decision: go with REF for all of them except the piezo pre-position before a focus stack (H3), which becomes 200 µm.**<br>- The pre-position only parks the piezo; the stack planes are absolute (`piezo_event_pos` = position-file piezo ± 30).<br>- Real metadata shows `ZPosition_um_Intended` 170 → 228.5, while `DA Z Stage-Position` stays at the parked 185 (hardware-sequenced).<br>- Every `cycle00.csv` on `E:\` since 2026-01 has piezo 200.0.<br>- Moving these values into config is for a separate session. |
| P15 (tissue scanner) | **fix**: stitching the same as REF (no flip, no CLAHE). The scanner is not used on Elm. Keep `imwrite` (A2), because REF's `imsave` can't run in Elm's env ("keep what works now"). |
| All group-A rows | **keep** |
| GA08 / Q1 (Cancel during Prime/Wash) | **Deviation from REF:** Cancel must **stop**. Skip the 4 mL PBST flush, disconnect the devices and re-enable the buttons. |
| Q2 (Cancel hang in tiling/max-projection waits) | **fix** (deviation from REF) |
| Q3 (doubled focus sweep) | **Keep acquisition unchanged** (both channel passes are still imaged). Recent switch to DAPI for focus/stitching may change again. **Fix the plane search instead (deviation from REF):** pick the best plane only within the 40-image focusing stack.<br>- Proposed rule, the same for equal and different channels: sharpness is computed on the **target-channel pass** (frames N..2N−1), and the saved DIC/alignment image comes from the **align-channel pass** (frames 0..N−1) at the same index.<br>- `max_index` is then always 0..N−1, so the `IndexError` goes away.<br>- Evidence (12 real stacks, `E:\20260928_Dennis_STARmap_Test3`): both passes peak at the same plane, and the second pass is 1-4% less sharp. Results therefore match today's.<br>- **Confirmed: use pass 2.**<br>- Validation:<br>&nbsp;&nbsp;(a) The code builds events `for c in [align_channel, target_channel]`, channel-major (REF `:340-346`, `:424-429`).<br>&nbsp;&nbsp;(b) In the different-channel branch, REF already takes sharpness from `target_channel` frames and the saved image from `align_channel` frames (REF `:374-376`).<br>&nbsp;&nbsp;(c) `docs/config_files.md` defines `*_focus_target_channel` as "Channel used for autofocus" and `align_channel` as "Channel used for inter-cycle image alignment".<br>&nbsp;&nbsp;(d) Real stack metadata (`focusgeneseq01/Pos0_1`) shows frames stored in acquisition order: frame 0 and frame 40 are both `{'channel': 'Hyb-DAPI', 'z': 0}`, with PVCAM frame numbers 1 and 41. The channel names are identical, so only the event order identifies the pass. |
| Cancel stops the pump mid-dispense (D03) | **Recorded; no change on this branch** (needs more extensive testing).<br>- Available command: `Ismatec.stopPump()` sends `I`. It is already sent on every pump disconnect.<br>- Proposed later fix: send stop from `cancel_btn_handler`, plus a safety stop in `runSequence` when a pump step ends by cancel, then test on Elm with water.<br>- Q1 (skip the PBST flush on cancel) still applies. |
| Q4 (logging) | **Keep the extra panel messages** (notification and red warning panels). **No duplicate lines in `log.txt`:** `log.txt` keeps the REF lines, once each. Fix the `%.2f` logging-format traceback on manual Fill. |
| Q5 (AWS missing-folder guard) | **fix** |
| Q6 (start-flag race) | **leave** (not an issue in practice) |
| Q7 (tissue scanner) | same as P15 |
| GA10 / Q8 (pump-speed field) | **fix (deviation from REF):**<br>- Save the value stripped, one line.<br>- Pre-fill the field with the last non-blank value every launch.<br>- Before Prime/Fill/Wash/Start, if the field is empty or not a positive number, prompt the operator and don't start.<br>- The existing "Please confirm the current pump speed" pop-ups stay. |
| Group C, group D | defaults (C keep / small restores; D leave), except D items now covered by Q1/Q2/Q5/Q8 |

---

## Fix status (step 3, 2026-10-05)

| Item(s) | Commit | Notes |
|---|---|---|
| P04, P05, P21 | `3393477` | Elm config and data byte-identical to REF |
| P01 | `77596d4` | |
| P02, Q1, D21, D03 | `17e163e` | Cancel: no PBST flush; pump stopped; all devices released (approved deviation) |
| P03, P06, P07, P16, Q3, H3 | `446773c` | Piezo park 200 µm (approved) |
| P10, P11, P12, P19, Q5 | `e4e112b` | |
| P13 | `c7b3d3f` | |
| P08, P09 | `3aaf605` | |
| P14 | `7865564` | |
| P17, Q2 | `618593f` | |
| P18 | `9587a2b` | Unit test vs the REF if/elif chain |
| P20 | `e1e1f0f` | |
| P15, Q7 | `22e3c3e` | `imwrite` kept (A2) |
| Q4, C03 | `f665043` | |
| GA10, Q8 | `3488ea6` | |
| C02 | `51fce95` | |
| C04, C05, C06, C08, C09 | `cbd3473` | |
| Q6 | not changed | user decision |
| C01, C07, C10, C11, C13 | not changed | keep |
| C12 | partly (`e4e112b` adds zstandard) | rest in the separate hard-coded/packaging session |
| D01 (= Q2) | `618593f` | |
| D02, D04–D20, D22, D23 | not changed | shared bugs, listed only |

Evidence that each fix works was in `docs/dryrun_results/` (checkpoint 3). That folder was deleted on 2026-10-16; the reports remain in git history at commit `9011677` (`git show 9011677:docs/dryrun_results/checkpoint3_summary.md`).

## 1. Group B: regressions to fix (NEW → REF behavior)

Each row will be one commit (or a tight group) in Step 3.

| ID | Sev. | What is wrong in NEW | Effect on a run | Fix (to REF behavior) | Evidence | Decision |
|---|---|---|---|---|---|---|
| **P01** | Critical | Normal end of a fluidics sequence sets only the int flags `cycle_done`/`start_image`. It never sets `cycle_done_event`/`start_image_event`, and both consumers wait only on those events (`system/fluidics_exchange_system.py:384-400`; consumers `automation_controller.py:105`, `panels/fluidics_control_panel.py:86`). | **Automated run hangs after the first fluidics step.** Prime/Wash never do the 4 mL PBST flush. The pump, selector and heater are never disconnected (ports stay open, so the next Start/Prime/Wash fails until restart). The auto buttons stay disabled. | Set both events where the int flags are set (before the `sleep(5)`). Keep the int flags. | F01, GB01, GA07; BR#1, #2 | |
| **P02** | High | Cancel sets `cycle_done=1` but not `cycle_done_event` (`front_end/Widgets.py:721-734`). | Cancel during Prime/Wash leaves the flush thread blocked forever. It also keeps the process alive at exit. | Also set `cycle_done_event` in `cancel_btn_handler`. **Not** `cancelSequence()` as the BR suggests, because that sends a pump stop REF never sends. See Q1. | F02, GB06; BR#4 | |
| **P03** | Critical | No `os.chdir`, but the best-focus image is still saved with a relative name (`system/imaging/focus.py:212-214`). It lands in the launch folder, so `dicfocus<cycle>/` stays empty. | Alignment aborts every cycle after 00. The run then **hangs permanently** in `make_tile` and Cancel can't release it (see Q2). | Save to `pos_path/focus<cycle>/<pos>.tif`. | I01, GB14; BR#3 | |
| **P04** | Critical | `config_file/` holds another microscope's values: selector **COM6/COM5** (Elm: COM11/COM10), heater DAQ **Dev2** (Elm: Dev3), `maxproject_drive` **M:\\** (Elm: D:\\). This PC has no COM5, no Dev2 and no M:. COM6 is a different serial device. | Selector config fails, or it sends valve commands to the wrong device. Heaters can't be created. Max projection fails at `mkdir`. Nothing can run. | Copy REF's `ElveflowMuxDevice_selector.json`, `Heat_stage.json`, `scope.json` (decision 1: carry Elm configs). | F05, F06, I02, GA01-03, N01-03 | |
| **P05** | High | `reagent_sequence_file/Fluidics_sequence_strip.json` ends after the heat wait. | After every strip, hot STRIP buffer stays in the chamber with no PBST wash. | Copy REF's file (adds 2 × 4 mL PBST, source 2). | F07, N05; BR §E | |
| **P06** | High | Focus sweep is ±40 µm, 54 planes (`system/imaging/position_utils.py:29-30`). | Each focus position takes about 35% longer. The search window is wider than validated. It also exposes P07. | Restore ±30 (40 planes). | I04, N11; BR#6 | |
| **P07** | High (latent) | `img.reshape(80, …)` is hard-coded (`focus.py:207`). | `ValueError` whenever the align channel differs from the focus target channel. Focus then never completes. Not triggered with today's all-`Hyb-DAPI` config. | `reshape(-1, …)` as REF does. | I03; BR#5 | |
| **P08** | High | Heater `except` block no longer sets `status[i] = 0` (`device/Heatingstage.py:204-210`). | A stage that heated earlier and then errors still counts as heated, so the run continues as if it had heated. | Restore `self.status[i] = 0` first. | F08; BR#7 | |
| **P09** | Low | Heater `except` logs `name` before resetting the DO line. If the first temperature read fails, `name` is unbound, so it raises **before** `do_task.write(image_mode)`. | That stage is left in heat mode. | Restore REF order: status, DO write, then log. | F09 | |
| **P10** | High | AWS S3 upload is a stub (`panels/status_panel.py:81-83`). | Ticking "upload to AWS" does nothing. | Port REF `upload_aws_handler` (tar+zstd per cycle folder, `aws s3 cp` with `INTELLIGENT_TIERING` + SHA256, 3 retries, delete archive on success). See Q5 about a missing-folder guard. | GB03; BR#8 | |
| **P11** | High | End-of-run uploads ignore the checkboxes. `create_exp_auto` never sets `AWS`/`Local_upload`. It **always** runs `send_to_server` and `send_protocol` (REF has `send_protocol` commented out). The auto checkbox is relabelled "change storage server" (REF: "Send to storage server"). | Every run pushes data and protocol files to the server, whether the box is ticked or not. | Restore REF flag capture, gating, disabled `send_protocol` and the label. | GA04, GA05, GB02; BR#9 | |
| **P12** | Medium | Default server is `jackw-ux1` (REF `10.128.30.152`). | Data and notes go to the wrong host. | Restore REF default. | GA06; BR#12 | |
| **P13** | Medium | Pump set to **1.2** mL/min on connect (REF 1.5) (`device/Pump.py:36`). | Prime, wash, the PBST flush and manual fills deliver about 80% of nominal volume. Automated steps reset it to 1.5, so they are fine. | Restore 1.5. | F04, GA09; BR#11 | |
| **P14** | Medium | Live-view loop adds `and 'imagecycle' in self.app.process_cycle` (`panels/imaging_control_panel.py:216`). `process_cycle` isn't initialized. | Manual imaging in a fresh session: live view thread crashes (`AttributeError`). After a non-imaging step, live view is silently skipped. | Remove the extra condition. | GB04; BR#10 | |
| **P15** | Medium | Tissue-scanner stitching flips every tile 180° and applies CLAHE (`front_end/tissue_scanner.py:311-316`). | Overview looks different. Tile contents are rotated relative to REF, so the operator may click the wrong tiles. See Q7. | Restore REF stitching (keep the `imwrite` fix, A2). | GB20; BR#13 | |
| **P16** | Medium | Focus acquisition details: (a) piezo pre-position uses `piezo_middle_pos` instead of fixed **185** on the primary path; (b) missing `stop_stage_sequence('DA Z Stage')` before the XY move; (c) 2 analysis workers instead of **4**. | Different command order to the piezo, and slower focus analysis. Retry and primary paths now behave differently. | Restore all three. | I05, I06, I07; BR#14 | |
| **P17** | Low | Max-projection cancel path lost `stop_stage_sequence`. | After a cancel the piezo can be left in sequence mode. | Restore. | I08; BR#15 | |
| **P18** | Low | Protocol lookup order changed (`user_defined` first; `rehyb` before non-rehyb). | No effect for any name the recipe builder generates. A hand-edited mixed name would load a different file. | Restore REF order. Keep the explicit `FileNotFoundError` (A3). | F14; BR#16 | |
| **P19** | Low | `except` around `find_protocol` narrowed to `(KeyError, FileNotFoundError, ValueError)` (REF: bare `except`). | e.g. a `PermissionError` copying the protocol kills the automation thread silently. No dialog appears, and devices stay connected. | `except Exception`. | F15, GB08 | |
| **P20** | Low | `save_to_note` catches only `OSError` (REF: bare). | Pressing "Send note" before creating an experiment prints a traceback and shows no GUI message. | `except Exception`. | GB12 | |
| **P21** | Medium | Elm data files differ or are missing. Items marked † are not read by code but matter to operators: tissue-scanner `slide{1,2,3}/slide.pos` and `auto.csv` (another scope's coordinates); chamber-coordinate files† (`slide*_chamber_coor.pos`, `right_corner.pos`, `Chamber_Coordinates_Position_Save/`); gasket folders renamed† (`original_sequence_250um_gasket`, `2IRM_and_2CRM_750um_gasket`) with different strip volumes inside†; `pump_speed_calibration.txt` 1.3 vs 1.58 (see note); stray `slide1/slide.pos~`. | The tissue scanner drives the stage to another microscope's slide corners. The operator library differs. | Copy REF's `device/tissue_scanner/**`, `reagent_sequence_file/**` and `pump_speed_calibration.txt`. Delete `slide.pos~`. | GB24, N06-N10, F12 | |

**Note on P21 (calibration file), corrected after review.** The value in the pump-speed field **does** set the pump run time, in both trees:
1. Prime/Fill/Wash/Start do `fluidics.pumprate = float(field)`.
2. Each step then runs the pump for `vol / pumprate` minutes, while the pump's nominal flow rate stays fixed at 1.5 (P13). So a higher measured rate means a shorter run.

What is broken is only how the *file* pre-fills the field:
- Start saves `field + "\n"`, and the field often already ends in a newline, so the file alternates between `1.58\r\n\r\n` and a single line.
- `readlines()[-1]` then gives a blank default on alternate launches (GA10). Currently the file gives `['1.58\n', '\n']`, so it opens blank.
- On the other launches the file value *is* the default. So the file value matters whenever it loads, and N04's 21% figure applies in those sessions.

The file now holds Elm's 1.58 (commit `3393477`). For the fix, see GA10/Q8 in "Review decisions".

---

## 2. Group A: NEW fixes a real REF bug (keep, after review)

| ID | REF bug | NEW behavior | Note | Evidence | Decision |
|---|---|---|---|---|---|
| **A1** | `self.fluidics.Heatingdevice.cancel==1` (`Widgets.py:1078`) is a comparison, so **Cancel never stops the heaters**. | `= 1`. Cancel stops heating within 5-10 s. | This deliberately changes behavior. A side effect in NEW: cancelled stages still log "done with heat successfully". Optional tidy-up: don't log success when cancelled. | F10, GB05 | |
| **A2** | `tiff.imsave` (`tissue_scanner.py:260`). Elm's env has tifffile 2025.2.18 (installed 2025-03-12), which **has no `imsave`**, so REF's scanner stitching raises on this PC today. | `tiff.imwrite`. | | GB21, N15 | |
| **A3** | Unknown protocol name → `UnboundLocalError` later. | Clear `FileNotFoundError` immediately. | Keep, together with the P19 catch widening. | F15 | |
| **A4** | `recipe_builder.py` `def __int__` typo. | `__init__`. | No visible effect. | GB22 | |
| **A5** | AWS password field is pre-filled with a **plaintext credential**. | Blank. The AWS CLI's own credentials are used, as REF effectively does. | **Rotate that credential.** | GA13 | |
| **A6** | `os.chdir` left the working directory inside `pos_path/dicfocus<cycle>` after alignment. After a manual Step 2 or a mid-cycle cancel, REF's relative paths (`config_file/`, `reagent_sequence_file/`, `device/tissue_scanner/`) break. | No `chdir` anywhere, so relative paths always work. | Requires P03 to be fixed. | GB11, N14 | |

---

## 3. Decisions needed (?)

| ID | Question | Background | My recommendation | Decision |
|---|---|---|---|---|
| **Q1** | Cancel during Prime/Wash: should it still pump the 4 mL PBST flush? | REF: Cancel sets `cycle_done=1`, which wakes the flush thread, so it **still pumps 4 mL PBST after you cancel**. Exact parity (P02) reproduces this. | Parity: keep REF behavior. A deviation (skip the flush on cancel) is a one-line check if you prefer it. | |
| **Q2** | Fix the shared Cancel hang in `make_tile` / `image_and_maxprojection`? | Both wait loops (`tiling.py:48-51`, `max_projection.py:54-58`; REF `:841-844`, `:955-958`) never check `cancel_process`. A Cancel during focus/alignment, or any alignment abort, hangs the run forever in **both** trees. After P03 it's rare again, as in REF. | Fix it (add a cancel check to both loops). This is a small deviation from REF, but Cancel then actually works. | |
| **Q3** | Focus sweeps the same channel twice when align = target channel (Elm config: all `Hyb-DAPI`)? | `focus_channel = [align, target]` builds events for both. Checked on real data: `E:\20260928_Dennis_STARmap_Test3\focus*\Pos0_1\Pos0_NDTiffStack.tif` has **80 frames = 40 planes × 2**. So focus takes 2× the time. If the sharpest frame is in the 2nd pass, `piezo_event_pos[argmax]` raises `IndexError`. In that run, all 192 focus positions (48 × 4 cycles) succeeded. | Leave as is for parity (it works in practice). Revisit later as an optimization: it halves focus time. | |
| **Q4** | Should `log.txt` and the GUI panels match REF exactly? | NEW's logging writes **every fluidics line twice** to `pos_path/log.txt` (a second, timestamped copy). It also shows extra INFO lines in the notification panel and WARNING/ERROR in the red warning panel. Every manual Fill prints a "--- Logging error ---" traceback to the console. | Make `log.txt` identical to REF (drop the duplicate file handler). Keep console logging. Remove the extra GUI-panel messages for parity. Fix the logging-format bug. | |
| **Q5** | Add a guard to the ported AWS upload? | REF `upload_aws_handler` calls `os.listdir` on the max-projection folder without checking that it exists. With AWS ticked and no folder, the end of the run crashes and the buttons stay disabled. | Add an `isdir` guard. It is a tiny deviation and only changes a crash into a log message. | |
| **Q6** | Fix the latent start-flag race? | Both trees read `start_image` right after starting the fluidics thread, while it may still be 1 from the previous step. It is harmless in practice, but becomes slightly more likely once P01 sets events. | Fix it with P01: clear the flag/event before `t.start()`. That is a harmless deviation. | |
| **Q7** | Is the tissue scanner used on Elm, and is REF's orientation right? | P15 restores REF stitching. But A2 shows REF's stitching can't currently finish on this PC (tifffile has no `imsave`), so REF's orientation may not have been checked with the current camera recently. | Restore REF (P15), and verify on Elm in Step 4. | |
| **Q8** | Fix the calibration-file readback (both trees)? | The field always opens empty (see the P21 note), so the operator must type the speed every session. If they forget, `float()` raises. | Leave it for parity unless you want the field pre-filled. Fixing it changes operator workflow: a stale value could then be accepted without thinking. | |

---

## 4. Group D: bugs in both trees (listed, not fixed unless you say so)

| ID | Bug (both trees) | Evidence | Decision |
|---|---|---|---|
| D01 | Wait loops in `make_tile`/`image_and_maxprojection` ignore Cancel, so the run hangs (see **Q2**). | I13, GB14 | |
| D02 | Failed heat step (`heat_status==0`) logs "Heater is wrong" and returns without signalling. The run waits forever, and later `startSequence` refuses ("still running"). | F11 | |
| D03 | Cancel never stops the pump. The current dispense runs to the end of its timer. `FluidicSystem.cancel` is dead code. | F21 | |
| D04 | Selector address 22 maps to selector 1 port 11 (wrong reagent). There is no effect with 16 reagents. | F22 | |
| D05 | Ismatec `flowTime` outside (0, 59940) leaves `flowTimeNow` unbound. Unreachable today. | F23 | |
| D06 | Heater config range error names the wrong stage (stale loop index). | F24 | |
| D07 | Start-flag race after `t.start()` (see **Q6**). | F03, GB17 | |
| D08 | Calibration file blank last line, so the pump-speed field opens empty (see **Q8**). | F12, GA10 | |
| D09 | Manual-tab "Fill experiment detail" calls the auto handler. | GA19 | |
| D10 | Using Device configuration before Create Experiment fails silently, or writes `temp.txt`/`log.txt` into `C:\`. | GA20 | |
| D11 | Manual-fill wait uses a hard-coded 1.5 mL/min, not the calibration. Large fills could be cut off if the calibration is below 1.5. | GA21 | |
| D12 | `clear_focus_canvas`/`clear_tile_canvas` draw into the alignment figure. Cosmetic. | GA22 | |
| D13 | Pixel-size field and "change pixel size" are never read. `scope.json` is used instead. | GA23 | |
| D14 | `scp`/`ssh` return codes ignored: failed uploads and notes are reported as success. `scp -r` into an existing directory nests it on the server. | GB13, I17 | |
| D15 | `check_file` is never reset, so a stale pass lets a run start with missing cycle00 files. | GB15 | |
| D16 | `check_storage` is never called, and it has a filename typo (`pre_adjust_pos.pos`). There is no disk-space check before runs. | GB16 | |
| D17 | Mock-alignment `x_offset` has the wrong shape (plot/debug CSV only). | I15 | |
| D18 | `scope_constant` lacks `scope_*` attributes, so `AttributeError` if `piezo != 1`. Elm has `piezo: 1`. | I16 | |
| D19 | Max-projection semaphore never acquired, so threads are unbounded (memory pressure if projection lags). | I18 | |
| D20 | A second acquisition failure kills the max-projection thread, and the run waits until Cancel. Also: `~bool` in `Assign_image_channel` (no effect). | I19, I20 | |
| D21 | **Cancel in an automated run never disconnects the devices.** Afterwards, COM9/COM10/COM11 stay open and the Dev3 heater channels stay reserved. Pressing Start again then fails in `connect_selector` with `SerialException ... COM11: Access is denied`, so the operator must restart the program. The pump itself reconnects, because its old object is garbage-collected. Shown by the dry run `cancel_restart` in both trees, 2026-10-05. Fix together with the deferred Cancel/pump-stop work, because `disconnect_pump` sends the pump stop. | `docs/dryrun_results/checkpoint2_summary.md` (deleted 2026-10-16; in git history at `23559b8`) | |
| D22 | The live-view thread reads `scope.maxprojection_name` every 5 s. If the next step replaces `scope` before the thread sees `'end'`, it loops forever and keeps the program alive at exit. Seen in the dry run (100× speed); unlikely at real speed. | dry run `auto_full` | |
| D23 | Cancel during focus with "Skip alignment": the mock alignment then reads a missing `offset<cycle>.csv`, so the automation thread ends with `FileNotFoundError` (no hang, no device effect). | dry run `cancel_focus` | |

---

## 5. Group C: neutral differences (keep NEW unless noted)

| ID | Difference | Proposed | Evidence | Decision |
|---|---|---|---|---|
| C01 | Bundled `code/supplementary/package` is put first on `sys.path`. Checked: the bundled pycromanager is byte-identical to the env's 0.29.9 apart from two `sys.path` lines. The bundled ndtiff is identical to the env's: the env's "3.1.0" label is stale and its files are 2.2.1. `all_site_packages` is never imported. | Keep (no behavior difference). | N13 | |
| C02 | `select_chamber`/`select_bypass` calls removed from prime, wash, fill and every automation step. `relay_group=1` is set on every device config. The relay driver is a `pass` stub in both trees, so this has no hardware effect. | Restore the calls for exact parity (cheap, keeps relay support possible). | GA11, GA12, GB07 | |
| C03 | Logging framework adds `log.txt` duplicates and extra GUI-panel text (see **Q4**). | Per Q4. | F18, GA14, GA15, N12 | |
| C04 | REF's process-wide `warnings.filterwarnings("ignore")` was dropped, so warnings now appear on the console. | Restore for parity. | I10 | |
| C05 | `aixintest.csv` (alignment debug) is written to the launch folder instead of `pos_path/dicfocus<cycle>/`. | Write it to REF's location. | I09, GB10, N14 | |
| C06 | `write_log` catches only `OSError`, not everything as in REF. Not reachable in normal flows. | `except Exception` for parity. | F19, GA18, GB19 | |
| C07 | Small GUI/log text changes (protocol-load message, exception text appended to errors, live-view print, `pump_speed:` print removed). | Keep. | F16, F17, I11, GB18 | |
| C08 | `max_projection.live_view` calls `draw_liveview` without importing it. Never called in either tree. | Add the import. | I12 | |
| C09 | Ismatec driver prints `dispenseRate` (wrong unit in hours; division by zero is unreachable). Serial traffic is identical. | Drop the print. | F13; BR#17 | |
| C10 | `device/__init__.py` eagerly imports all device modules. No effect. | Keep. | F20 | |
| C11 | `experiment_profile` path join without `E:\\`. Identical for absolute paths. | Keep. | GA17 | |
| C12 | Packaging manifests are incomplete: `zstandard`, pyzmq, dask etc. missing; `pyproject.toml` has an invalid build backend and entry point. No effect on Elm, which uses its existing env. | Fix later (not parity). | N16; BR#18 | |
| C13 | Unused REF S3 checksum helpers and an old commented-out handler were dropped. | Keep dropped. | GB25 | |

---

## 6. Corrections to the earlier bug report

- **§E "config_file is byte-identical"** is true for the `_production` folder only. NEW (upstream `main`) has another rig's values. This is P04, and it was the most important miss.
- **#3:** the effect is worse than "alignment fails": the run **hangs** in `make_tile` and Cancel can't recover (P03 + Q2).
- **#4:** don't fix it with `cancelSequence()`. That sends a pump stop REF never sends, and it raises if the pump is disconnected (P02).
- **#11:** the 1.2 mL/min also affects prime, wash, the PBST flush and manual fills (about 80% volume).
- **#16:** "mutually exclusive" holds only within one protocol family. There is no effect for generated names.
- **§E calibration:** the file value is used only on launches where it pre-fills the field. Because of the blank-line bug (GA10), that is every other launch. The value typed in the field always sets the pump run time (P21 note).
- **§E `template.pos`:** differs only in line endings.
- **Bundled packages:** identical in behavior to the env (C01).

## 7. Coverage

Each reviewer file ends with a coverage table that lists **every REF function, method, class and data file** in its area, with its NEW counterpart and a verdict. All REF functions in `front_end/`, `system/`, `device/`, `driver/` and `mainwindow.py`, plus all `config_file/`, `reagent_sequence_file/` and `device/tissue_scanner/` data, are covered. Every constant moved to `constants.py` was checked against the REF literal: all 26 match, and 5 are unused. Nothing REF does is missing from NEW apart from the rows above.
