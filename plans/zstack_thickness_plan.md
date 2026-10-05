# Plan: configurable z-stack thickness

**Status:** being implemented on branch `variable_stack_height`.
**Written:** 2026-10-05. **Updated:** 2026-10-05 for `reference-parity`.
**Applies to:** branch `variable_stack_height`, which starts from `reference-parity` at `9011677` (the bug fixes are already in). Line numbers in "Current code that this changes" refer to `9011677`.
**Will be tested on:** Elm.

## Goal

1. A JSON setting sets the z-stack thickness. The GUI asks you to confirm it when an automated run starts.
2. The focus sweep range follows from the thickness, and every calculation that depends on it, including how focus stacks are split, is updated to match.
3. Optional max projections on sub-stacks, each saved as its own max-projection image.
4. The disk-space check at the start of a run accounts for all of the above.
5. A new autofocus method for thick sections.

## Agreed decisions

| Topic | Decision |
|---|---|
| Where the settings live | New keys in `config_file/scope.json`. A missing key falls back to a default that reproduces the current behavior, so older configs (Elm, Alder) keep working. |
| Focus sweep range | `R = min(max(1.2·T, T + 30), 300)` µm, where T is the z-stack thickness. 300 µm is the cap for very thick sections. |
| Focus step | 1.5 µm (current). 3 µm when T ≥ 50 µm. |
| Focus passes | Always acquire an align pass and a target pass, even when both use the same channel. |
| Raw focus stacks | **Keep them.** Never delete them. |
| Raw tile stacks | Keep the current behavior: the cycle's raw folder is deleted after all its projections are verified. No early per-tile deletion. |
| "Extreme focus change" threshold | Becomes a fraction of R. The default fraction is 1/3, which gives 20 µm at the default R of 60 µm, the same as today. |
| Autofocus | Build a `band_center` method. The default stays `peak` (the current method) until it is validated. After that, plan to use `band_center` automatically for T ≥ 50 µm. |
| Sub-stack on/off | Stacks of 30 µm or less are projected as one image, exactly as today. Splitting starts only above 30 µm. |
| Sub-stack size | Fixed 30 µm groups, rounded to a whole number of planes: 20 planes at a 1.5 µm step, the same depth as today's single projection. Every group starts on the same fixed spacing. |
| Leftover planes at the end | If the leftover is half a group or less, add it to the last full group. If it is more than half a group, it becomes its own, shorter group. As a result, stacks up to 45 µm still give one projection. |
| Sub-stack file names | `MAX_<pos>_z00.tif`, `_z01`, and so on, in the same cycle folder, used only when there are 2 or more groups. A single group keeps today's name, `MAX_<pos>.tif`. The pipeline will be adapted to read them. |
| Bug-report fixes | Done on `reference-parity`, which this branch builds on. See the "Overlap with bug fixes" section. |
| Testing | Unit tests offline, then directly on Elm. No `MMConfig_demo.cfg` run, because its channel names differ. |

## Open questions

None at the moment.

## Current code that this changes

