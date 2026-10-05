# Inventory N: non-code files, cross-cutting constants, runtime environment

Reviewer area: data/config files, `constants.py` / `types_seq.py`, vendored packages and `sys.path`, dependency manifests, and working-directory assumptions.
REF = `C:\Users\SVC_barseq\Seq_o_matics_2.5\`. NEW = `C:\Users\SVC_barseq\Seq_o_matics_github\.claude\worktrees\reference-parity\code\` (clean git worktree at `dc55b5a`).
All file diffs use `diff --strip-trailing-cr`.

**Important correction to the bug report (§E).** It says "`config_file/` is byte-identical in REF and PROD". That is true for PROD (`Seq_o_matics_2.5_production\code\config_file` == REF). It is **false for NEW**: three config files in the NEW worktree hold another microscope's values (N01–N03). NEW's *code* equals PROD, but its data files do not.

Environment facts from this PC (it hosts REF and the `seq_o_matic` conda env). I enumerated these read-only: I listed COM ports with `serial.tools.list_ports` and NI devices with `nidaqmx.system.System.local().devices`, without opening any port or task.
- COM ports present: COM1, COM2, COM4, COM6, COM9, COM10, COM11. COM10 and COM11 are FTDI VID:PID 0403:6015 (SER P201…, the Elveflow MUX pair). COM6 is a different FTDI 0403:6001 device (SER A10MO4KAA). **There is no COM5.**
- NI-DAQ devices: `Dev1` (PCIe-6323) and `Dev3` (USB-6001). **There is no `Dev2`.**
- Drives: C:, D: and E: exist. **There is no M:.**

---

## 1. Findings table

| ID | Group | Severity | REF location | NEW location | What REF does | What NEW does | Effect on a run | Proposed action | Bug-report # |
|---|---|---|---|---|---|---|---|---|---|
| N01 | B | Critical | REF:config_file/Heat_stage.json:1-3 | NEW:config_file/Heat_stage.json:1-3 | `"DAQ":"Dev3"` for all 3 stages. Read by REF:system/fluidics_exchange_system.py:77 and turned into channel names `Dev3/ao0`, `Dev3/port1/line0..2`, `Dev3/ai0,ai1,ai3` (REF:device/Heatingstage.py:25,46,48). | `"DAQ":"Dev2"` for all 3 stages. The same code path builds `Dev2/...` (NEW:device/Heatingstage.py:65,108,110). | This PC has no `Dev2`, so creating the nidaqmx channels raises a DaqError. The heater group cannot be configured, every heat step is impossible, and automation cannot start: it requires all device groups to be configured. | Restore REF's `Heat_stage.json` (Dev3). | — (report wrongly said config identical) |
| N02 | B | Critical | REF:config_file/ElveflowMuxDevice_selector.json:1-2 | NEW:config_file/ElveflowMuxDevice_selector.json:1-2 | `ElveflowMux_1` on `COM11`, `ElveflowMux_2` on `COM10`. Opened by `serial.Serial(port=self.config[0/1]['port'])` (REF:device/Selector.py:23,29). | `COM6` and `COM5`. Same code (NEW:device/Selector.py:51,57). | COM5 does not exist here, so opening selector2 raises `SerialException`. COM6 is a different FTDI device, so selector1 would open it and send it MUX commands, or fail if another program holds it. Selector configuration fails, so no reagent can be routed. | Restore REF's file (COM11/COM10). | — |
| N03 | B | Critical | REF:config_file/scope.json:15 | NEW:config_file/scope.json:15 | `"maxproject_drive":"D:\\"`. Read at REF:system/image_acquisition_and_analysis_system.py:261 and used for the `<drive>\<pos_path[3:]>_maxprojection\<cycle>\` output (`:988-989,1188-1190,1203`) and for `shutil.disk_usage` (REF:front_end/Widgets.py:1181). | `"M:\\"`, used the same way (NEW:system/imaging/imaging_system.py:81; NEW:system/imaging/max_projection.py:93-94,315-317,343; NEW:front_end/automation_controller.py:56,230; NEW:front_end/panels/imaging_control_panel.py:227). | This PC has no M: drive. `os.mkdir("M:\\…_maxprojection")` and `disk_usage("M:\\")` raise `FileNotFoundError`, so max projection fails and no max-projected images are written. If an M: drive is mapped later, images go to a different disk than REF uses. | Restore `D:\\`. | — |
| N04 | B | High | REF:device/pump_speed_calibration.txt:1 | NEW:device/pump_speed_calibration.txt:1 | `1.58`. It is read at startup (REF:front_end/Widgets.py:73-74) into `pump_speed_str`, the default of the pump-speed Entry (`:282`). It is copied to `fluidics.pumprate` on Start/Prime/Wash/Pump (`:879,947,1055,1093`) and written back on Start (`:1052`). | `1.3`. Same flow (NEW:front_end/Widgets.py:118-119,326; NEW:front_end/panels/fluidics_control_panel.py:58,130,202,246-249). | Pump run time is `vol/rate` minutes (REF:device/Pump.py:15), and the sequence timer is `60*vol/pumprate` (NEW:system/fluidics_exchange_system.py:420). On first launch NEW runs every pump step 1.58/1.3 = 1.215× longer, so about 21% more reagent per step than REF delivers on Elm. The value persists, because Start writes it back to the file. | Restore 1.58 (Elm's calibration). | §E (confirmed) |
| N05 | B | High | REF:reagent_sequence_file/Fluidics_sequence_strip.json:1-8 | NEW:reagent_sequence_file/Fluidics_sequence_strip.json:1-6 | 3× (STRIP 8 mL from source 8, 300 s heat wait), then **2× PBST 4 mL from source 2**. Loaded by `find_protocol` for any name containing `strip` (REF:system/fluidics_exchange_system.py:503-514) and copied into `pos_path`. | Ends after the third heat wait; there are no PBST washes. Loaded by NEW:system/fluidics/protocol_loader.py:40 (`"strip" in t`) and copied to `pos_path`. | After stripping, the chamber is left full of STRIP buffer and is not washed with 8 mL PBST before the next hyb/seq. The experiment-folder copy of the protocol also differs. | Restore REF's file. | §E (confirmed) |
| N06 | C | Low | REF:reagent_sequence_file/original_sequence_250um_gasket/, REF:reagent_sequence_file/2IRM_and_2CRM_750um_gasket/ | NEW:reagent_sequence_file/original_sequence/, NEW:reagent_sequence_file/2IRM_and_2CRM/ | Folders are named with their gasket size. `original_sequence_250um_gasket/Fluidics_sequence_strip.json` uses STRIP 8 mL ×3 plus 2× PBST 4 mL, the same as REF's top-level file. All 13 other files are identical. `2IRM…` and `750um gasket/` are identical between trees. | Folders renamed. `original_sequence/Fluidics_sequence_strip.json` uses STRIP **4 mL** ×3 and no PBST. | No code opens these subfolders (grep finds no match in either tree). The only effect is the recipe-builder dropdown: `os.listdir("reagent_sequence_file")` with `[0:-5]` (REF:front_end/recipe_builder.py:22,31; NEW:front_end/recipe_builder.py:31,45). It shows `original_sequence_250um_` / `2IRM_and_2CRM_750um_` in REF and `original_seq` / `2IRM_and_` in NEW. Choosing any folder entry is invalid in both trees. Operators who copy these folder files by hand would get the wrong volumes. | Restore REF names and content so the library matches Elm. | §E (confirmed) |
| N07 | B | Medium | REF:device/tissue_scanner/slide{1,2,3}/slide.pos | NEW:device/tissue_scanner/slide{1,2,3}/slide.pos | Elm's slide-corner Micro-Manager position lists, for example slide1 Z ≈ 3078.5 and XY (45491, 27904), (54639, -7168), … Read by `scan_slide` (REF:front_end/tissue_scanner.py:265) to build the overview tile grid. | Different corner sets: Z ≈ 3094–3212 and completely different XY, for example slide1 (46917.8, -28738.0). Read at NEW:front_end/tissue_scanner.py:328. | The tissue-scanner overview drives the stage to another microscope's slide corners, which gives a wrong or empty overview and possibly a stage move outside Elm's slide area. | Restore REF's files. | §E (confirmed) |
| N08 | B | Low | REF:device/tissue_scanner/slide{1,2,3}/auto.csv | NEW:device/tissue_scanner/slide{1,2,3}/auto.csv | Elm's saved tile picks (16, 32 and 36 rows). Written by `save_coordinates` (REF:front_end/tissue_scanner.py:342) and read by `combine_pos` (`:210`), which writes `<pos_path>/auto.pos`. | Different picks (52, 52 and 48 rows) (NEW:front_end/tissue_scanner.py:247,447). | If an operator clicks "Combine slide edge positions" without first re-scanning, the experiment's `auto.pos` contains non-Elm coordinates. Each new scan overwrites the file. | Restore REF's files. | §E (confirmed) |
| N09 | C | Low | REF:device/tissue_scanner/slide{1,2,3}_chamber_coor.pos, right_corner.pos, Chamber_Coordinates_Position_Save/{Use_This_For_The_Automated_3_Chambers_Platform, Use_This_For_The_Mannual_4_Chambers_Platform}/ | absent | Saved MM position lists that operators load by hand. | Absent. | No code in either tree references them (grep for `chamber_coor`, `right_corner`, `Chamber_Coordinates` finds nothing). Only operator workflow is affected. | Copy them over for parity. | §E (confirmed) |
| N10 | C | Low | absent | NEW:device/tissue_scanner/slide1/slide.pos~ | — | Editor backup, identical to NEW `slide1/slide.pos`. | Not read by code. | Delete it. | §E |
| N11 | B | High | REF:system/image_acquisition_and_analysis_system.py:112-113 (`scope_constant`) | NEW:system/imaging/position_utils.py (`scope_constant`, `piezo_focus_start_pos = -40`, `piezo_focus_end_pos = 40`) | Focus sweep ±30 µm. | ±40 µm. All other members are equal: `piezo_step` 1.5, maxpro ±15, `sharpen1`, `pos_per_slice` 4, `z_dir` 1. | This is the only cross-cutting numeric constant whose value changed. Effects are described in #5/#6. | Restore ±30. | #6 (confirmed) |
| N12 | C | Low | REF writes debug logs only through explicit `open(pos_path/log.txt,'a')` calls (e.g. REF:front_end/Widgets.py:805; REF:system/fluidics_exchange_system.py:116; REF:system/image_acquisition_and_analysis_system.py:324; REF:device/Heatingstage.py:168) | NEW:logging_config.py:113-180; NEW:mainwindow.py:26; NEW:front_end/panels/workspace_panel.py:92-93,169-170 | One writer style; nothing is attached to the `logging` module. | `setup_logging()` attaches a console StreamHandler (INFO+) and a TkHandler (INFO+ to the notification panel, WARNING+ to the red warning panel). After the work path is chosen, `update_log_file` also adds a DEBUG+ FileHandler that keeps `pos_path/log.txt` open, the same file the legacy code appends to. | `log.txt` gains interleaved `YYYY-mm-dd HH:MM:SS [LEVEL] seqomatic.x: …` lines, and the GUI panels show extra messages, with warnings in red. No hardware effect. The TkHandler inserts into Tk widgets from worker threads, like REF's `add_*` helpers already do. | Keep. Check that no new WARNING text alarms operators. | §F note |
| N13 | C | Low | REF imports `pycromanager` from the env: REF:front_end/tissue_scanner.py:9,12; REF:system/image_acquisition_and_analysis_system.py:11,16 | NEW:mainwindow.py:16-19 inserts `code/supplementary/package` at `sys.path[0]`; NEW:supplementary/package/pycromanager/__init__.py:3-11 and `acquisition/java_backend_acquisitions.py:4-12` insert the same folder again | Uses env `site-packages/pycromanager` (0.29.9) and `ndtiff`. | Uses the vendored `pycromanager` and `ndtiff`. | **Same code.** Vendored pycromanager is byte-identical to the env copy except for those two `sys.path` inserts. Vendored `ndtiff` is byte-identical to the env copy. The env's `ndtiff-3.1.0.dist-info` is stale: the installed files are 2.2.1 (`_version.py` → `(2,2,1)`; no `ndtiff_dataset.py`/`ndstorage_base.py` from the 3.1.0 RECORD), and the running env reports `ndtiff 2.2.1`. `Core()`, `Acquisition(...)` and `multi_d_acquisition_events` behave identically. The NDTiff files on disk are written by Micro-Manager's Java side, not Python, and the program never calls `get_dataset`/`Dataset`. See §3. | None. Optionally drop the vendoring, or pin the env, to avoid confusion. | §F note |
| N14 | C | Low | REF changes CWD: REF:system/image_acquisition_and_analysis_system.py:32,435,535,540,831,1018,1156; REF:front_end/Widgets.py:1359,1361,1437 | NEW has no `os.chdir` anywhere | Relative paths resolve against whatever CWD the last imaging step left. For example, after a real alignment CWD = `pos_path\dicfocus<cycle>` (`get_file_name` chdir, `:831`), until max projection restores `system_path` (`:1156`). | CWD never changes. Every relative path resolves to the launch directory. | (a) `aixintest.csv` (REF:front_end/Widgets.py:1394; NEW:front_end/panels/imaging_control_panel.py:181) is written into `pos_path\dicfocus<cycle>\` by REF after a real alignment (into the launch folder only for mock alignment) and always into the launch folder (`code\`) by NEW. It is a debug file and is not read back. (b) Focus best-plane `<pos>.tif` is now written to the launch folder (NEW:system/imaging/focus.py:212-214). That is bug #3. (c) NEW removes REF's latent short window where `focus_status=1` is set (REF:…:533) before CWD is restored (`:535,540` → Widgets `:1359`), during which a relative open of `reagent_sequence_file`/`config_file` would fail. | Keep NEW's no-chdir design. Fix (b) per #3. Optionally write `aixintest.csv` under `pos_path`. | #3 (related) |
| N15 | A | Low | REF:front_end/tissue_scanner.py:260 `tiff.imsave(...)` | NEW:front_end/tissue_scanner.py:316 `tiff.imwrite(...)` | The env's `tifffile` is 2025.2.18, and `hasattr(tifffile,'imsave')` is **False**. So REF's `stich_image` raises `AttributeError` after scanning, and `scan_slide` never opens the coordinate collector. | `imwrite` works. | With today's env, REF's tissue-scanner overview cannot finish; NEW's can (but see #13 for its orientation change). **?** REF `slide1/auto.csv` is dated 2025-04-29, after tifffile was installed (2025-03-12). Either the scanner was run from another interpreter, or the env changed. A human should confirm which interpreter Elm actually runs. | Keep `imwrite`. | §F (confirmed with env evidence) |
| N16 | C | Low | — (REF has no manifests) | worktree root: requirements.txt, environment.yml, pyproject.toml, setup.py, MANIFEST.in | — | `environment.yml` omits pyzmq, dask, docstring-inheritance and sortedcontainers. The vendored pycromanager imports all of them (zmq_bridge, acquisition), so an env built from it cannot import pycromanager. `environment.yml` and `requirements.txt` also omit zstandard (#18). `pyproject.toml` declares the invalid backend `setuptools.backends._legacy:_Backend` and an entry point `seq_o_matic.mainwindow:main` that does not exist (mainwindow is a script with no `main`). `tifffile>=2021.7` and `opencv-python>=4.5` are unpinned (Elm: 2025.2.18, 4.6.0.66). | No effect on Elm, which uses the existing `seq_o_matic` env. A fresh install from these files would fail or differ. Pins that match Elm: numpy 1.26.0, pandas 1.5.3, matplotlib 3.5.3, scikit-image 0.20.0, nidaqmx 0.9.0, pyserial 3.5, Python 3.10.13. | Fix manifests later (not parity-critical). | #18 (extended) |

Counts: A = 1 (N15), B = 8 (N01–N05, N07, N08, N11, with N11 being #6), C = 7 (N06, N09, N10, N12, N13, N14, N16), D = 0, ? = 0 rows (one provenance question is noted inside N15).
(N11 duplicates bug #6 from the constants angle. N04, N05, N07, N08 and N09 confirm §E. N01, N02 and N03 are new.)

---

## 2. `constants.py` and `types_seq.py` value check

Every constant in NEW:constants.py was compared with the REF literal it replaced.

| NEW constant (constants.py line) | Value | Used at (NEW) | REF literal | Match |
|---|---|---|---|---|
| HEAT_RAMP_TIMEOUT_SECONDS (:11) | 300 | device/Heatingstage.py:160,170 | REF:device/Heatingstage.py:82,92 `300` | same |
| HEAT_TEMP_TOLERANCE (:12) | 0.15 | Heatingstage.py:160 | REF:…:82 `self.temp - 0.15` | same |
| HEAT_TEMP_FAILURE_TOLERANCE (:13) | 0.5 | Heatingstage.py:170 | REF:…:92 `- 0.5` | same |
| HEAT_INITIAL_TEMP_MIN / MAX (:14-15) | 1.5 / 3.0 | Heatingstage.py:281 | REF:…:179 `<= 1.5 or >= 3.0` | same |
| HEAT_CONFIG_WARMUP_SECONDS (:16) | 15 | Heatingstage.py:286 | REF:…:184 `sleep(15)` | same |
| HEAT_CONFIG_DELTA_THRESHOLD (:17) | 0.05 | Heatingstage.py:291 | REF:…:189 `<=0.05` | same |
| HEAT_IDLE_VOLTAGE (:18) | 0.1 | Heatingstage.py:138 | REF:…:71 `write(0.1)` | same |
| HEAT_DEFAULT_TEMP_VOLTAGE (:19) | 5.7 | system/fluidics_exchange_system.py:185 | REF:system/fluidics_exchange_system.py:127 `heat_stage_group(…,5.7,…)` | same |
| HEAT_MONITOR_INTERVAL_SECONDS (:20) | 5 | Heatingstage.py:161 | REF:…:83 `sleep(5)` | same |
| HEAT_HOLD_MONITOR_INTERVAL_SECONDS (:21) | 10 | Heatingstage.py:198 | REF:…:120 `sleep(10)` | same |
| HEAT_THREAD_STAGGER_SECONDS (:22) | 3 | Heatingstage.py:230 | REF:…:143 `sleep(3)` | same |
| FLUIDICS_WAIT_BETWEEN_STEPS_SECONDS (:27) | 3 | fluidics_exchange_system.py:144 | REF:…:97 `waiting_time=3` | same |
| PUMP_WAIT_BUFFER_SECONDS (:28) | 5 | **unused** | (REF uses `FluidicsConstants.bufferms = 5`, unchanged in NEW:system/fluidics_exchange_system.py:68-) | dead constant, no effect |
| SELECTOR_SETTLE_SECONDS (:29) | 2 | device/Selector.py:105,107,113,120; fluidics_exchange_system.py:293 | REF:device/Selector.py:52,54,58,64 `sleep(2)`; REF:system/fluidics_exchange_system.py:214 `sleep(2)` | same (the final `sleep(3)` at REF:Selector.py:67 / NEW:Selector.py:123 stays a literal and is equal) |
| SELECTOR_UNIT_PORT_COUNT (:30) | 11 | Selector.py:45 | REF:Selector.py:18 `unit_port=11` | same |
| SELECTOR_PASSTHROUGH_PORT (:31) | 12 | Selector.py:46 | REF:Selector.py:19 `pass_though_port=12` | same |
| DEFAULT_PUMP_RATE_ML_PER_MIN (:32) | 1.5 | fluidics_exchange_system.py:151 | REF:…:104 `pumprate =1.5` | same (overridden at Start by the GUI field, see N04) |
| DEFAULT_HEAT_TEMP_VOLTAGE (:33) | 5.6 | fluidics_exchange_system.py:145 | REF:…:98 `heat_temp=5.6` | same |
| SEQUENCE_FINISH_DELAY_SECONDS (:34) | 5 | fluidics_exchange_system.py:399 | REF:…:294 `sleep(5)` | same |
| IMAGE_WIDTH_PX (:39) | 3200 | **unused** (imwidth still from scope.json) | — | dead |
| LIVEVIEW_CROP_START / END (:40-41) | 500 / 1200 | **unused** (literal `img[500:1200, 500:1200]` kept at NEW:front_end/logwindow.py:224 = REF:front_end/logwindow.py:126) | 500:1200 | dead, same |
| TOPHAT_FILTER_SIZE (:42) | (10, 10) | front_end/logwindow.py:41 | REF:front_end/logwindow.py:26 `(10, 10)` | same |
| DENOISING_PERCENTILE (:43) | 85 | front_end/logwindow.py:48 | REF:front_end/logwindow.py:32 `85` | same |
| MAIN_WINDOW_GEOMETRY (:48) | "1250x800" | front_end/logwindow.py:95 | REF:front_end/logwindow.py:42 | same |
| DEVICE_POPUP_GEOMETRY (:49) | "500x170" | **unused** (literal kept at NEW:front_end/panels/device_panel.py:28 = REF:front_end/Widgets.py:813,982) | "500x170" | dead, same |

No mismatches in `constants.py`.
- `types_seq.py` contains only `TypedDict` classes and aliases used in annotations. They are imported at NEW:device/Heatingstage.py:29, Pump.py:12, Relay.py:16, Selector.py:22, system/fluidics/protocol_loader.py:17 and system/fluidics_exchange_system.py:35, and have no runtime effect. `ScopeConfig.scope_name` is declared but read nowhere, as in REF.
- Other constant classes: `FluidicsConstants` (REF:system/fluidics_exchange_system.py:43-; NEW:…:68-) matches member by member. The tissue-scanner `scope_constant` (REF:front_end/tissue_scanner.py:23-; NEW:front_end/tissue_scanner.py) is identical apart from a docstring. The imaging `scope_constant` differs only in the focus range (N11).
- **REF literals that NEW now reads from a different source:** none. `scope.json` keys are read the same way: REF:system/image_acquisition_and_analysis_system.py:250-265 vs NEW:system/imaging/imaging_system.py:70-85, and REF:front_end/Widgets.py:709,755 vs NEW:front_end/panels/workspace_panel.py:98,174. `pump_speed_calibration.txt`, `Heat_stage.json`, the pump, selector and relay JSONs, and `Fluidics_Reagent_Components.json` are read from the same relative or `system_path`-based paths in both trees. The values *inside* the files differ (N01–N04).

---

## 3. Runtime environment details

**What NEW imports from where** (launching `python mainwindow.py` from `code\`):
- `sys.path[0]` = `…\code\supplementary\package` (NEW:mainwindow.py:17-19). Its top-level entries are `pycromanager/`, `ndtiff/` and `all_site_packages/`.
  - `pycromanager` comes from the vendored copy (0.29.9). Its `__init__` re-inserts `…\supplementary\package` (no-op), as does `acquisition/java_backend_acquisitions.py` (no-op).
  - `ndtiff` comes from the vendored copy (2.2.1), byte-identical to the env's.
  - `all_site_packages/` is a partial dump of another site-packages: 183 entries (IPython, numpy, PyQt5 dist-info, etc.) inside `all_site_packages/all_site_packages/`. It has no `__init__.py`, and its `.pth` files (`distutils-precedence.pth`, `pywin32.pth`) are **not** processed, because the folder was added with `sys.path.insert`, not `site.addsitedir`. Nothing imports `all_site_packages`, so it is dead weight and shadows nothing.
- Everything else comes from the env (`C:\Users\SVC_barseq\.conda\envs\seq_o_matic`, Python 3.10.13): zmq 26.2.0, dask 2025.2.0, sortedcontainers 2.4.0, docstring_inheritance, pymmcore 11.2.1.71.0 (imported by pycromanager only for the Python backend, which is unused), numpy 1.26.0, tifffile 2025.2.18, cv2 4.6.0, skimage 0.20.0, scipy 1.15.2, pandas 1.5.3, matplotlib 3.5.3, PIL 11.1.0, pyserial 3.5, nidaqmx 0.9.0, pytz 2025.1, zstandard 0.25.0 (used by REF's upload only).
- Program packages (`front_end`, `system`, `device`, `driver`, `constants`, `types_seq`, `logging_config`) come from the script directory `code\` (sys.path entry after the vendor path). No name collides with the vendor folder.
- Use in the code: `Core()` (NEW:system/imaging/imaging_system.py:57, max_projection.py:220, front_end/tissue_scanner.py:206) and `Acquisition(directory=…, name=…, show_display=False)` (NEW focus.py:177,289,316; max_projection.py:203,241; tissue_scanner.py:285). These are the same call forms as REF (REF image_acquisition…:237,404,475,502,1087,1104,1125; tissue_scanner.py:175,239). `multi_d_acquisition_events` is imported but not called in either tree.
- Conclusion: there is no library-level behavior difference. The Java side (Micro-Manager 2.0.3 nightly) and the NDTiff on-disk layout it writes are the same for both trees. Both trees read the tiles with `tifffile` directly.
- Non-code supplementary content: PROD's `supplementary\MicroManager_install\MMSetup_64bit_2.0.3_20240112.exe` is absent from the NEW worktree. NEW has `MMConfig_Ti2E-xc2.cfg`, `Ti2_Mic_Driver.dll`, NIDAQ installers and the selector installer. None of these are used at run time.

---

## 4. Working-directory assumptions

Both trees take `system_path = os.getcwd()` at launch (REF:mainwindow.py:7; NEW:mainwindow.py:29), and `self.cwd = os.getcwd()` (REF:front_end/Widgets.py:71; NEW:front_end/Widgets.py:116). Both therefore **must be launched with CWD = the code folder**. NEW did not change this assumption: only the vendor path uses `__file__`. NEW removed every `os.chdir` (N14).

| Relative access (launch-dir-relative) | REF | NEW | Same? |
|---|---|---|---|
| `LOGO.png` window icon | front_end/logwindow.py:45 | front_end/logwindow.py:98 | same |
| `config_file/Fluidics_Reagent_Components.json` | device/Selector.py:13; front_end/Widgets.py:926 | device/Selector.py:40; front_end/panels/fluidics_control_panel.py:105 | same |
| `config_file/scope.json` | front_end/Widgets.py:707,753 | front_end/panels/workspace_panel.py:96,172 | same (file content differs, N03) |
| `reagent_sequence_file/<protocol>.json` read + copy to pos_path | system/fluidics_exchange_system.py:390-514 | system/fluidics_exchange_system.py:512-520 → system/fluidics/protocol_loader.py:88-100 | same path. In REF it works only if CWD has been restored (N14) |
| `os.listdir("reagent_sequence_file")` recipe list | front_end/recipe_builder.py:22,31 | front_end/recipe_builder.py:31,45 | same (folder names differ, N06) |
| `device/tissue_scanner/<slide>/{auto.csv, slide.pos, stack_1/, stitched_image_check.tif}`, `device/tissue_scanner/template.pos` | front_end/tissue_scanner.py:210,212,225-226,239,246-247,260,265,342 | front_end/tissue_scanner.py:247,249,271-272,285,301-302,316,328,447 | same (template.pos identical up to CR; slide data differ, N07/N08) |
| `test_only.csv` (tile debug) | front_end/tissue_scanner.py:164 | front_end/tissue_scanner.py:182 | same |
| `aixintest.csv` | front_end/Widgets.py:1394 (CWD = dicfocus dir after real alignment) | front_end/panels/imaging_control_panel.py:181 (always launch dir) | location differs (N14) |
| `<pos>.tif` best-focus image | system/image_acquisition_and_analysis_system.py:381 (CWD = `pos_path\focus<cycle>` via `:435`) | system/imaging/focus.py:214 (launch dir) | differs, bug #3 |
| `os.listdir()` of CWD in `get_file_name` | image_acquisition…:31-34, 830-833 (after chdir) | position_utils.py:59 `os.listdir(path)` (absolute) | same result |

`system_path`/`cwd`-joined accesses (independent of later CWD), all the same in both trees:
- `device/pump_speed_calibration.txt`: REF Widgets:73,1052; NEW Widgets:118, fluidics_control_panel:246.
- `config_file/{IsmatecPumpDevice_pump, ElveflowMuxDevice_selector, Fluidics_Reagent_Components, Heat_stage, KMtronic_relay}.json`: REF fluidics_exchange_system:66-80; NEW :110-124.
- `config_file/Heat_stage.json`: REF Widgets:498; NEW experiment_config_panel:232.
- `reagent_sequence_file/Fluidics_sequence_{flush,fill}_all.json`: REF fluidics:106,108; NEW:153,155.
- `logo/{auto_logo,hand}.png`: REF Widgets:81-82; NEW Widgets:126-127.
- `front_end/slide.png`: REF Widgets:489; NEW experiment_config_panel:223.

`experiment_detail.txt`: REF front_end/experiment_profile.py:61-62 uses `os.path.join("E:\\", pos_path, …)`. Because `pos_path` is absolute (it starts with a drive letter), `"E:\\"` is discarded, so this equals NEW experiment_profile.py:74-75. Same.

---

## 5. Coverage table (non-code items and cross-cutting code in scope)

| REF item | NEW counterpart | Verdict |
|---|---|---|
| config_file/ElveflowMuxDevice_selector.json | same path | N02 |
| config_file/Heat_stage.json | same path | N01 |
| config_file/scope.json | same path | N03 (only `maxproject_drive` differs; `scope_name` "Alder" in both, unused) |
| config_file/Fluidics_Reagent_Components.json | same path | same (identical) |
| config_file/IsmatecPumpDevice_pump.json (COM9) | same path | same (identical) |
| config_file/KMtronic_relay.json (COM9) | same path | same (identical) |
| reagent_sequence_file/*.json top level (14 files) | same | same, except Fluidics_sequence_strip.json → N05 |
| reagent_sequence_file/original_sequence_250um_gasket/ (14) | original_sequence/ | N06 (strip differs; 13 identical) |
| reagent_sequence_file/2IRM_and_2CRM_750um_gasket/ (14) | 2IRM_and_2CRM/ | N06 (rename only; contents identical) |
| reagent_sequence_file/750um gasket/ (14) | same | same (identical) |
| device/pump_speed_calibration.txt | same | N04 |
| device/tissue_scanner/template.pos | same | same (differs only in CRLF) |
| device/tissue_scanner/slide{1,2,3}/slide.pos | same | N07 |
| device/tissue_scanner/slide{1,2,3}/auto.csv | same | N08 |
| device/tissue_scanner/slide*_chamber_coor.pos, right_corner.pos, Chamber_Coordinates_Position_Save/ | none | N09 |
| — | device/tissue_scanner/slide1/slide.pos~ | N10 |
| logo/{LOGO,auto_logo,hand,slide}.png | same | same (identical) |
| LOGO.png (root) | same | same (identical) |
| front_end/LOGO.png, front_end/slide.png | same | same (identical) |
| mainwindow.py imports (`from front_end.Widgets import *`, `from front_end.logwindow import *`) | NEW:mainwindow.py:13-26 (explicit imports, vendor sys.path, `setup_logging()`) | N12, N13. The star-import names used (`os`, `Log_window`, `window_widgets`) are all provided. The rest of mainwindow.py (grid layout, `mainloop`) is identical. |
| `Log_window` class body (Tk created at import) | NEW:front_end/logwindow.py `LogWindow` singleton + `Log_window` alias, `_lw = LogWindow.initialize()` at import (:152-158) | same (Tk still created at import; geometry, title and icon equal) |
| `hattop_convert`, `denoise` (REF:front_end/logwindow.py:25-33) | NEW:front_end/logwindow.py:38-49 | same |
| `FluidicsConstants` (REF:system/fluidics_exchange_system.py:43) | NEW:system/fluidics_exchange_system.py:68 | same |
| `scope_constant` (REF:system/image_acquisition_and_analysis_system.py:109) | NEW:system/imaging/position_utils.py | N11 |
| `scope_constant` (REF:front_end/tissue_scanner.py:23) | NEW:front_end/tissue_scanner.py | same |
| (none) | NEW:constants.py (all entries) | same values (see §2); 5 dead constants |
| (none) | NEW:types_seq.py | no runtime effect |
| (none) | NEW:logging_config.py (`TkHandler`, `setup_logging`, `update_log_file`, `get_logger`, `_add_file_handler`, `_update_file_handler`) | N12 |
| (none) | NEW package `__init__.py` files (device, driver, front_end, front_end/panels, system, system/fluidics, system/imaging) | same (import-time re-exports only; no hardware is touched at import) |
| env pycromanager 0.29.9 / ndtiff (2.2.1 files, 3.1.0 metadata) | NEW:supplementary/package/{pycromanager, ndtiff, all_site_packages} | N13 |
| (none) | worktree requirements.txt / environment.yml / pyproject.toml / setup.py / MANIFEST.in | N16 |
| `os.chdir` users (REF image_acquisition…:32,435,535,540,831,1018,1156; Widgets:1359,1361,1437) | none | N14 |
| `tiff.imsave` (REF tissue_scanner.py:260) | `tiff.imwrite` | N15 |
| REF clutter: Untitled.ipynb, test_*.ipynb, aixintest.csv, .ipynb_checkpoints/, .idea/, Saved Games/, Searches/ | absent | not part of program |
