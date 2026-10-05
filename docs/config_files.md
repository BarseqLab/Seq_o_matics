# Configuration Files Reference

All configuration files are located in `code/config_file/` and use JSON format. Each file is a JSON array containing one or more device/component definitions.

---

## IsmatecPumpDevice_pump.json

Defines the Ismatec IPC peristaltic pump connection.

```json
[{
  "pump_name": "IsmatecPumpDevice_1",
  "port": "COM9",
  "tubingDiameter": 0.51,
  "pumpID": "IPC 501",
  "flowReversed": 0
}]
```

| Field | Type | Description |
|-------|------|-------------|
| `pump_name` | string | Identifier for this pump instance |
| `port` | string | Serial COM port (e.g., `"COM9"`) |
| `tubingDiameter` | float | Inner diameter of pump tubing in mm (e.g., `0.51`) |
| `pumpID` | string | Expected pump model ID for verification (e.g., `"IPC 501"`) |
| `flowReversed` | int | `0` = normal flow direction, `1` = reversed |

---

## ElveflowMuxDevice_selector.json

Defines the two cascaded Elveflow multiplexer selectors. Two selectors are used in series to support up to 16 reagent addresses.

```json
[
  {"selector_name": "ElveflowMux_1", "port": "COM6"},
  {"selector_name": "ElveflowMux_2", "port": "COM5"}
]
```

| Field | Type | Description |
|-------|------|-------------|
| `selector_name` | string | Identifier for this selector |
| `port` | string | Serial COM port |

**Addressing scheme:** Reagent addresses 1-11 are routed directly through selector 1. Addresses 12+ engage selector 2's passthrough (port 12) to cascade through selector 1 for extended range.

---

## Heat_stage.json

Defines one or more heating stages controlled via a National Instruments DAQ device.