| Location | What it does now | Problem |
|---|---|---|
| `system/imaging/position_utils.py:20-45` (`scope_constant`) | Hard-coded focus sweep ±30 µm (40 planes; `reference-parity` P06), max-projection stack −15 to +15 µm (20 planes), step 1.5 µm | Not configurable |
| `system/imaging/imaging_system.py:88-97` | Computes `stack_num_focus` and `stack_num_maxpro` from those constants. The `piezo == 0` branch uses constants that are commented out, so it raises `AttributeError`. | Must come from the new settings |
| `system/imaging/focus.py:67-109` | Builds the focus events with `np.arange`: channels in the outer loop, planes in the inner loop, centered on `piezo[0]` from the cycle CSV. Both passes get the same axes when the channels match. | Range and step must come from the settings |
| `system/imaging/focus.py:196-230` | Reads the whole `<pos>_NDTiffStack.tif` with `tifffile.imread`. Two passes (2N frames) → sharpness on pass 2, saved image from pass 1 (P07). Same channel → NDTiff keeps only pass 2, which is used for both. Crop `[800:2400]` is hard-coded. | Only the first file of a split stack is read; the whole stack is loaded into memory; crop ignores `imwidth` |
| `system/imaging/focus.py:349`, `front_end/panels/imaging_control_panel.py:154-155` | 20 µm extreme-change threshold, hard-coded in two places | Must be a fraction of R |
| `system/imaging/max_projection.py:101-126, 166-167` | Sets the channels per round and builds max-projection events from `scope_constant` | Range must come from the settings |
| `system/imaging/max_projection.py:302-322` | Reads the whole stack with `skimage.io.imread`. Max over all planes for each channel. DIC uses plane 9. Writes one `MAX_<pos>.tif` | No sub-stacks; DIC index is hard-coded; memory grows with N |
| `system/imaging/max_projection.py:265-269, 300` | `thread_limiter.release()` is called but `acquire()` never is | No limit on concurrent threads |
| `system/imaging/max_projection.py:376-404` | Expects one file per tile | Must expect one file per tile per group |
| `front_end/panels/imaging_control_panel.py:212-245` | Live view reads `scope.maxprojection_name` | Must show one group |
| `front_end/automation_controller.py:213-247` (`check_storage`) | Allows 102,400,920 bytes per tile per round (5 channels). Ignores raw and focus stacks. Its fallback file name is misspelled (`pre_adjust_pos.pos`). | **Never called** (only wrapped by `Widgets.py:707`), here or in the reference copy |
| `front_end/panels/fluidics_control_panel.py:265-282` (`start_btn_check`) | A second `tk.Tk()` popup that only confirms the pump speed | Needs the z-stack confirmation and the disk check |
| `front_end/panels/workspace_panel.py:95-97, 171-173` | `scope.json` is loaded only when "Create experiment" is pressed | Edits to the JSON don't take effect until then |

Hardware facts (from `C:\Program Files\Micro-Manager-2.0\MMConfig_Ti2E-xc2.cfg`):
- Piezo (`DA Z Stage`) travel is 0–400 µm, with a start position of 200 µm.
- The camera is 3200 × 3200 × 16-bit, so one frame is 20.48 MB.
- Micro-Manager starts a new stack file at about 4 GB, roughly 209 frames.

## Settings (new keys in `scope.json`)

| Key | Default | Meaning |
|---|---|---|
| `z_stack_thickness_um` | 30 | T, the thickness of the imaging stack |
| `z_step_um` | 1.5 | Step between imaging planes |
| `focus_step_um` | 1.5 | Focus step for thin sections |
| `focus_step_thick_um` | 3 | Focus step when T ≥ `thick_section_um` |
| `thick_section_um` | 50 | Thickness at which a section counts as thick |
| `focus_range_cap_um` | 300 | Upper limit on R |
| `focus_method` | `"peak"` | `"peak"`, `"band_center"`, or `"auto"` (`band_center` when T ≥ `thick_section_um`, otherwise `peak`) |
| `focus_extreme_change_frac` | 0.3333 | Threshold = fraction × R |
| `band_center_frac` | 0.5 | Threshold used by `band_center` (Phase 3) |
| `maxproj_split_above_um` | 30 | On/off switch: split into groups only when T is greater than this |
| `maxproj_substack_um` | 30 | Group size in µm; planes per group = `round(substack_um / z_step_um)` |
| `storage_margin` | 1.10 | Safety factor on the disk estimate |

Derived values:
- `N = round(T / z_step)` imaging planes, at positions `middle − T/2 + i·step`. At the defaults this gives exactly today's −15 to +13.5 µm.
- `R = min(max(1.2·T, T + 30), cap)`.
- `N_f = round(R / focus_step)` focus planes, at `middle − R/2 + i·focus_step`.
- `n_sub = round(maxproj_substack_um / z_step)`, which is 20 planes at the defaults.
- Groups:
  - If `T ≤ split_above`: one group of all N planes.
  - Otherwise, write `N = q·n_sub + r`:
    - Start with q full groups of `n_sub` planes.
    - If `r > n_sub / 2`, add the leftover as its own group.
    - If `0 < r ≤ n_sub / 2`, add it to the last full group, which gets `n_sub + r` planes.
    - If `q = 0`, there is one group.
  - K is the number of groups. Every group starts at a multiple of `n_sub`, so the z spacing between group starts is always `n_sub · z_step` (30 µm at the defaults).
  - Because of the leftover rule, anything up to 45 µm (30 planes) is still one group. It is saved as one `MAX_<pos>.tif` and listed in the sub-stack CSV. Splitting first happens at 46 µm (31 planes, groups 20/11).

Checks:
- The focus sweep and the imaging stack must both fit inside the piezo travel, which is read from Micro-Manager (`Stage Low/High Position(um)`). If either doesn't fit, the confirmation window shows a warning.
- Warn when the cap leaves less than 30 µm of margin (T > 270 µm). Reject T > 300 µm, where the stack would be thicker than the focus sweep.

