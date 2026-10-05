# Inventory I: Imaging system (REF `system/image_acquisition_and_analysis_system.py` vs NEW `system/imaging/*`)

Method: read REF (1269 lines) in full and all NEW files (`system/image_acquisition_and_analysis_system.py` shim, `system/imaging/{__init__,imaging_system,focus,alignment,tiling,max_projection,position_utils}.py`, `constants.py`, `types_seq.py`). I also ran a normalized line diff (docstrings, comments and whitespace removed, `p.` mapped to `self.`) to make sure no other statement changed. NEW `system/` equals PROD `code/system/` apart from CRLF line endings, so the bug report's PROD line numbers apply to NEW unchanged. Every `scope` attribute that the front end reads (`cycle`, `maxprojection_name`, `slidenum`, `x_offset`, `focus_status`, ...) is still stored on the `ImagingSystem` object, because the managers write through `p = self._parent`.

None of `constants.py`'s imaging constants (`IMAGE_WIDTH_PX=3200`, `TOPHAT_FILTER_SIZE=(10,10)`, `DENOISING_PERCENTILE=85`, ...) is imported by `system/imaging/*`. The imaging code still uses its own literals, and they match REF. `types_seq.ScopeConfig` is type-only.

## 1. Findings table

| ID | Group | Severity | REF location | NEW location | What REF does | What NEW does | Effect on a run | Proposed action | Bug-report # |
|---|---|---|---|---|---|---|---|---|---|
| I01 | B | Critical | REF:system/image_acquisition_and_analysis_system.py:435 (`os.chdir(os.path.join(self.pos_path, "focus" + self.cycle))`), :379-381 (`z_name = pos + ".tif"`; `skimage.io.imsave(z_name, …)`) | NEW:system/imaging/focus.py:251-252 (no chdir), :212-214 (same relative `imsave`) | Changes into `focus<cycle>` before the analysis threads run, so `Pos*.tif` best-focus images land in `focus<cycle>/`. `copy_dic` (:521) then moves them into `dicfocus<cycle>/`. | Never changes the working directory, so `Pos*.tif` is written to the process working directory (the launch dir, normally `code/`) and overwritten every cycle. `copy_dic` (focus.py:335) finds nothing, so `dicfocus<cycle>/` stays empty (including `dicfocuscycle00`). | In every cycle after 00, `do_alignment` reads 0 files from both folders. 0==0 passes the first check, then `len(slidenum) != len(imcurr)` causes "…Abort.", and `alignment_status` stays 0 (alignment.py:130-134). **Correction to the report:** the run does not merely misalign. `make_tile` (tiling.py:48-51) then loops forever on `alignment_status == 0` without checking cancel. The automation thread is inside `image_auto` (automation_controller.py:149), so the run hangs permanently and Cancel cannot release it (see I13). This applies only when "skip alignment" (`mock_align`) is off. | Save to `os.path.join(p.pos_path, "focus"+p.cycle, pos + ".tif")`. | #3 (confirmed, effect is worse: a hang) |
| I02 | B | Critical | REF:config_file/scope.json:15 `"maxproject_drive":"D:\\"` | NEW:config_file/scope.json:15 `"maxproject_drive":"M:\\"` | Max projections go to `D:\<pos_path[3:]>_maxprojection\<cycle>\MAX_*.tif`. `send_to_server` uploads from `D:\…`. | Uses `M:\`. **NEW differs from PROD here** (PROD has `D:\\`), so the report's statement that `config_file/` is byte-identical does not hold for NEW. | On Elm, if there is no `M:` drive, `create_max_projection_folder`'s `os.mkdir(M:\…_maxprojection)` (max_projection.py:93-94) raises inside the max-projection thread. No tile is imaged, `max_projection_status` never becomes 1, and the automation loop waits until Cancel. If `M:` exists (for example a mapped share), every max projection, the live view (imaging_control_panel.py:229) and the server upload source move there. Cross-area note: the same diff also shows `ElveflowMux` COM11/COM10 → COM6/COM5 and heater `DAQ` Dev3 → Dev2. Those belong to the fluidics/heater reviewers. | Restore REF `config_file/*.json` (Elm values). | (new) |
| I03 | B | High (latent) | REF:…:374 `img.reshape(-1, self.imwidth, self.imwidth)` | NEW:system/imaging/focus.py:207 `img.reshape(80, p.imwidth, p.imwidth)` | Works for any plane count. | Hard-coded 80. With the ±40 sweep, `np.arange(m-40, m+40, 1.5)` gives 54 planes, so 2 channels give 108 frames and `ValueError`. | Triggered only when `align_channel` ≠ focus target channel (current scope.json has all `Hyb-DAPI`, so this is latent). When it triggers, every `find_focus_plane` fails and is printed. `save_offset_and_json` then raises `KeyError` and "focus is wrong or cancelled" is shown. `focus_status` is never set and the automation waits forever. | Restore `reshape(-1, …)`. | #5 (confirmed) |
| I04 | B | High | REF:…:112-113 `piezo_focus_start_pos = -30`, `piezo_focus_end_pos = 30` | NEW:system/imaging/position_utils.py:29-30 `-40` / `40` | 40 focus planes (1.5 µm). | 54 planes. `stack_num_focus` becomes round(80/1.5)=53 instead of 40 (unused elsewhere). | Each focus position takes about 35% longer. The search window is wider than REF's validated setting, so it can pick a far-off plane (focus diffs ≥20 µm are flagged at focus.py:338). It also exposes I03. | Restore ±30. | #6 (confirmed) |
| I05 | B | Medium | REF:…:469-470 `piezo_z = 185`; `set_position("DA Z Stage", piezo_z)` (primary path) | NEW:system/imaging/focus.py:284 `p.core.set_position("DA Z Stage", p.piezo_middle_pos)` | Pre-positions the piezo at a fixed 185 µm before each focus stack. | Pre-positions at row 0's `piezo` value from `<cycle>.csv` (set in `calculate_z_stack`, focus.py:74). The retry path (:310) still uses 185, so the two paths now differ. | The piezo starts the sequence from a different place. The event z values are absolute, so this is probably harmless, but the first-frame settle differs from validated REF. | Restore `185`. | #14 (confirmed) |
| I06 | B | Medium | REF:…:455 `self.core.stop_stage_sequence('DA Z Stage')` at the top of the primary `try` | NEW:system/imaging/focus.py:270-273 (missing) | Stops any running piezo sequence before every XY move. | Does not. Only the retry path (:296) stops it. | If the piezo was left in sequence mode (for example by a previous aborted acquisition or a manual MM session), the first attempt can fail. NEW then sleeps 3 s and retries, with 185 pre-position (I05). The result is a different command order to the hardware. | Add the call back. | #14 (confirmed) |
| I07 | B | Low | REF:…:513 `ThreadPoolExecutor(max_workers=4)` | NEW:system/imaging/focus.py:327 `max_workers=2` | 4 parallel `find_focus_plane` workers. | 2. | Sharpness analysis after the focus stacks takes about twice as long. Results are the same. | Restore 4. | #14 (confirmed) |
| I08 | B | Low | REF:…:1062 `self.core.stop_stage_sequence('DA Z Stage')` before `set_position(piezo_middle_pos)` on cancel | NEW:system/imaging/max_projection.py:172-180 (missing) | On cancel, stops the piezo sequence and then moves the piezo. | Only moves it. | After a cancel during imaging, the piezo can stay in sequence mode, and the `set_position` may be ignored or fail. | Add the call back. | #15 (confirmed) |
| I09 | C | Low | REF `os.chdir` calls: :32 (module `get_file_name`, unused), :435, :535, :540 (focus → `focus<cycle>` then `pos_path`), :831 (`scope.get_file_name` leaves the CWD in `dicfocus<cycle>` after `do_alignment`), :1018 (`pos_path/<cycle>` during max projection), :1156 (`system_path`). Also REF:front_end/Widgets.py:1359/1361/1437 `os.chdir(self.system_path)`. | NEW: no `os.chdir` anywhere. `position_utils.get_file_name` uses `os.listdir(path)` (:58-62). | The process CWD moves around during imaging. Besides I01, the only relative-path consumer is the front end's `data.to_csv("aixintest.csv")` (REF Widgets.py:1394). In REF that file lands in `pos_path/dicfocus<cycle>/`, or in `system_path` when alignment is mocked. | `aixintest.csv` always lands in the launch dir (imaging_control_panel.py:181). All other imaging I/O uses absolute paths in both trees (Acquisition directories, max-projection files, CSV/.pos files). | Debug CSV location only. The `.tif` filters ignore it. | Optional: write it to `pos_path`. | (report G mentions only the PROD side) |
| I10 | C | Low | REF:…:18-20 `warnings.filterwarnings("ignore")` at import (affects the whole process) | NEW: absent (no `filterwarnings` anywhere in NEW) | All Python warnings are suppressed program-wide. | Warnings are printed, for example pandas SettingWithCopyWarning in `fix_Posinfo` (tiling.py:169), concat-with-empty FutureWarning, and skimage low-contrast `imsave`. | Console noise only. | Optional: restore it in `system/imaging/__init__.py` or `mainwindow.py`. | – |
| I11 | C | Low | REF:…:536-539 bare `except:` and `"focus is wrong or cancelled"`. :1148-1150 bare `except:` and `update_error("Missing maxprojection")`. | NEW:focus.py:349-350 `except Exception as e` and `f"focus is wrong or cancelled: {e}"`. max_projection.py:264-265 `f"Missing maxprojection: {e}"`. | Fixed GUI error text. | The GUI error text has the exception appended. KeyboardInterrupt/SystemExit are no longer caught (no practical effect). | GUI text only. | None. | #14 (last row) |
| I12 | C | Low (latent) | REF:…:1213-1222 `live_view` calls `draw_liveview`, which comes from `from front_end.logwindow import *` (:21) | NEW:system/imaging/max_projection.py:352-369 calls `draw_liveview`, which is **not imported** (:18-21 imports only 4 names) | Works. | `NameError` if called. | Neither tree calls `scope.live_view`, because the front end has its own live view. No current effect. | Import `draw_liveview`. | – |
| I13 | D | Medium | REF:…:841-844 (`make_tile` waits on `alignment_status`), :955-958 (`image_and_maxprojection` waits on `maketiles_status`) | NEW:tiling.py:48-51, max_projection.py:54-58 (same) | The wait loops never check `cancel_process`. Any alignment abort (image-count mismatch, :593-598/:620-624, or a cancel return at :586-587) leaves `make_tile` sleeping forever, and the automation thread with it. | Same. Because of I01, NEW hits this every non-00 cycle. | A run hangs after any alignment failure. Cancel cannot break it. | Add `and p.cancel_process != 1` to both loops (needs a decision, because REF also lacks it). | – |
| I14 | ? | Medium | REF:…:424/428 `focus_channel = [align_channel] + [target]`. :340-346 builds events for both entries. :370-372 `focusimg = img` when equal. :382 `self.piezo_event_pos[max_index]` | NEW:focus.py:240-245, :96-102, :203-205, :215 (same) | With the Elm config (align = target = `Hyb-DAPI`), the same channel is swept **twice** (2N events with duplicate axes). If the NDTiff stack holds all 2N frames, `argmax` runs over 2N frames while `piezo_event_pos` has N entries. An `argmax ≥ N` then raises `IndexError` for that position, and the run ends in "focus is wrong or cancelled". It probably works only because photobleaching makes the first pass sharper. | Same. | Focus time doubles in both trees. A possible intermittent focus failure. Unclear: it depends on how pycromanager/NDTiff stores duplicate-axis events. Needs a hardware check of the `Pos*_NDTiffStack.tif` page count. | Human decision. If confirmed, dedupe `focus_channel` when both entries are equal. | – |
| I15 | D | Low | REF:…:546-550 (mock_align) `self.x_offset = np.zeros(self.pos_batch_size)` with a list | NEW:alignment.py:56-60 (same) | Builds an N-D array (for example shape (8,8)) instead of length `sum`. `slidenum` is all zeros. | Same. | Only the front-end alignment plot or `aixintest.csv` is wrong (caught by try/except). The `regoffset` files are correct. | Optional: `np.zeros(sum(...))`. | – |
| I16 | D | Low (latent) | REF:…:109-127 `scope_constant` has no `scope_*` attributes, but :272-273 use them when `piezo != 1` | NEW:position_utils.py:20-45 (commented out), imaging_system.py:93-97 | `AttributeError` in `__init__` if `piezo` ≠ 1. | Same. | Elm has `piezo: 1`, so there is no effect. | None. | – |
| I17 | D | Low | REF:…:1202-1210 `send_to_server`: `ssh <server> -vvv mkdir -p /mnt/imagestorage/<pos[3:]>_maxprojection`, then `scp -r <drive><pos[3:]>_maxprojection <server>:/mnt/imagestorage/<pos[3:]>_maxprojection`. :1193-1199 `send_protocol`: `scp <pos_path>\<f> <server>:<same server_path>` | NEW:max_projection.py:319-350: identical command strings (except the drive from I02) | `scp -r` into a directory that already exists nests it (`…_maxprojection/…_maxprojection/<cycle>`). `os.system` return codes are ignored. Backslashes in `pos_path[3:]` pass through to the remote path. | Same. | Server layout is nested in both trees. Upload failures are silent. | None (parity). The caller-side differences are in #9 (front end). | (#9 is caller-side) |
| I18 | D | Low | REF:…:266 `Semaphore(10)`, :1174 `release()` only, never `acquire()`. :1145-1147 one thread per tile | NEW:imaging_system.py:86, max_projection.py:295, :261-263 (same) | The limiter does nothing, so max-projection threads are unbounded. Each thread loads a full tile stack (about 120 frames of 3200² uint16, about 2.4 GB for hyb). | Same. | Memory pressure if projection lags acquisition. | None (parity). | – |
| I19 | D | Low | REF:…:1002-1003 `… and ~('01' in self.cycle)` | NEW:max_projection.py:111-112 (same) | `~bool` is -1/-2, which is always truthy. No practical effect, because the `'01'` case is caught by the first branch. | Same. | None. | None. | – |
| I20 | D | Low | REF:…:1134-1143 a second acquisition failure raises `ValueError("The tile can't be imaged!")` | NEW:max_projection.py:250-259 (same) | The max-projection thread dies. `max_projection_status` stays 0 and automation waits until Cancel. REF also leaves the CWD in `pos_path/<cycle>` (:1156 is skipped). | Same, minus the CWD effect. | Same hang in both trees. | None (parity). | – |

Counts: A 0, B 8 (I01–I08), C 4 (I09–I12), D 7 (I13, I15–I20), ? 1 (I14).

### Status of bug-report items in this area
- **#3** confirmed. Correction: the consequence is a permanent hang in `make_tile`, not only an aborted alignment (I01 + I13). Line refs PROD focus.py:212-214 and REF :381/:435 are correct.
- **#5** confirmed: 54 planes, so 108 frames, and `reshape(80)` raises.
- **#6** confirmed.
- **#14** confirmed in all rows. The "bare except" row refers to the final try at REF:536 (the primary-path catch is `except Exception as e` in both trees).
- **#15** confirmed.
- **#9**: the `send_to_server` and `send_protocol` bodies are identical in both trees (I17). The regression is entirely in the caller.
- **Section E**: "`config_file/` is byte-identical" holds for PROD but **not for NEW** (I02, plus the COM-port and DAQ differences).

## 2. Coverage table (REF scope → NEW)

| REF item (REF line) | NEW counterpart | Verdict |
|---|---|---|
| imports, `from front_end.logwindow import *`, `warnings.filterwarnings` (:6-29) | per-module named imports | I10, I12 |
| module `get_file_name` (:31, chdir) | position_utils.py:48 (no chdir) | same (unused by scope); see I09 |
| `sort_by` (:40) | position_utils.py:65 | same |
| `clean_space` (:46) | position_utils.py:79 | same |
| `single_createtiles` (:50) | position_utils.py:256 (re-exported via shim) | same |
| `scope_constant` (:109) | position_utils.py:20 | I04, I16 (maxpro ±15, step 1.5, sharpen1, pos_per_slice=4, z_dir=1 same) |
| `get_time` (:130) | position_utils.py:85 | same |
| `get_col` / `get_row` (:136/:142) | position_utils.py:92/:99 | same |
| `copy_dic` (:148) | position_utils.py:106 | same (but starved by I01) |
| `ind2sub` (:156) | position_utils.py:121 | same |
| `save_offset_and_json` (:163) | position_utils.py:136 | same |
| `get_pos_data` / `get_position_piezo` / `get_position` (:188/:202/:214) | position_utils.py:177/:200/:222 | same |
| `filterSize`, `kernel`, `color_array`, `hattop_convert`, `denoise` (:224-231) | position_utils.py:242-253 | same |
| `scope.__init__` (:233) | ImagingSystem.__init__ imaging_system.py:42 | same (adds manager objects) |
| `move_to_fluidics` / `move_to_image` (:276/:283) | imaging_system.py:109/:113 | same (no-ops) |
| `check_cycle00` (:290) | imaging_system.py:117 | same |
| `get_pixel` (:311) | imaging_system.py:143 | same |
| `get_sharpness` (:315) | focus.py:42 | same (medianBlur 3, filter2D sharpen1, crop [800:2400, 800:2400] at focus.py:210) |
| `write_log` (:323) | imaging_system.py:148 | same |
| `calculate_z_stack` (:328) | focus.py:62 | same (range via I04) |
| `create_piezo_event` (:336) | focus.py:79 | same (event order: channel-major, then z; exposure from cfg); I14 |
| `calculate_z_stack_without_piezo` / `create_scope_event` (:350/:354) | focus.py:106/:121 | same (unused; `scope_step` undefined in both) |
| `find_focus_plane` (:368) | focus.py:191 | I01, I03, I14 |
| `image_with_piezo` (:388) | focus.py:146 | same (piezo reset to 200; unused by front end) |
| `image_with_scope` (:415) | focus.py:187 | same (pass) |
| `focus_image` (:419) | focus.py:221 | I01, I04, I05, I06, I07, I09, I11 (cancel path, 3 s retry sleep, retry 185, ≥20 µm check, `focus_status` logic same) |
| `do_alignment` (:543) | alignment.py:43 | same logic; I09 (no chdir), I13, I15 |
| `calculate_shift_singlethread` (:629) | alignment.py:139 | same |
| `calculate_shift` (:639) | alignment.py:156 | same (one thread per position, 3 s stagger, join) |
| `update_regoffsetfile` (:670) | alignment.py:193 | same (DevicePositions index 2 with piezo, 1 without) |
| `createBlackmanWindow` (:703) | alignment.py:233 | same |
| `machineEpsilon` (:725) | alignment.py:266 | same |
| `imregcorr` (:732) | alignment.py:283 | same (hard-coded 2048×2048 reshape in both; would fail if DIC images were 3200²; parity) |
| `sanity_check_alignment` (:793) | alignment.py:380 | same (±50 thresholds; status forced to 1) |
| `scope.get_file_name` (:830, chdir) | imaging_system.py:154, which calls position_utils.get_file_name | I09 |
| `make_tile` (:838) | tiling.py:36 | I13 |
| `load_achor_regpos` (:851) | tiling.py:58 | same |
| `count_tiles` (:866) | tiling.py:76 | same |
| `createtiles` (:869) | tiling.py:81 | same |
| `fix_Posinfo` (:930) | tiling.py:149 | same (`tiledregoffset<cycle>.csv`) |
| `image_and_maxprojection` (:952) | max_projection.py:43 | I13 |
| `create_max_projection_folder` (:971) | max_projection.py:70 | same code; I02 (drive) |
| `Assign_image_channel` (:995) | max_projection.py:97 | same; I19 |
| `start_max_imgage_cycle` (:1015) | max_projection.py:124 | I09 (chdir replaced by an unused `p._cycle_dir`) |
| `maxprojection_image_cycle` (:1033) | max_projection.py:143 | I08, I09, I11, I18, I20 (pre-position `piezo_init` from cycle00.csv, stop/wait order, 2 s retry sleep, `Core()` re-create, end `set_position(piezo_middle_pos)`, 3 s sleep, `check_transfer_complete` same) |
| `process_scope_image` (:1165) | max_projection.py:280 | same; I18 |
| `maxprojection` (:1179) | max_projection.py:297 | same (`MAX_<pos>.tif` in `<drive><pos[3:]>_maxprojection\<cycle>\`, np.max over z except DIC plane 9, input dtype kept, `photometric='minisblack'`); I02 |
| `send_protocol` (:1193) | max_projection.py:319 | same; I17 |
| `send_to_server` (:1202) | max_projection.py:333 | same; I17, I02 |
| `live_view` (:1213) | max_projection.py:352 | I12 |
| `check_transfer_complete` (:1224) | max_projection.py:371 | same (`rmtree(pos_path/<cycle>)` on success) |
| `pos_to_csv` (:1244) | imaging_system.py:166 | same |
| shim module namespace (REF exported everything) | NEW shim exports the `system.imaging` `__all__`, `position_utils *` and `scope` | same for the only consumers (named imports of `scope`, `get_pos_data`, `single_createtiles` in automation_controller.py:18 and workspace_panel.py:72/131) |
| config `scope.json` (used by the scope class) | NEW config_file/scope.json | I02 |
| — (no REF counterpart) | `ImagingSystem` delegate methods; `FocusManager`, `AlignmentManager`, `TilingManager`, `MaxProjectionManager` `__init__` | same (pure delegation; state stays on the parent) |
