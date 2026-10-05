"""Run ONE program tree through ONE scenario with fake hardware. Invoked by run.py.

    python -m dryrun.runner --tree <copied code dir> --scenario <name> --exp <exp dir>
                            --maxdrive <dir> --out <trace.json> [--speed 100]

The tree must be a scratch copy: the program writes into its own folder.
"""

import argparse
import os
import sys
import threading
import traceback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--exp", required=True)
    ap.add_argument("--maxdrive", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--speed", type=float, default=100.0)
    ap.add_argument("--pump-speed", default="1.58")
    ap.add_argument("--imwidth", type=int, default=1024)
    ap.add_argument("--stall", type=float, default=3 * 3600, help="virtual seconds without progress = hang")
    ap.add_argument("--max-virtual", type=float, default=96 * 3600)
    ap.add_argument("--mm-config", default=None,
                    help="use REAL pycromanager with a headless Micro-Manager started on this (demo) config")
    args = ap.parse_args()

    tree = os.path.abspath(args.tree)
    exp_dir = os.path.abspath(args.exp)

    # 1. Fakes first, then the guard that blocks every real hardware module.
    from dryrun import guard, fake_serial, fake_nidaqmx, fake_pycromanager
    fake_serial.install()
    fake_nidaqmx.install()
    if args.mm_config:
        # Micro-Manager demo run: the microscope side is the real pycromanager talking to a
        # headless Micro-Manager with demo devices; pump, selectors and heaters stay faked.
        guard.BLOCKED = ("serial", "nidaqmx")
    else:
        fake_pycromanager.install()
    guard.install()

    # 2. Heavy libraries bind the real datetime class before the clock is patched.
    import numpy, pandas, cv2, tifffile, skimage.io, scipy, pytz  # noqa: F401
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot  # noqa: F401

    from dryrun import clock, trace, images, fake_os, gui, scenarios
    clock.install(args.speed)
    fake_nidaqmx.MODEL.t_last = clock.vnow()
    if args.mm_config:
        start_demo_micromanager(args.mm_config)  # before fake_os: it launches the Java process
    fake_os.install()
    images.IMWIDTH = args.imwidth
    images.set_surfaces([(p[0], p[3], p[4]) for p in scenarios.POSITIONS])

    trace.set_extra("meta", {"tree": tree, "scenario": args.scenario, "exp": exp_dir, "speed": args.speed,
                             "maxdrive": os.path.abspath(args.maxdrive), "pump_speed": args.pump_speed})

    def thread_excepthook(a):
        trace.record("exception", where=f"thread {a.thread.name if a.thread else '?'}", error=repr(a.exc_value),
                     traceback="".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback))[-4000:])
    threading.excepthook = thread_excepthook

    finished = clock.REAL_EVENT()

    def finalize(status, detail=None):
        if finished.is_set():
            return
        finished.set()
        try:
            trace.set_extra("final", collect_final(tree, exp_dir, os.path.abspath(args.maxdrive)))
        except Exception as e:
            trace.set_extra("final_error", repr(e))
        trace.set_extra("guard_problems", guard.check())
        trace.dump(args.out, status=status, detail=detail, virtual_end=round(clock.vnow(), 1))
        sys.stdout.flush()
        if args.mm_config:
            stop_demo_micromanager()
        os._exit(0)

    ctx = {"scenario": args.scenario, "exp_dir": exp_dir, "pump_speed": args.pump_speed}

    def driver():
        app = None
        try:
            app = program_globals["my_widges"]
            scenarios.STEPS[scenarios.SCENARIOS[args.scenario]["steps"]](app, ctx)
            finalize("completed")
        except Exception:
            trace.record("exception", where="driver", traceback=traceback.format_exc()[-4000:])
            finalize("driver_error", traceback.format_exc()[-2000:])

    def watchdog():
        last_sig, t_last = None, clock.vnow()
        while not finished.is_set():
            clock.REAL_SLEEP(1.0)
            sig = (trace.count(), len(scenarios.log_text(exp_dir)))
            if sig != last_sig:
                last_sig, t_last = sig, clock.vnow()
            idle = clock.vnow() - t_last
            if idle >= args.stall or clock.vnow() >= args.max_virtual:
                busy = [t.name for t in threading.enumerate()
                        if t is not threading.main_thread() and not t.name.startswith("dryrun-")]
                if busy:
                    trace.record("hang", idle_virtual_s=round(idle, 1), threads=busy)
                    finalize("hang", f"no progress for {idle / 3600:.1f} virtual hours; program threads waiting: {busy}")
                else:
                    trace.record("idle", idle_virtual_s=round(idle, 1))
                    finalize("stopped", f"program idle for {idle / 3600:.1f} virtual hours with nothing running "
                                        f"(the scenario's next milestone never came)")

    def on_mainloop():
        threading.Thread(target=driver, name="dryrun-driver", daemon=True).start()
        threading.Thread(target=watchdog, name="dryrun-watchdog", daemon=True).start()

    gui.install(on_mainloop)

    # 3. Run the program's own entry point, from its own folder.
    os.chdir(tree)
    sys.path.insert(0, tree)
    program_globals = {"__name__": "__main__", "__file__": os.path.join(tree, "mainwindow.py")}
    with open(os.path.join(tree, "mainwindow.py"), encoding="utf-8") as f:
        code = compile(f.read(), os.path.join(tree, "mainwindow.py"), "exec")
    try:
        exec(code, program_globals)
    except SystemExit:
        pass
    except Exception:
        trace.record("exception", where="mainwindow", traceback=traceback.format_exc()[-4000:])
        finalize("startup_error", traceback.format_exc()[-2000:])
    finalize("mainloop_exited")