```json
[
  {
    "heat_stage": "heatstage1",
    "do_port": "port1",
    "do_line": "line0",
    "ai_line": "ai0",
    "DAQ": "Dev2",
    "ao_port": "ao0"
  },
  {
    "heat_stage": "heatstage2",
    "do_port": "port1",
    "do_line": "line1",
    "ai_line": "ai1",
    "DAQ": "Dev2",
    "ao_port": "ao0"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `heat_stage` | string | Identifier for this heating stage |
| `DAQ` | string | NI DAQ device name (e.g., `"Dev2"`) |
| `ao_port` | string | Analog output port for voltage control (shared across stages) |
| `do_port` | string | Digital output port (e.g., `"port1"`) |
| `do_line` | string | Digital output line for this heater (e.g., `"line0"`) |
| `ai_line` | string | Analog input line for temperature readback (e.g., `"ai0"`) |

**How it works:**
- The analog output (`ao_port`) sets a voltage to control heating power (shared by all stages on the same DAQ).
- Each stage has its own digital output line (`do_line`) that enables/disables heating for that stage.
- Temperature is monitored via the analog input (`ai_line`) for each stage independently.

---

## KMtronic_relay.json

Defines the KMtronic 4-channel USB relay controller.

```json
[{"Relay_name": "Relay_1", "port": "COM9"}]
```

| Field | Type | Description |
|-------|------|-------------|
| `Relay_name` | string | Identifier for this relay |
| `port` | string | Serial COM port |

**Note:** The relay functionality is currently partially implemented (stub) in the codebase.

---

## Fluidics_Reagent_Components.json

Maps reagent/solution names to selector addresses. This defines which physical port on the selector manifold each reagent is connected to.

```json
[
  {"solution": "incorporation buffer", "address": 1},
  {"solution": "PBST", "address": 2},
  {"solution": "Iodoacetamide Blocker", "address": 3},
  {"solution": "IRM", "address": 4},
  {"solution": "USM", "address": 5},
  {"solution": "CRM", "address": 6},
  {"solution": "FISH WASH", "address": 7},
  {"solution": "STRIP", "address": 8},
  {"solution": "hyb oligos mix", "address": 9},
  {"solution": "DAPI", "address": 10},
  {"solution": "bc primer mix", "address": 11},
  {"solution": "gene primer mix", "address": 12},
  {"solution": "hyb oligos mix 2", "address": 13},
  {"solution": "END", "address": 14},
  {"solution": "hyb oligos mix 3", "address": 15},
  {"solution": "hyb oligos mix 4", "address": 16}
]
```

| Field | Type | Description |
|-------|------|-------------|
| `solution` | string | Human-readable reagent name |
| `address` | int | Physical selector port number (1-16) |

---

## scope.json

Defines microscope parameters for the imaging system.

```json
[{
  "scope_name": "Alder",
  "piezo": 1,
  "ZDrive_safe_pos": 11.3,
  "XYStage_fluidics_safe_pos": [56556, -8095],
  "XYStage_image_safe_pos": [44951, -5484],
  "scope_exposure_time_dict": {
    "G": 60, "T": 30, "A": 20, "C": 40, "DIC": 20,
    "Hyb-GFP": 100, "Hyb-YFP": 30, "Hyb-TxRed": 30,
    "Hyb-Cy5": 20, "Hyb-DAPI": 20,
    "C-focus": 20, "Hyb-TxRed-focus": 20
  },
  "z_dir": -1,
  "stage_x_dir": -1,
  "stage_y_dir": 1,
  "pixel_size": 0.33,
  "imwidth": 3200,
  "overlap": 10,
  "geneseq_focus_target_channel": "Hyb-DAPI",
  "Hyb_focus_target_channel": "Hyb-DAPI",
  "maxproject_drive": "M:\\",
  "align_channel": "Hyb-DAPI"
}]
```

| Field | Type | Description |
|-------|------|-------------|
| `scope_name` | string | Microscope identifier (e.g., `"Alder"`) |
| `piezo` | int | `1` = has piezo z-stage, `0` = no piezo |
| `ZDrive_safe_pos` | float | Safe Z position (um) to retract to before XY moves |
| `XYStage_fluidics_safe_pos` | [float, float] | XY position to move stage to during fluidics exchange |
| `XYStage_image_safe_pos` | [float, float] | XY position to move stage to before imaging |
| `scope_exposure_time_dict` | object | Exposure time (ms) per imaging channel |
| `z_dir` | int | Z-axis direction convention (`-1` or `1`) |
| `stage_x_dir` | int | X-axis direction convention (`-1` or `1`) |
| `stage_y_dir` | int | Y-axis direction convention (`-1` or `1`) |
| `pixel_size` | float | Camera pixel size in um/pixel |
| `imwidth` | int | Camera image width in pixels |
| `overlap` | int | Tile overlap percentage (e.g., `10` = 10%) |
| `geneseq_focus_target_channel` | string | Channel used for autofocus during gene sequencing cycles |
| `Hyb_focus_target_channel` | string | Channel used for autofocus during hybridization cycles |
| `maxproject_drive` | string | Network drive path for max-projection output (e.g., `"M:\\"`) |
| `align_channel` | string | Channel used for inter-cycle image alignment |

### Z-stack thickness keys

All optional. A missing key takes the default, which reproduces the behaviour before these keys existed (30 µm stack, 60 µm focus sweep, one projection per tile). The values in effect are shown in the start confirmation window and written to `log.txt` and `zstack_settings_used.json` in the work folder. They are read again each time Start is pressed.

| Field | Default | Description |
|-------|---------|-------------|
| `z_stack_thickness_um` | `30` | T, thickness of the imaging stack. Must be at most `focus_range_cap_um`. |
| `z_step_um` | `1.5` | Step between imaging planes. N = round(T / step) planes. |
| `focus_step_um` | `1.5` | Focus step for thin sections |
| `focus_step_thick_um` | `3` | Focus step when T ≥ `thick_section_um` |
| `thick_section_um` | `50` | Thickness at which a section counts as thick |
| `focus_range_cap_um` | `300` | Upper limit on the focus sweep R = min(max(1.2·T, T + 30), cap) |
| `focus_method` | `"peak"` | `"peak"` (sharpest plane), `"band_center"` (middle of the sharp band), or `"auto"` (`band_center` when T ≥ `thick_section_um`) |
| `focus_extreme_change_frac` | `0.3333` | A focus change of at least this fraction of R is reported as extreme (20 µm at the defaults) |
| `band_center_frac` | `0.5` | `band_center` threshold, as a fraction of the way from baseline to peak |
| `maxproj_split_above_um` | `30` | Split the stack into sub-stack projections only when T is greater than this |
| `maxproj_substack_um` | `30` | Sub-stack size. A leftover of half a group or less joins the last group. |
| `storage_margin` | `1.10` | Safety factor on the disk-space estimate |

With more than one sub-stack, each tile gives `MAX_<pos>_z00.tif`, `_z01`, … (`z00` is the lowest piezo position), and `<cycle>_substacks.csv` in the same folder lists the planes and piezo range of each group. With one group the file keeps its usual name, `MAX_<pos>.tif`.

### Channel Names

Channels correspond to filter cube / illumination combinations configured in Micro-Manager:

| Channel | Usage |
|---------|-------|
| `G`, `T`, `A`, `C` | Barcode sequencing base channels (green, red, etc.) |
| `DIC` | Differential interference contrast (brightfield) |
| `Hyb-GFP`, `Hyb-YFP`, `Hyb-TxRed`, `Hyb-Cy5` | Hybridization fluorescence channels |
| `Hyb-DAPI` | DAPI nuclear stain channel (typically used for focus and alignment) |
| `C-focus`, `Hyb-TxRed-focus` | Dedicated focus channels with specific exposure settings |
