# Inventory F: Fluidics, devices and drivers (REF vs NEW)

REF = `C:\Users\SVC_barseq\Seq_o_matics_2.5\`; NEW = `C:\Users\SVC_barseq\Seq_o_matics_github\.claude\worktrees\reference-parity\code\`.
Everything below comes from reading the code statically. Nothing was run or imported. Bug-report line numbers (PROD) were checked against NEW and match.

## 1. Findings table

| ID | Group | Severity | REF location | NEW location | What REF does | What NEW does | Effect on a run | Proposed action | Bug-report # |
|---|---|---|---|---|---|---|---|---|---|
| F01 | B | Critical | REF:system/fluidics_exchange_system.py:280-295 (consumers REF:front_end/Widgets.py:1255-1260, :901-905) | NEW:system/fluidics_exchange_system.py:384-400 (consumers NEW:front_end/automation_controller.py:105-107, NEW:front_end/panels/fluidics_control_panel.py:86) | On normal completion it sets the int flags `cycle_done = 1` and `start_image = 1`. Both consumers poll those flags every 2 s. | Sets the same int flags but never calls `cycle_done_event.set()` or `start_image_event.set()`. Both consumers wait only on the events. The events are set only in `finishSequence()` (:342-347) and `cancelSequence()` (:274-283), and nothing calls either. | The automated run hangs after the first fluidics step; only Cancel ends it. Prime and Wash never do the 4 mL in-chamber PBST flush, never log "Wash/Prime line Done!", and never disconnect the pump, selector or heater (`sensor_fluidics_process`, panel :86-100). **New consequence:** COM9, COM11 and COM10 stay open and the DAQ tasks stay reserved, so the next Start, Prime or Wash fails inside `connect_pump()`/`connect_selector()` (the serial port is already open) until the program is restarted. | In the completion branch, right where the int flags are set (before `time.sleep(5)`, as REF does), add `self.cycle_done_event.set()` and `self.start_image_event.set()`. Keep the int flags. | #1, #2 (confirmed) |
| F02 | B | High | REF:front_end/Widgets.py:1076-1089 | NEW:front_end/Widgets.py:721-734 | Cancel sets `fluidics.cycle_done = 1`, which releases the polling flush thread. | Sets `cycle_done = 1` but not `cycle_done_event`. | A Cancel during Prime or Wash leaves the flush thread blocked forever, and the devices stay connected (see F01). | Add `self.fluidics.cycle_done_event.set()` to `cancel_btn_handler`. **Do not** call `fluidics.cancelSequence()` as the bug report suggests: it also calls `stopPump()` (sends `1I`), which REF's cancel never does, and it raises if the pump was never connected or its port is closed. That would change REF behavior and could abort the handler before the GUI reset. | #4 (confirmed; the proposed fix is amended here) |
| F03 | D | Low | REF:front_end/Widgets.py:1252-1255, REF:system/fluidics_exchange_system.py:248-249 | NEW:front_end/automation_controller.py:102-105, NEW:system/fluidics_exchange_system.py:333-336 | `start_image` stays 1 from the previous fluidics step. It is reset only inside the new worker thread (`startSequence`), and the caller reads the flag right after `t.start()`. | Same pattern with `start_image_event`, which is cleared only inside the worker thread. | This is a latent race in both trees. If the caller reads before the worker resets the flag (unlikely under the GIL), imaging would start while fluidics is still running. It becomes live in NEW once F01 is fixed. | When fixing F01, also clear `start_image_event` (and set `start_image = 0`) in the caller before `t.start()`. That is harmless and keeps parity. | – |
| F04 | B | Medium | REF:device/Pump.py:12 | NEW:device/Pump.py:36 | `initialize()` calls `setFlowRate(1.5)`. | Calls `setFlowRate(1.2)`. | Every `connect_pump()`/`config_pump()` leaves the pump at 1.2 mL/min. Automated fluidics steps reset it to 1.5 (NEW:front_end/automation_controller.py:83, the same as REF:Widgets.py:1239). Prime and Wash fill/flush sequences, the 4 mL in-chamber flush and manual "fill single reagent" all run at 1.2 mL/min, while the run time is still `vol/pumprate`. They therefore deliver about 20 % less than REF. | Restore `setFlowRate(1.5)`, for example via a constant equal to `DEFAULT_PUMP_RATE_ML_PER_MIN`. | #11 (confirmed) |
| F05 | B | Critical | REF:config_file/ElveflowMuxDevice_selector.json | NEW:config_file/ElveflowMuxDevice_selector.json | Selector ports `COM11` (selector 1) and `COM10` (selector 2). | `COM6` and `COM5`. | On Elm, `config_selector()`/`connect_selector()` open the wrong COM ports: the selector config fails ("Please, reconnect selector groups!") or the wrong serial device gets addressed. No fluidics can run. **This contradicts the bug report's "config_file is byte-identical": that holds for PROD, but the NEW worktree's committed config differs.** | Copy REF's `config_file/ElveflowMuxDevice_selector.json`. | – (new) |
| F06 | B | Critical | REF:config_file/Heat_stage.json | NEW:config_file/Heat_stage.json | All three stages are on DAQ `Dev3` (ao0, port1/line0-2, ai0/ai1/ai3). | All on `Dev2`. | On Elm, `heat_stage_group.connect_heater_group()` builds `Dev2/ao0` etc. Task creation fails or drives the wrong NI device, so heater config and every `connect_heater()` (Prime, Wash, Start) raise. | Copy REF's `config_file/Heat_stage.json`. (`scope.json` also differs, `maxproject_drive` `D:\` → `M:\`; that belongs to the imaging/config area.) | – (new) |
| F07 | B | High | REF:reagent_sequence_file/Fluidics_sequence_strip.json:6-8 | NEW:reagent_sequence_file/Fluidics_sequence_strip.json:6 | STRIP ×3, the 300 s heat step, then **2 × 4 mL PBST (source 2)**. | Ends after the heat step. | After every strip cycle, NEW leaves hot STRIP buffer in the chamber with no PBST wash. Downstream chemistry and imaging see residual strip buffer. | Copy REF's strip protocol (and the other gasket-specific files, per section E). | Section E (confirmed) |
| F08 | B | High | REF:device/Heatingstage.py:126-129 | NEW:device/Heatingstage.py:204-210 | The `except` block sets `self.status[i] = 0` first, then switches the stage to image mode. | `status[i] = 0` was removed. `status` is reset only in `__init__` (:69). | Within one heater-group instance, a stage that succeeded in an earlier heat step and throws a DAQ exception in a later one still counts. `heat_status` becomes 1 and the sequence continues as if heated. REF stops the sequence instead (see F11). | Restore `self.status[i] = 0` as the first line of the `except` block. | #7 (confirmed) |
| F09 | B | Low | REF:device/Heatingstage.py:126-133 | NEW:device/Heatingstage.py:204-206 | The `except` block resets `status` and **writes `do_task[i]` back to image mode before** it touches `name`. If the exception came from the first `ai_task[i].read()` (:78), `name` is unbound, and the later f-string raises `UnboundLocalError` only after the DO line was reset. | The first statement is `logger.error("Device %s heating error: %s", name, e)`. If the first read fails, `name` is unbound, so `UnboundLocalError` is raised **before** `do_task[i].write(self.image_mode)`. | When the first temperature read fails, NEW leaves that stage's DO line in heat mode (`False`). `end_heat()` still drops AO to 0.1 V. The heater stays enabled at low drive until the next `connect_heater_group()` or image-mode write. | Restore REF's order: `status[i]=0`, then the `do_task` write, and log only after that. Also bind `name = self.dev_name[i]` before the `try`, which fixes the D-bug in both trees. | – (new) |
| F10 | A | Medium | REF:front_end/Widgets.py:1078 | NEW:front_end/Widgets.py:724 | `self.fluidics.Heatingdevice.cancel==1` is a comparison, so Cancel never stops the heater threads. The heat step runs to completion (up to 300 s ramp plus hold), then `runSequence` sees status -1 and stops. | `= 1` makes the heater threads leave their ramp and hold loops within ≤5 s or ≤10 s. `runSequence` logs "Heater is cancelled" and schedules nothing more. Side effect: the cancelled stages still log "Device X is done with heat successfully!" and set `status=1`, and the group may log "All stages heated successfully" (NEW:device/Heatingstage.py:199-202, 234-238). | Cancel stops heating promptly in NEW. The log text is misleading. | Keep the NEW fix. Optionally skip the success log or status when `self.cancel==1`. Port the fix back to REF. | Section F (confirmed) |
| F11 | D | Medium | REF:system/fluidics_exchange_system.py:352-357 | NEW:system/fluidics_exchange_system.py:464-469 | When the heat step fails (`heat_status==0`), it logs "Heater is wrong" and returns. It never schedules the next step and never sets `cycle_done` or `start_image`. | Same. | In both trees, the automated run then waits forever (only Cancel ends it), and `sequenceStatus` stays 1, so any later `startSequence()` refuses to run ("System is still running!"). | Out of parity scope. List it for the owners. | – |
| F12 | ? | Low | REF:device/pump_speed_calibration.txt (bytes `1.58\r\n\r\n`), read at REF:front_end/Widgets.py:73-74 | NEW:device/pump_speed_calibration.txt (bytes `1.3\r\n\r\n`), read at NEW:front_end/Widgets.py:118-119 | The value is 1.58. | The value is 1.3. | **Correction to the bug report:** both files end with an empty line, so `f.readlines()[-1]` is `"\n"` in both trees, and the stored value is **not** used as the GUI default. In both trees the pump-speed entry starts empty (a newline), and `pumprate` is whatever the operator types. The value difference therefore has no runtime effect today. It would matter only if the file had a single line. | Copy REF's file for record parity. Separately, D-bug in both trees: read the last *non-empty* line, or `strip()` before writing (`start_btn_handler` writes `get()+"\n"`, so the newline left in the entry produces the blank line). | Section E (corrected) |
| F13 | C | Low | REF:driver/ismatec_ipc.py:150-185 | NEW:driver/ismatec_ipc.py:168-228, NEW:device/Pump.py:81-90 | `setFlowVolumeAndRate(flowTime)`. The serial commands are `N`, `W`, then `V####` / `VM###` / `VH###`. | `(flowVolume, flowTime)` sends the same commands in the same order, then computes and prints `dispenseRate = float(flowVolume)/float(flowTimeNow)`. | The serial traffic is identical. `ZeroDivisionError` happens only if flowTime < 0.1 s (volume < ~0.003 mL); the smallest pump step in every protocol is 1 mL, so it is never triggered. The `float()` makes the string volume from the Spinbox (manual fill) safe. The rate printed in the hours branch has the wrong unit. | Optional: guard the division or drop the print. | #17 (confirmed; no current trigger) |
| F14 | C | Low | REF:system/fluidics_exchange_system.py:388-516 | NEW:system/fluidics/protocol_loader.py:28-102, NEW:system/fluidics_exchange_system.py:502-518 | Match order: geneseq01, bcseq01, geneseq02+, bcseq02+, **user_defined**, HYB, add_gene_primer, add_bc_primer, HYB_rehyb, add_gene_primer_rehyb, add_bc_primer_rehyb, strip. | `user_defined` comes first. Then geneseq/bcseq, then the three `rehyb` variants (add_gene, add_bc, HYB), then the non-rehyb variants (add_gene, add_bc, HYB), then strip. | Every recipe-builder name (`Fluidics_sequence_<x>NN`, REF:front_end/recipe_builder.py:31-72) resolves to the same file in both trees, so there is no effect today. The bug report's "mutually exclusive" claim holds only within one family: a hand-edited name containing both `HYB` and `add_gene_primer`/`add_bc_primer` would load HYB in REF and the primer file in NEW. A name with `user_defined` plus `geneseq`/`bcseq` would also differ. The paths are relative to the CWD in both trees (`reagent_sequence_file`); NEW never calls `chdir`, so the CWD is always the launch directory, which equals REF's state at that point. | Reorder `PROTOCOL_MAP` to REF's order (put `user_defined` after bcseq02+) for strict parity. | #16 (confirmed, refined) |
| F15 | A | Low | REF:system/fluidics_exchange_system.py:516; caller REF:front_end/Widgets.py:1242-1252 (bare `except`) | NEW:system/fluidics/protocol_loader.py:73; caller NEW:front_end/automation_controller.py:90-101 (`except (KeyError, FileNotFoundError, ValueError)`) | An unknown name raises `UnboundLocalError`, and the bare `except` turns any error into the "Protocol issue" messagebox plus a device disconnect. | It raises `FileNotFoundError`, but the caller now catches only three exception types. For example, a `PermissionError` on `shutil.copyfile` into `pos_path` is no longer caught, so the automation thread dies without the messagebox or disconnect. | Normally no effect. In the rare I/O-error case, NEW gives no GUI feedback and leaves the devices connected. | Widen the caller to `except Exception` to match REF's catch-all. | #16 (partly) |
| F16 | C | Low | REF:system/fluidics_exchange_system.py:392-507 | NEW:system/fluidics/protocol_loader.py:92 | Logs and GUI text such as `load Fluidics_sequence_HYB protocol\n!` (note the misplaced `!`) or `load Fluidics_sequence_user_defined protocol\n!`. | `load <file_name> protocol!\n`, for example `load Fluidics_sequence_HYB.json protocol!`. | The text in log.txt and the purple GUI panel differs slightly. | None needed. | – |
| F17 | C | Low | REF:system/fluidics_exchange_system.py:262-264 | NEW:system/fluidics_exchange_system.py:286-288 | `pumpVol(vol)` uses `self.pumprate` and prints `pump_speed: <rate>`. | `pumpVol(vol, rate)`, and every caller passes `fluidics.pumprate`. There is no print. | Console output only. | None. | G note |
| F18 | C | Low | REF: none (no `logging`) | NEW:system/fluidics_exchange_system.py:166, 176-189, 253, 276, 429-431, 451-452, 476-477; NEW:device/Pump.py:37, 88; NEW:device/Selector.py:87; NEW:device/Heatingstage.py:126, 137, 205, 236-247; NEW:driver/ismatec_ipc.py:80, 83; NEW:logging_config.py | – | (a) `write_log()` also calls `logger.debug(txt)`. Once `update_log_file(pos_path/log.txt)` runs (NEW:front_end/panels/workspace_panel.py:93, :170), the file handler writes a **second, timestamped copy of every fluidics log line into the same `log.txt`**. (b) Every `logger.info` line ("Step i/n: pumping…", "Selecting reagent…", "Starting heat at voltage…") also shows in the GUI notification panel and the console. Every `logger.warning`/`error` line (for example "Partial heating failure", "All stages failed heating") shows in the red warning panel. (c) In manual fill, `logger.info("Pumping %.2f mL…", volumeToPump)` receives the Spinbox **string**, which produces a "--- Logging error ---" traceback on stderr. That is not fatal. | log.txt content and GUI panels differ. There is no hardware effect. | Optional: drop `logger.debug` from `write_log`, or point the file handler elsewhere. Pass `float(vol)` to the logger. | – |
| F19 | C | Low | REF:system/fluidics_exchange_system.py:114-120 | NEW:system/fluidics_exchange_system.py:161-172 | `write_log` uses a bare `except: pass`. | Catches only `OSError`. | A non-OSError (for example `TypeError` from a bad `pos_path`) would now propagate into `runSequence`. That cannot happen with the current callers, because `pos_path` is always a string. | Optional: `except Exception`. | – |
| F20 | C | Low | REF:device/ has no `__init__.py` | NEW:device/__init__.py:7-10, NEW:driver/__init__.py:6-7 | Importing `device.Pump` loads only Pump. | Importing any `device.*` module loads all four device modules (nidaqmx, serial, `front_end.logwindow`). | No effect: the fluidics system imports all four anyway. | None. | – |
| F21 | D | Low | REF:system/fluidics_exchange_system.py:202-208 vs REF:front_end/Widgets.py:1076-1089 | NEW:system/fluidics_exchange_system.py:274-283 vs NEW:front_end/Widgets.py:721-734 | Cancel never stops the pump. The pump finishes its timed dispense (`V####` already loaded). `FluidicSystem.cancel` is never set to 1 anywhere, so the `if self.cancel==1` guard in `runSequence` is dead code. | Same. | After Cancel, the current pump step keeps dispensing to the end of its timer. | Out of parity scope. List it for the owners. | – |
| F22 | D | Low | REF:device/Selector.py:40-67 | NEW:device/Selector.py:73-123 | Address → port mapping: 1-10 go to selector 1 port N; 11 goes to selector 1 port 11 (`port_address==0`); 12-21 go to selector 1 port 12 and then selector 2 port N-11. Address 22 (≤ `source_limit` = 22) has `selector_need=2` and `port_address=0`, so it goes to selector 1 port 11 (the wrong reagent). | Identical. | No effect today (16 reagents, maximum address 16). | None. | – |
| F23 | D | Low | REF:driver/ismatec_ipc.py:181-184 | NEW:driver/ismatec_ipc.py:219-223 | A `flowTime` outside (0, 59940) min leaves `flowTimeNow` unbound, and `print(flowTimeNow)` raises. | Identical. | Unreachable with the current protocols. | None. | #17 note |
| F24 | D | Low | REF:device/Heatingstage.py:178-182 | NEW:device/Heatingstage.py:280-284 | The initial-range check names `self.dev_name[i]` using the stale loop index `i`, so it always names the last stage. | Identical. | Wrong heater name in the SystemError text. | None. | – |