MM_APP = r"C:\Program Files\Micro-Manager-2.0"


def start_demo_micromanager(cfg):
    """Start a headless Micro-Manager (Java) with a demo config, refusing if one is already listening."""
    import socket
    from dryrun import trace
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 4827)) == 0:
            raise RuntimeError("Something already listens on port 4827 (a running Micro-Manager?). "
                               "Refusing to start: the program would talk to it instead of the demo.")
    from pycromanager import start_headless
    start_headless(MM_APP, os.path.abspath(cfg), port=4827)
    from pycromanager import Core
    core = Core()
    trace.set_extra("micromanager_demo", {"config": os.path.abspath(cfg), "camera": core.get_camera_device(),
                                          "focus": core.get_focus_device(),
                                          "xy": core.get_xy_stage_device()})


def stop_demo_micromanager():
    try:
        from pycromanager.headless import stop_headless
        stop_headless()
    except Exception as e:
        print(f"could not stop headless Micro-Manager: {e}")


def collect_final(tree, exp_dir, maxdrive):
    from dryrun import fake_serial, fake_nidaqmx, gui, clock
    out = {"open_ports": fake_serial.open_ports(), "reserved_daq": fake_nidaqmx.reserved_channels()}
    # program threads still alive, with where they are
    frames = sys._current_frames()
    threads = []
    for t in threading.enumerate():
        if t.name.startswith("dryrun-") or t is threading.main_thread():
            continue
        fr = frames.get(t.ident)
        stack = traceback.format_stack(fr) if fr else []
        prog = [s for s in stack if tree.lower() in s.lower()]
        threads.append({"name": t.name, "daemon": t.daemon, "stack": (prog or stack)[-6:]})
    out["threads"] = threads
    out["files_exp"] = list_files(exp_dir)
    out["files_maxdrive"] = list_files(maxdrive)
    stray = []
    for name in os.listdir(tree):
        p = os.path.join(tree, name)
        if os.path.isfile(p) and (name.lower().endswith(".tif") or name == "aixintest.csv"):
            stray.append(name)
    out["files_in_program_folder"] = sorted(stray)
    texts = {}
    for name in os.listdir(exp_dir):
        p = os.path.join(exp_dir, name)
        if os.path.isfile(p) and name.lower().endswith((".csv", ".pos", ".json", ".txt")) and os.path.getsize(p) < 2_000_000:
            with open(p, encoding="utf-8", errors="replace") as f:
                texts[name] = f.read()
    out["exp_text_files"] = texts
    try:
        out["gui_text"] = gui.call(gui.all_text_widgets, timeout=30)
    except Exception as e:
        out["gui_text_error"] = repr(e)
    with open(os.path.join(tree, "device", "pump_speed_calibration.txt"), "rb") as f:
        out["pump_speed_calibration_bytes"] = repr(f.read())
    return out


def list_files(root):
    res = {}
    if not os.path.isdir(root):
        return res
    for dp, dns, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            res[os.path.relpath(p, root).replace("\\", "/")] = os.path.getsize(p)
        for dn in dns:
            p = os.path.join(dp, dn)
            if not os.listdir(p):
                res[os.path.relpath(p, root).replace("\\", "/") + "/"] = 0
    return res


if __name__ == "__main__":
    main()