### Worked examples

Assumes a 1.5 µm imaging step. "Hyb" means a hyb round with 6 channels. Data sizes are per tile or per focus position, per round.

| T (µm) | N | R (µm) | Focus step | N_f | Groups (planes each) | Extreme threshold (µm) | Raw focus stack per position | Raw hyb stack per tile | Hyb output per tile |
|---|---|---|---|---|---|---|---|---|---|
| **30 (default)** | 20 | 60 | 1.5 | 40 | 1 (20) | 20 | 1.6 GB | 2.5 GB | 123 MB |
| 40 | 27 | 70 | 1.5 | 47 | 1 (27; leftover 7 added) | 23 | 1.9 GB | 3.3 GB | 123 MB |
| 45 | 30 | 75 | 1.5 | 50 | 1 (30; leftover 10 added) | 25 | 2.0 GB | 3.7 GB | 123 MB |
| 46 | 31 | 76 | 1.5 | 51 | 2 (20/11) | 25 | 2.1 GB | 3.8 GB | 246 MB |
| 50 | 33 | 80 | 3 | 27 | 2 (20/13) | 27 | 1.1 GB | 4.1 GB | 246 MB |
| 60 | 40 | 90 | 3 | 30 | 2 (20/20) | 30 | 1.2 GB | 4.9 GB | 246 MB |
| 70 | 47 | 100 | 3 | 33 | 2 (20/27; leftover 7 added) | 33 | 1.4 GB | 5.8 GB | 246 MB |
| 100 | 67 | 130 | 3 | 43 | 3 (20/20/27; leftover 7 added) | 43 | 1.8 GB | 8.2 GB | 369 MB |
| 150 | 100 | 180 | 3 | 60 | 5 (20×5) | 60 | 2.5 GB | 12.3 GB | 614 MB |
| 250 | 167 | 300 | 3 | 100 | 8 (20×7/27) | 100 | 4.1 GB | 20.5 GB | 983 MB |
| 300 | 200 | 300 | 3 | 100 | 10 (20×10) | 100 | 4.1 GB | 24.6 GB | 1.2 GB |

Notes:
- At the defaults, the focus sweep is 60 µm, the same as `reference-parity` and the reference copy (`main` uses 80 µm).
- In the leftover rule, "half a group" is 10 planes (15 µm) at the defaults: a leftover of 10 or fewer planes is added to the last full group, and 11 or more becomes its own group.
- Raw hyb stacks are split into several files from about T = 55 µm. With these settings the focus stack stays at 200 frames or fewer, so it fits in one file, but the reader handles split files either way.

## Phases

### Phase 1 – Settings module (no behavior change at the defaults)
- Add `system/imaging/zstack_settings.py`. It holds a frozen dataclass built from `scope_cfg[0]` with the defaults above, plus `imaging_planes()`, `focus_planes()`, `substack_groups()`, `focus_method_for(T)`, `extreme_threshold()` and `validate(piezo_limits)`.
- This one module is used by focus, max projection, the disk check and the GUI.
- `ImagingSystem.__init__` builds it. `stack_num_focus` and `stack_num_maxpro` come from it. The `scope_constant` range attributes are retired (the tissue scanner keeps its own constants and is not changed).
- Add the new keys to `config_file/scope.json` and `docs/config_files.md`.

### Phase 2 – Focus acquisition and reading the stack
- Build the events from the settings: an align pass, then a target pass, each with N_f planes.
  - Each pass gets its own extra axis, `focus_pass` = 0 (align) or 1 (target). The `channel` axis keeps the real channel name, so the data still reads naturally in Micro-Manager. Without the extra axis, two passes on the same channel get identical labels and NDTiff keeps only the second.
- Read stacks with a small NDTiff index reader in this repo (`system/imaging/ndtiff_stack.py`), one plane at a time. The sharpness crop is the centre half of the frame, from `imwidth` (`[800:2400]` at 3200).
  - This handles stacks split across several files and never loads the whole stack into memory.
  - Not `ndtiff.Dataset`: the reader only needs the index format (same layout as bundled ndtiff 2.2.1), and the dry-run harness refuses to import the real `ndtiff`.
- Sharpness is computed on the target pass. The saved alignment image comes from the align pass at the chosen plane.
  - This changes today's behavior when both channels are the same: `reference-parity` uses the second pass for both, because NDTiff collapsed the two passes.