## 2. Coverage table

### REF:system/fluidics_exchange_system.py → NEW:system/fluidics_exchange_system.py (+ NEW:system/fluidics/*)

| REF item | NEW counterpart | Verdict |
|---|---|---|
| `bcolors` (:19) | :40 | same |
| `get_time` (:32) | :54 (copy also in protocol_loader.py:20) | same |
| `FluidicSourceInfo.__init__` (:37) | :59 | same |
| `FluidicsConstants` (:43-61), bufferms=5 | :68-87 | same |
| `FluidicSystem.__init__` (:64-109) | :108-156. The literals moved to constants: 3 (`FLUIDICS_WAIT_BETWEEN_STEPS_SECONDS`), 5.6 (`DEFAULT_HEAT_TEMP_VOLTAGE`) and 1.5 (`DEFAULT_PUMP_RATE_ML_PER_MIN`), all equal to REF. `SequenceState` IntEnum values equal REF's ints. The two Events were added. | same, plus Events (F01) |
| `write_log` (:114) | :161 | F18, F19 |
| `config_pump` (:122) | :174 | same (pump speed: F04) |
| `config_heater` (:126), 5.7 V | :182, `HEAT_DEFAULT_TEMP_VOLTAGE`=5.7 | same |
| `connect_heater` / `disconnect_heater` (:133/:136) | :192 / :197 | same |
| `connect_pump` (:138) | :201 | same (F04) |
| `is_pump_running` (:142) | :207 | same |
| `disconnect_pump` (:145) | :211 | same |
| `config_selector` / `connect_selector` / `disconnect_selector` (:148-156) | :215-226 | same (port config: F05) |
| `config_relay` / `connect_relay` / `disconnect_relay` (:158-167) | :228-242 | same (relay driver is a stub in both trees). NEW's device panel no longer calls `config_relay`, but it is a no-op. |
| `isPumpRunning` (:171) | :246 | same |
| `Get_Response` (:173) | :248 (`except Exception`) | same |
| `select_bypass` / `select_chamber` (:183-193) | :259-265 (`pass`) | same: REF's `change_relay_state` is already `pass`. The REF calls in Widgets, dropped in NEW, are no-ops (bug report G confirmed). |
| `stopPumping` / `startPumping` (:195-200) | :267-272 | same |
| `cancelSequence` (:202) | :274 (also sets `cycle_done_event`) | uncalled in both; see F02, F21 |
| `setSource` (:212), sleep 2 | :290, `SELECTOR_SETTLE_SECONDS`=2 | same |
| `loadSequence` (:217) | :295 | same |
| `updateStatus` (:221) | :300 | same |
| `startSequence` (:241) | :321 (also clears both Events) | same, F03 |
| `finishSequence` (:255) | :342 (also sets both Events) | uncalled in both; F01 |
| `pumpVol` (:262) | :286 (`rate` argument) | F17 |
| `runSequence` (:266-386): pump time `int(60*vol/pumprate)`+5 s, 2 s poll, `Timer(3)` between steps, `Timer(0)` re-poll while the pump runs, heat, wait, and stopper/other branches, `sleep(5)` at the end | :354-500, identical logic, sleeps and order | F01, F11 (the logger lines are F18) |
| `find_protocol` (:388-516) | :502 → `protocol_loader.load_protocol` / `_load_and_copy` / `PROTOCOL_MAP` | F14, F15, F16 |

