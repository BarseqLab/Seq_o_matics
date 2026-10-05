# Hard-coded per-microscope values (to handle in a separate session)

These values are written directly in the Python code, not in `config_file/`. Changing microscopes, devices or storage may require editing them. The list was collected on 2026-10-05 from this branch and compared with the Elm reference (REF = `C:\Users\SVC_barseq\Seq_o_matics_2.5\`).

**Status on this branch:**
- Rows marked **(P##)** are reference-parity regressions. The parity work restores them to the Elm/REF value.
- Every other row already matches REF.
- Moving any of them into config is out of scope here; it is planned for the separate session.

Locations are NEW (`code/`) paths at upstream `5e5adf0`. Line numbers may shift as parity fixes land.

## Storage, servers, cloud

| Value | Elm/REF | NEW now | Where (NEW) | Notes |
|---|---|---|---|---|
| Default storage server | `10.128.30.152` | `jackw-ux1` **(P12)** | `front_end/Widgets.py:349` | REF `front_end/Widgets.py:305` |
| Default server account | `imagestorage` | same | `front_end/Widgets.py:342` | |
| Server destination path | `/mnt/imagestorage/<pos_path[3:]>_maxprojection` | same | `system/imaging/max_projection.py:328, :344` | `scp -r` nests the folder (D14) |
| AWS account default (GUI only) | `aixin.zhang@alleninstitute.org` | same | `front_end/Widgets.py:356` | The value is not used by the upload; the AWS CLI's own credentials are. |
| S3 bucket and storage class | `barseq-acquisition`, `INTELLIGENT_TIERING`, SHA256 | (stub until P10) | REF `front_end/Widgets.py:588-626` | |
| Experiment-name assumption | `pos_path[3:]` (strips a drive letter such as `D:/`) | same | max_projection, automation_controller, alignment | Breaks for UNC or deeper paths. |
| `experiment_detail.txt` root | `os.path.join("E:\\", pos_path, …)` | dropped `E:\\` | REF `front_end/experiment_profile.py:61-62` | Same result for absolute paths (C11). |
| Disk-space estimate per tile | `102400920` bytes | same | `front_end/automation_controller.py:228` | `check_storage` is never called (D16). |

## Pump and fluidics

| Value | Elm/REF | NEW now | Where (NEW) | Notes |
|---|---|---|---|---|
| Pump flow rate set on connect | 1.5 mL/min | 1.2 **(P13)** | `device/Pump.py:36` | REF `device/Pump.py:12` |
| Flow rate reset before each automated fluidics step | 1.5 | same | `front_end/automation_controller.py:83` | REF `front_end/Widgets.py:1239` |
| Manual-fill wait | `vol / 1.5 * 60 + 10` s | same | `front_end/panels/fluidics_control_panel.py:146` | Ignores the calibration (D11). |
| PBST in-chamber flush after prime/wash | 4 mL | same | `front_end/panels/fluidics_control_panel.py` (sensor_fluidics_process) | |
| Default pump rate before the GUI sets it | 1.5 | same | `constants.DEFAULT_PUMP_RATE_ML_PER_MIN` | |
| Selector geometry | 11 ports per unit, pass-through port 12, source limit 22 | same | `constants.py:30-31`, `device/Selector.py` | D04 |
| Selector settle times | 2 s, final 3 s | same | `constants.SELECTOR_SETTLE_SECONDS`, `device/Selector.py:123` | |

## Heaters

| Value | Elm/REF | NEW now | Where (NEW) |
|---|---|---|---|
| Heat setpoint voltage (sequence) / config voltage / idle voltage | 5.6 V / 5.7 V / 0.1 V | same | `constants.py:18-19, :33` |
| Ramp timeout, tolerances, poll intervals, stagger | 300 s; −0.15 / −0.5; 5 s / 10 s; 3 s | same | `constants.py:11-22` |
| Config check range, warm-up, delta | 1.5-3.0 V, 15 s, 0.05 | same | `constants.py:14-17` |

## Microscope and imaging

| Value | Elm/REF | NEW now | Where (NEW) | Notes |
|---|---|---|---|---|
| Focus sweep range | ±30 µm | ±40 **(P06)** | `system/imaging/position_utils.py:29-30` | REF `system/image_acquisition_and_analysis_system.py:112-113` |
| Piezo step | 1.5 µm | same | `position_utils.py` (`scope_constant.piezo_step`) | |
| Max-projection range | ±15 µm | same | `position_utils.py` | |
| Piezo pre-position before a focus stack | **185** µm (both paths) | `piezo_middle_pos` on the primary path, 185 on the retry path **(P16)** | `system/imaging/focus.py:284, :310` | REF `:469`, `:496` |
| Piezo reset in `image_with_piezo` | 200 µm | same | `focus.py:183` | Unused by the front end. |
| Positions per slice | 4 | same | `position_utils.py` (`pos_per_slice`) | Used in alignment. |
| `scope_constant.z_dir` | 1 | same | `position_utils.py` | Separate from `scope.json` `z_dir` (−1). |
| Focus sharpness crop | `[800:2400, 800:2400]` | same | `focus.py:210` | Assumes imwidth ≥ 2400. |
| Sharpening kernel | `[[0,1,0],[-1,5,-1],[0,-1,0]]` | same | `position_utils.py` (`sharpen1`) | |
| Focus analysis threads | 4 | 2 **(P16)** | `focus.py:327` | |
| Focus-shift warning threshold | ≥ 20 µm | same | `focus.py:338` | |
| Alignment image size | 2048 × 2048 (reshape in `imregcorr`) | same | `system/imaging/alignment.py:315, :318` | DIC images must be 2048². |
| Alignment sanity thresholds | ±50 px | same | `alignment.py:404-414` | |
| Channel sets per cycle type | geneseq/bcseq 01: G, T, A, C, Hyb-DAPI; 02+: G, T, A, C; hyb: Hyb-GFP, Hyb-YFP, Hyb-TxRed, Hyb-Cy5, Hyb-DAPI, DIC | same | `system/imaging/max_projection.py:105-120` | Names must match MM channel presets. |
| DIC plane kept in max projection | plane index 9 | same | `max_projection.py:311-314` | |
| Live-view crop and reshape | `[500:1200]`, 2048² | same | `front_end/logwindow.py:224`, `max_projection.py:365-367` | |
| Micro-Manager device names | `XYStage`, `ZDrive`, `DA Z Stage` | same | focus.py, max_projection.py | |

## Tissue scanner (not used on Elm)

| Value | Elm/REF | NEW now | Where (NEW) |
|---|---|---|---|
| Overview Z default | 3228 | same | `front_end/tissue_scanner.py:229` |
| Overview channel and exposure | Hyb-DAPI 20 ms (DIC event 10 ms) | same | `tissue_scanner.py:187` and `run_scope` |
| Exposure table | G 220, T 150, A 100, C 100, DIC 10, GFP 100, TxRed 100, DAPI 50 | same | `tissue_scanner.py:59` |
| `scope_constant` | focus ±30, max-projection ±15, step 1.5, pixel size 0.33, imwidth 3200, overlap 0, scale 0.1 | same | `tissue_scanner.py:30-50` |