- Keep the raw focus stacks after focusing. (`clean_space` still clears a cycle's old stacks when that same cycle is focused again, so the reader never picks up a stale `<pos>_1`.) Also write a per-cycle `focus<cycle>/sharpness_<pos>.csv` with plane, piezo position and sharpness. It is needed to tune Phase 3 later.
- The extreme-change threshold is fraction × R, used in both `focus.py` and the focus plot.
- `save_offset_and_json` needs no change: its 1.5 factors cancel, so it works for any step.

### Phase 3 – `band_center` autofocus
- Today's method uses the sharpest plane. In thick tissue many planes look equally sharp, and the wide sweep adds false peaks from glass and debris. The sharpest plane is often not the middle of the tissue.
- The `band_center` method:
  1. Smooth the sharpness curve (moving median over about 3 planes).
  2. Baseline = 10th percentile of the curve.
  3. Threshold = baseline + `band_center_frac` × (peak − baseline).
  4. Take the run of planes above the threshold that contains the peak.
  5. Use the middle of that run as the focus plane.
- Log the band width as the estimated tissue thickness. Warn if it is wider than T (tissue thicker than the stack) or touches either end of the sweep (focus may lie outside the sweep). Both set `focus_bad`.
- The alignment image must be chosen the same way for cycle00 and later cycles. Switching methods mid-experiment needs a new cycle00 focus.
- The default stays `peak`. Validate offline against the saved sharpness CSVs from Elm runs, then switch the default to `auto`, which uses `band_center` when T ≥ 50 µm.

### Phase 4 – Sub-stack max projections
- Acquisition is unchanged: one stack per tile of C channels × N planes. Groups are made after acquisition.
- The groups follow the rule under "Derived values": fixed 30 µm groups, and a leftover of half a group or less is added to the last group.
  - Channels other than DIC: max over the group's planes.
  - DIC: the middle plane of the group (replaces the hard-coded 9).
- Output file names:
  - K = 1: `MAX_<pos>.tif`, the same as today.
  - K > 1: `MAX_<pos>_z00.tif` … `_z{K−1}.tif`. Each file is channels × height × width, the same format as today. `z00` is the lowest piezo position.
- Write `<cycle>_substacks.csv` next to the projections, listing each group's index, first and last plane, piezo start and end (µm) and number of planes, so the pipeline can map `_zNN` to depth. It is written only when splitting is on (T > `maxproj_split_above_um`), so the output at the defaults is exactly today's.
- Stream planes through the NDTiff reader, one group at a time. Memory per worker is then about C frames, whatever T is.
- Fix the thread limit: call `acquire()` before starting each worker. The limit stays 10: with streaming, a worker holds about 6 × 20 MB, so 10 workers fit in memory at any T.
- `check_transfer_complete` expects tiles × K files. Live view shows the middle group.

### Phase 5 – Disk check and confirmation window
- Rewrite `check_storage` using `zstack_settings`. Count image rounds from `process_ls`, and get each round's channel count (4, 5 or 6) from the same rule as `Assign_image_channel`, moved into a shared helper. Tiles come from `single_createtiles` on the cycle00 positions, as today. F = number of focus positions (`sum(slice_per_slide) × 4`). B = `imwidth² × 2` bytes.
  - Projections (max-projection drive, permanent): Σ over rounds of tiles × C × K × B.
  - Raw tile stacks (work-folder drive, deleted at the end of each cycle): peak = max over rounds of tiles × C × N × B.
  - Raw focus stacks (work-folder drive, **permanent**): Σ over focus rounds (image rounds + `imagecycle00`) of F × 2 × N_f × B.
  - If both folders are on the same drive, the totals are added. The sum is multiplied by `storage_margin` and compared with `shutil.disk_usage`.
  - Fix the `pre_adjust_pos.pos` typo.
- `start_btn_check`:
  - Re-read `scope.json`.
  - Extend the popup to show the pump speed, T and N, R, N_f, the focus step and piezo window, the focus method, the sub-stack groups, and space needed vs. free for each drive, with a pass/fail result.
  - The z-stack lines are shown only if the protocol has image rounds.
  - Confirm is blocked when a check fails, unless an override is ticked.
  - Use `tk.Toplevel` instead of a second `tk.Tk()`.
- Log the settings in effect to `log.txt`, and write them to `zstack_settings_used.json` in the work folder (it is uploaded with the protocol files).

### Phase 6 – Testing
- Offline unit tests:
  - Plane positions at the defaults are identical to today's arrays.
  - The worked-example table above.
  - Group boundaries.
  - The disk estimate.
  - `band_center` on synthetic curves.
- Dry-run harness (`dryrun/`, from `reference-parity`): every existing scenario on `ref` and `branch`, plus thick-stack scenarios (`imaging_thick_46`, `imaging_thick_100`) on `branch`. At the defaults the acquisition events must match the reference.
- On Elm:
  1. Default settings: the focus offsets, `dicfocus` images and `MAX_` files should match a run on `reference-parity` (the sweep is 60 µm in both). When the align and target channels are the same, the `dicfocus` images now come from the first pass (intended).
  2. A thick stack: check that split stack files are read, that the groups and the CSV are written, that the disk estimate matches actual use, and that memory stays bounded.
     - 45 µm gives 1 group (30 planes); the leftover is added. Check the file name has no suffix.
     - 50 µm gives 2 groups (20/13); the leftover becomes its own group.
     - 100 µm gives 3 groups (20/20/27); the leftover is added to the last group.
  3. Validate `band_center` on the saved sharpness CSVs before changing the default.

## Overlap with bug fixes (branch `reference-parity`)

This branch starts from `reference-parity` at `9011677`, so the bug fixes are already in and there is nothing to merge. Keep the fixes intact when editing the same functions.

Relevant items from `BUG_REPORT_vs_reference.md`. That report is not in this repo; it is at `C:\Users\SVC_barseq\Seq_o_matics_2.5_production\BUG_REPORT_vs_reference.md`. The reference copy is `C:\Users\SVC_barseq\Seq_o_matics_2.5\`. Inventory IDs (P..) are from `docs/parity_inventory.md`.

| # | Summary | State on `reference-parity` | Relation to this plan |
|---|---|---|---|
| 1 | Normal fluidics completion never sets `start_image_event`, so automation hangs after the first fluidics step. | Fixed, P01 (`77596d4`) | Automated Elm tests are unblocked. |
| 3 | The best-focus image is saved with a relative path, so the `dicfocus*` folders stay empty and alignment aborts. | Fixed, P03 (`446773c`): saved to `focus<cycle>/` with an absolute path | Phase 2 keeps that path. |
| 5 | Hard-coded `reshape(80, …)`. | Fixed, P07 (`446773c`): split by `len(frames) == 2N` | Replaced by the Phase 2 reader. |
| 6 | Focus sweep ±40 µm vs. ±30 µm in the reference copy. | Fixed, P06 (`446773c`): ±30 µm | The formula for R gives the same 60 µm at the defaults. |
| 14 | Focus acquisition changes (piezo pre-position, missing `stop_stage_sequence`, 4 → 2 worker threads). | Fixed, P16 (`446773c`): `stop_stage_sequence`, 4 workers, piezo park at 200 µm (approved, H3) | Phase 2 keeps all three. |
| 15 | The cancel path in max projection dropped `stop_stage_sequence`. | Fixed, P17 (`618593f`) | Phase 4 keeps it. |

Checked on 2026-10-05 (before the fixes):
- **#1 and #3 are new in the refactor.** Both appear in GitHub commit `dc55b5a` ("Commit to production level", 2026-04-01). Neither is in the reference copy or in the 2024 initial commit.
- **#1:** the reference copy polls the integer flag `start_image` (reference `front_end/Widgets.py:1255-1260`), which `runSequence` sets to 1 at the end of a sequence. The refactor waits on `start_image_event` instead (`automation_controller.py:105`). The end-of-sequence path (`fluidics_exchange_system.py:384-400`) still sets only the integer. The event is set only in `finishSequence()`, which nothing calls.
- **#3:** the reference copy runs `os.chdir(<pos_path>/focus<cycle>)` before saving (reference `image_acquisition_and_analysis_system.py:435`), then saves `pos + ".tif"` (:379-381). The refactor removed every `os.chdir` but kept the relative file name, so the images land in the folder the GUI was launched from. Then:
  - `copy_dic` finds nothing to move.
  - Both `dicfocus` folders have 0 images, so the count check passes.
  - `alignment.py:130-134` aborts with "The number of images is different from slice numbers."
- No stray `Pos*.tif` files are in the launch folders on this PC, so the refactored focus step has probably not been run here. Anyone running the reference code, including Elm, would not see either bug.