### REF:device/Pump.py → NEW:device/Pump.py

| REF item | NEW counterpart | Verdict |
|---|---|---|
| `__init__` | :27 (`driver=None`) | same |
| `initialize` | :31 | **F04** |
| `pumpVolume(vol, rate)`: time = `vol/rate` min | :81 (also passes `vol` to the driver) | same command stream; F13, F18 |
| `setFlowRate_ml_per_min`, `stopPump`, `startPump`, `get_speed`, `isPumpRunning`, `PumpDisconnect`, `GetResponse` | :92-114, :75 | same |
| – | NEW-only `connect`, `disconnect`, `is_connected`, `pump_volume`, `start`, `stop`, `is_running`, `set_flow_rate` (:42-73): ABC interface, no callers | no behavior change |

### REF:device/Selector.py → NEW:device/Selector.py

| REF item | NEW counterpart | Verdict |
|---|---|---|
| `__init__` (relative `config_file/…`, unit 11, pass-through 12, `source_limit`) | :38 (constants 11 and 12 equal REF) | same |
| `connect` / `disconnect` | :49 / :63 | same (COM ports: F05) |
| `set_path` (sleeps 2 / 2 / 3) | :73 (`SELECTOR_SETTLE_SECONDS`=2, plus 3) | same; F22 (both trees) |
| `config_selector` (incorporation buffer → gene primer mix → incorporation buffer) | :125 | same |
| `move` (`/1B<pos>R\r`) | :133 | same |
| – | NEW-only `is_connected` (:68), unused | no behavior change |

