"""Scenarios: experiment-folder setup (done by run.py) and GUI steps (done by runner.py).

Each scenario drives the program the way an operator would, by calling the same
handlers the buttons call, on the Tk thread.
"""

import json
import os

from dryrun import clock, gui, trace

# Four corner positions of one slice (Elm-like coordinates). 100 um apart in x
# so the tiler makes a 2 x 1 tile grid with the test image width.
POSITIONS = [
    ("Pos0", 52900.0, -19400.0, 3659.25, 200.0),
    ("Pos1", 53000.0, -19400.0, 3660.40, 200.0),
    ("Pos2", 53000.0, -19400.0, 3661.10, 200.0),
    ("Pos3", 52900.0, -19400.0, 3660.00, 200.0),
]

DEVICE_GROUPS = ["pump group", "relay group", "heater group", "selector group"]

SCENARIOS = {
    "auto_full": {
        "description": "Automated run: fluidics + focus + max projection over several cycles, uploads off.",
        "process": ["Fluidics_sequence_geneseq01", "imagecycle00", "imagecycle_geneseq01",
                    "Fluidics_sequence_geneseq02", "imagecycle_geneseq02",
                    "Fluidics_sequence_strip", "Fluidics_sequence_HYB", "imagecycle_hyb01"],
        "server": 0, "aws": 0, "steps": "auto",
    },
    "imaging_only": {
        "description": "Automated run with imaging steps only (no fluidics), uploads off.",
        "process": ["imagecycle00", "imagecycle_geneseq01"],
        "server": 0, "aws": 0, "steps": "auto",
    },
    "imaging_uploads": {
        "description": "Automated run with imaging steps only, 'Send to storage server' and 'upload to AWS' ticked.",
        "process": ["imagecycle00", "imagecycle_geneseq01"],
        "server": 1, "aws": 1, "steps": "auto",
    },
    "prime_wash": {
        "description": "Prime (fill all lines + 4 mL PBST in-chamber flush), then Wash.",
        "process": ["imagecycle00"],
        "server": 0, "aws": 0, "steps": "prime_wash",
    },
    "cancel_restart": {
        "description": "Start an automated run, press Cancel during the first fluidics step, then press Start again.",
        "process": ["Fluidics_sequence_geneseq01", "imagecycle00"],
        "server": 0, "aws": 0, "steps": "cancel_restart",
    },
}


# ---------------------------------------------------------------- folder setup

def _pos_entry(label, x, y, z, piezo):
    def dev(name, values):
        return {"Device": {"type": "STRING", "scalar": name},
                "Position_um": {"type": "DOUBLE", "array": values}}
    return {
        "DefaultXYStage": {"type": "STRING", "scalar": "XYStage"},
        "DefaultZStage": {"type": "STRING", "scalar": "DA Z Stage"},
        "DevicePositions": {"type": "PROPERTY_MAP", "array": [dev("ZDrive", [z]), dev("DA Z Stage", [piezo]),
                                                               dev("XYStage", [x, y])]},
        "GridCol": {"type": "INTEGER", "scalar": 0},
        "GridRow": {"type": "INTEGER", "scalar": 0},
        "Label": {"type": "STRING", "scalar": label},
        "Properties": {"type": "PROPERTY_MAP", "scalar": {}},
    }


def setup_experiment(exp_dir, scenario):
    os.makedirs(exp_dir, exist_ok=True)
    with open(os.path.join(exp_dir, "protocol.csv"), "w", newline="") as f:
        f.write("process\n" + "\n".join(SCENARIOS[scenario]["process"]) + "\n")
    pos = {"encoding": "UTF-8", "format": "Micro-Manager Property Map", "major_version": 2, "minor_version": 0,
           "map": {"StagePositions": {"type": "PROPERTY_MAP",
                                      "array": [_pos_entry(*p) for p in POSITIONS]}}}
    with open(os.path.join(exp_dir, "cycle00.pos"), "w") as f:
        json.dump(pos, f, indent=2)


# ---------------------------------------------------------------- GUI helpers

def _set_entry(widget, text):
    widget.delete(0, "end")
    widget.insert(0, text)


