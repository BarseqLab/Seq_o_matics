# Hard-coded per-microscope values: reference vs main

These are values written directly in the Python code rather than in `config_file/`. Changing microscopes, devices, storage or the imaging scheme may require editing them.

- **REF** = Elm reference `C:\Users\SVC_barseq\Seq_o_matics_2.5\` (paths relative to that folder).
- **main** = upstream `BarseqLab/Seq_o_matics` `main` @ `5e5adf0` (paths relative to `code/`).

The list was collected on 2026-10-05. **Decision pending:** whether, and how, to change these. Moving them into config is planned for a separate session. Nothing in this file has been changed yet.

## 1. Values that differ between REF and main

| # | Value | REF (Elm) | main | Effect of main's value | Related item |
|---|---|---|---|---|---|
| H1 | Focus sweep range | ±30 µm, giving 40 planes. `system/image_acquisition_and_analysis_system.py:112-113` | ±40 µm, giving 54 planes. `system/imaging/position_utils.py:29-30` | Focus takes about 35% longer, with a wider search window than validated. | P06 |
| H2 | Focus stack reshape | `reshape(-1, imwidth, imwidth)`, any plane count. `…analysis_system.py:374` | `reshape(80, …)`, hard-coded. `system/imaging/focus.py:207` | `ValueError` if the align channel differs from the target channel (54 planes × 2 = 108 ≠ 80). | P07 |
| H3 | Piezo pre-position before a focus stack (primary path) | **185 µm**. `…analysis_system.py:469` | `piezo_middle_pos` (row 0's piezo, e.g. 200). `focus.py:284` | Different start position. The retry path still uses 185 (`focus.py:310`, REF `:496`). | P16 |
| H4 | Focus analysis threads | 4. `…analysis_system.py:513` | 2. `focus.py:327` | Sharpness analysis takes about 2× as long. Same result. | P16 |
| H5 | Pump flow rate set on connect | **1.5 mL/min**. `device/Pump.py:12` | 1.2. `device/Pump.py:36` | Prime, wash, flush and manual fill deliver about 80% of nominal, because run times assume the calibration measured at 1.5. | P13 |
| H6 | Default storage server | `10.128.30.152`. `front_end/Widgets.py:305` | `jackw-ux1`. `front_end/Widgets.py:349` | Data and notes are sent to a different host. | P12 |

These six are the only hard-coded values that differ. Each one is a parity item (P06, P07, P12, P13, P16).

## 2. Values that are the same in REF and main

### Storage, servers, cloud
| Value | Value (both) | REF | main |
|---|---|---|---|
| Default server account | `imagestorage` | `front_end/Widgets.py:298` | `front_end/Widgets.py:342` |
| Server destination path | `/mnt/imagestorage/<pos_path[3:]>_maxprojection` | `…analysis_system.py:1196, :1204` | `system/imaging/max_projection.py:328, :344` |
| AWS account default (GUI only, not used by the upload) | `aixin.zhang@alleninstitute.org` | `front_end/Widgets.py:312` | `front_end/Widgets.py:356` |
| S3 bucket, storage class, checksum | `barseq-acquisition`, `INTELLIGENT_TIERING`, SHA256 | `front_end/Widgets.py:588-626` | (stub until P10) |
| Experiment-name assumption | `pos_path[3:]` (strips a drive prefix like `D:/`) | many | many |
| Disk-space estimate per tile | `102400920` bytes (`check_storage` is never called, D16) | `front_end/Widgets.py:1179` | `front_end/automation_controller.py:228` |

### Pump and fluidics
| Value | Value (both) | REF | main |
|---|---|---|---|
| Flow rate reset before each automated fluidics step | 1.5 mL/min | `front_end/Widgets.py:1239` | `front_end/automation_controller.py:83` |
| PBST in-chamber flush after prime/wash | 4 mL; wait `4/pumprate*60 + 5` s | `front_end/Widgets.py:909-914` | `front_end/panels/fluidics_control_panel.py:86-100` |
| Manual-fill wait | `vol/1.5*60 + 10` s (ignores calibration, D11) | `front_end/Widgets.py:970` | `fluidics_control_panel.py:146` |
| Default pump rate before the GUI sets it | 1.5 | `system/fluidics_exchange_system.py:104` | `constants.DEFAULT_PUMP_RATE_ML_PER_MIN` |
| Wait between steps, end-of-sequence delay, pump buffer | 3 s, 5 s, 5 s | `system/fluidics_exchange_system.py:97, 294, FluidicsConstants.bufferms` | `constants.py:27, 34`, `FluidicsConstants.bufferms` |
| Selector geometry | 11 ports per unit, pass-through port 12, source limit 22 | `device/Selector.py:18-19` | `constants.py:30-31` |
| Selector settle times | 2 s, then 3 s | `device/Selector.py:52-67` | `constants.SELECTOR_SETTLE_SECONDS`, `device/Selector.py:123` |

### Heaters
| Value | Value (both) | REF | main |
|---|---|---|---|
| Sequence setpoint / config / idle voltage | 5.6 V / 5.7 V / 0.1 V | `system/fluidics_exchange_system.py:98, :127`; `device/Heatingstage.py:71` | `constants.py:33, :19, :18` |
| Ramp timeout; tolerances | 300 s; −0.15 / −0.5 V | `device/Heatingstage.py:82, :92` | `constants.py:11-13` |
| Poll intervals; thread stagger | 5 s / 10 s; 3 s | `device/Heatingstage.py:83, :120, :143` | `constants.py:20-22` |
| Config check range, warm-up, delta | 1.5-3.0 V, 15 s, 0.05 | `device/Heatingstage.py:179-189` | `constants.py:14-17` |

### Microscope and imaging
| Value | Value (both) | REF | main |
|---|---|---|---|
| Piezo step | 1.5 µm | `…analysis_system.py:115` | `position_utils.py` |
| Max-projection range | ±15 µm | `…analysis_system.py:119-120` | `position_utils.py` |
| Piezo position on the focus retry path | 185 µm | `…analysis_system.py:496` | `focus.py:310` |
| Piezo reset in `image_with_piezo` (unused by the GUI) | 200 µm | `…analysis_system.py:410` | `focus.py:183` |
| Focus and max-projection retry sleeps | 3 s / 2 s; end-of-cycle 3 s | `…analysis_system.py` focus/maxproj | `focus.py`, `max_projection.py` |
| Positions per slice | 4 | `…analysis_system.py:126` | `position_utils.py` |
| `scope_constant.z_dir` (separate from `scope.json` `z_dir` = −1) | 1 | `…analysis_system.py:127` | `position_utils.py` |
| Focus sharpness crop | `[800:2400, 800:2400]` | `…analysis_system.py:377` | `focus.py:210` |
| Sharpening kernel | `[[0,1,0],[-1,5,-1],[0,-1,0]]` | `…analysis_system.py:123-125` | `position_utils.py` |
| Focus-shift warning threshold | ≥ 20 µm | `…analysis_system.py:524` | `focus.py:338` |
| Alignment image size | 2048 × 2048 | `…analysis_system.py:743, :746` | `alignment.py:315, :318` |
| Alignment sanity thresholds | ±50 px | `…analysis_system.py:811-821` | `alignment.py:404-414` |
| Channel sets per cycle type | geneseq/bcseq 01: G, T, A, C, Hyb-DAPI; 02+: G, T, A, C; hyb: Hyb-GFP, Hyb-YFP, Hyb-TxRed, Hyb-Cy5, Hyb-DAPI, DIC | `…analysis_system.py:997-1009` | `max_projection.py:105-120` |
| DIC plane kept in max projection | index 9 | `…analysis_system.py:1187` | `max_projection.py:311-314` |
| Live-view crop and reshape | `[500:1200]`; 2048² | `front_end/logwindow.py:126`; `…analysis_system.py:1218` | `front_end/logwindow.py:224`; `max_projection.py:365-367` |
| Micro-Manager device names | `XYStage`, `ZDrive`, `DA Z Stage` | throughout | throughout |
| Focus channels | `[align_channel, target_channel]` from `scope.json`. When both are `Hyb-DAPI`, the stack has 80 frames (see Q3). | `…analysis_system.py:424, :428` | `focus.py:240, :244` |

### Tissue scanner (not used on Elm)
| Value | Value (both) | REF | main |
|---|---|---|---|
| Overview Z default | 3228 | `front_end/tissue_scanner.py:198` | `front_end/tissue_scanner.py:229` |
| Overview channel and exposure | Hyb-DAPI 20 ms; DIC event 10 ms | `tissue_scanner.py:237, :169` | `tissue_scanner.py:187` and `run_scope` |
| Exposure table | G 220, T 150, A 100, C 100, DIC 10, GFP 100, TxRed 100, DAPI 50 | `tissue_scanner.py:41` | `tissue_scanner.py:59` |
| `scope_constant` | focus ±30, max-projection ±15, step 1.5, pixel size 0.33, imwidth 3200, overlap 0 | `tissue_scanner.py:23-40` | `tissue_scanner.py:30-50` |

## 3. Notes
- All 26 constants that main moved into `constants.py` keep REF's values. Five of them are unused.
- None of the values in §2 changed between REF and main. Any change to them would be a new decision, not a parity fix.