### REF:device/Relay.py → NEW:device/Relay.py

| REF item | NEW counterpart | Verdict |
|---|---|---|
| `BUTTON_TEXT_*`, `__init__`, `set_change_blocker`, `connected`, `change_relay_state`, `change_relay_states`, `on_connect_requested`, `quit` (all stubs) | :18-67 | same |
| – | NEW-only `connect`, `disconnect`, `is_connected`, `set_relay`, `set_all_relays` (stubs) | no behavior change |

### REF:device/Heatingstage.py → NEW:device/Heatingstage.py

| REF item | NEW counterpart | Verdict |
|---|---|---|
| `get_time` ([0:16]) | :41 | same |
| `__init__` | :61 | same |
| `connect_heater_group` (ao 0-5 V, DO set to image mode) | :91 | same (DAQ name: F06) |
| `disconnect_heater_group` | :117 | same |
| `start_heat` | :124 | same (+log F18) |
| `end_heat` (0.1 V) | :135 (`HEAT_IDLE_VOLTAGE`=0.1) | same |
| `heat_for_3min_single`: ramp until ≥ temp−0.15, timeout 300 s, 5 s poll; failure if ≥300 s and ≤ temp−0.5; hold `heat_time` s with 10 s poll | :143: constants 0.15, 300, 5, 0.5, 10 all equal REF | **F08, F09**, F10 (cancel side effect) |
| `heat_for_3min` (3 s stagger, join, `sum(status)` check, `end_heat`) | :212 (`HEAT_THREAD_STAGGER_SECONDS`=3) | same (+log F18) |
| `check_temp` | :253 | same |
| `write_log` (no try) | :259 | same |
| `config` (range 1.5-3.0, 15 s pulse, Δ>0.05) | :265 (constants equal REF) | same; F24 (both trees) |
| – | NEW-only `connect`, `disconnect`, `heat` (:76-87), unused | no behavior change |