def log_text(exp_dir):
    try:
        with open(os.path.join(exp_dir, "log.txt"), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def wait_until(pred, virtual_timeout, what):
    """Poll pred() until true; give up after virtual_timeout virtual seconds."""
    t_end = clock.vnow() + virtual_timeout
    while clock.vnow() < t_end:
        if pred():
            trace.record("driver", step=f"reached: {what}")
            return True
        clock.REAL_SLEEP(0.2)
    trace.record("driver", step=f"timed out waiting for: {what}")
    return False


def settle(virtual_quiet=300, virtual_max=3600):
    """Wait until no new trace events for virtual_quiet seconds."""
    t_end = clock.vnow() + virtual_max
    last, t_last = trace.count(), clock.vnow()
    while clock.vnow() < t_end:
        clock.REAL_SLEEP(0.2)
        n = trace.count()
        if n != last:
            last, t_last = n, clock.vnow()
        elif clock.vnow() - t_last >= virtual_quiet:
            return


def common_setup(app, ctx):
    sc = SCENARIOS[ctx["scenario"]]
    trace.record("driver", step="fill experiment fields")

    def fill():
        _set_entry(app.work_path_field_auto, ctx["exp_dir"])
        _set_entry(app.slice_number_field_auto, "1")
        _set_entry(app.pump_speed_input, ctx["pump_speed"])
        app.mock_alignment.set(1)  # real Elm runs always use "Skip alignment"
        app.change_server_value.set(sc["server"])
        app.upload_aws_value.set(sc["aws"])
    gui.call(fill)
    trace.record("driver", step="create experiment")
    gui.call(app.create_exp_auto)
    for group in DEVICE_GROUPS:
        trace.record("driver", step=f"configure {group}")
        gui.call(app.config_device)
        gui.call(lambda g=group: app.device_dropdown.set(g))
        gui.call(app.config_dev)
    trace.set_extra("device_status", dict(getattr(app, "device_status", {})))


def run_auto(app, ctx):
    common_setup(app, ctx)
    trace.record("driver", step="press Start, confirm pump speed")
    gui.call(app.start_btn_check)
    gui.call(app.start_btn_handler)
    ok = wait_until(lambda: "All rounds finished!" in log_text(ctx["exp_dir"]), 72 * 3600, "All rounds finished")
    if ok:
        wait_until(lambda: gui.call(lambda: str(app.cancel_sequence_btn["state"])) == "disabled", 6 * 3600,
                   "run finished (Cancel button disabled)")
    settle()


def run_prime_wash(app, ctx):
    common_setup(app, ctx)
    trace.record("driver", step="press Prime, confirm pump speed")
    gui.call(app.prime_btn_check)
    gui.call(app.prime_btn_handler)
    wait_until(lambda: log_text(ctx["exp_dir"]).count("Wash/Prime line Done!") >= 1, 6 * 3600, "Prime done")
    settle()
    trace.record("driver", step="press Wash, confirm pump speed")
    gui.call(app.wash_btn_check)
    gui.call(app.wash_btn_handler)
    wait_until(lambda: log_text(ctx["exp_dir"]).count("Wash/Prime line Done!") >= 2, 6 * 3600, "Wash done")
    settle()


def run_cancel_restart(app, ctx):
    common_setup(app, ctx)
    trace.record("driver", step="press Start, confirm pump speed")
    gui.call(app.start_btn_check)
    gui.call(app.start_btn_handler)
    wait_until(lambda: sum(1 for e in trace.events() if e["kind"] == "pump_dispense") >= 2, 6 * 3600,
               "second pump step started")
    clock.sleep(30)
    trace.record("driver", step="press Cancel")
    gui.call(app.cancel_btn_handler)
    settle(virtual_quiet=600, virtual_max=4 * 3600)
    trace.set_extra("after_cancel", {"open_ports": _ports(), "reserved_daq": _daq()})
    trace.record("driver", step="press Start again, confirm pump speed")
    gui.call(app.start_btn_check)
    gui.call(app.start_btn_handler)
    settle(virtual_quiet=600, virtual_max=2 * 3600)


def _ports():
    from dryrun import fake_serial
    return fake_serial.open_ports()


def _daq():
    from dryrun import fake_nidaqmx
    return fake_nidaqmx.reserved_channels()


STEPS = {"auto": run_auto, "prime_wash": run_prime_wash, "cancel_restart": run_cancel_restart}