### REF:driver/ismatec_ipc.py → NEW:driver/ismatec_ipc.py

| REF item | NEW counterpart | Verdict |
|---|---|---|
| `TimeoutError`, `acknowledge`/`start`/`stop` | :27-35 | same |
| `Ismatec.__init__` (9600 8N1, 0.1 s timeout; `#`, `A`, `+tube`, `"0000`, `!`×2) | :52 | same (+logger) |
| `pumpDisconnect`, `checkPumpIdentification`, `isPumpRunning`, `enableRemoteControl`, `setTubingDiameter` | :90-141 | same |
| `setFlowRate` (`!`, `S%06d`) | :143 | same |
| `setFlowVolumeAndRate(flowTime)` | :168 `(flowVolume, flowTime)` | F13, F23 |
| `resetVolumeCounter`, `inquire*`, `startPump`, `stopPump`, `setFlowDirection`, `stopFlow`, `sendToPump`, `sendString`, `getResponse`, `statusCheck` | :230-320 | same |
| REF `from front_end.logwindow import *` (unused) | removed | same |

### REF:driver/kmtronic_relay.py → NEW:driver/kmtronic_relay.py

| REF item | NEW counterpart | Verdict |
|---|---|---|
| `KmtronicRelay.__init__`, `connect`, `disconnect`, `_send_cmd`, `_get_response`, `__del__`, `connected`, `operate_relay`, `operate_relays`, `relay_states`, `_get_relay_states` | same lines, type hints only (the diff shows only annotations) | same (unused in both trees: the relay wrapper is a stub) |

### NEW-only modules
- `device/base.py`: ABCs. Every concrete class implements all its abstract methods, so instantiation works. No behavior.
- `device/__init__.py`, `driver/__init__.py`: eager imports (F20).
- `system/fluidics/sequence_runner.py`: only the `SequenceState` IntEnum. Its docstring mentions a `SequenceRunner` class that does not exist. No behavior.
- `system/fluidics/protocol_loader.py`: F14-F16.
- `constants.py`: every fluidics and heater constant matches REF's literals. `PUMP_WAIT_BUFFER_SECONDS`=5 is unused; `FluidicsConstants.bufferms`=5 is still used. **No constant differs from REF.** The only differing value in this area is the literal 1.2 in `Pump.initialize` (F04), which is not in constants.
- `types_seq.py`: typing only.

### Out-of-area observations (for other reviewers)
- `config_file/scope.json`: `maxproject_drive` is `D:\` in REF and `M:\` in NEW (worktree only; PROD equals REF).
- In both trees, `pump_speed_input` starts as `"\n"` (F12), so operators must type the speed every session.
