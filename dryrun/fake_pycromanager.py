"""Fake `pycromanager`: Core records stage/shutter calls, Acquisition writes NDTiff data.

One shared microscope state backs every Core() instance (the program creates
several). Acquisition follows the pycromanager naming rule `<name>_<k>` with the
first free k starting at 1, and writes the same files the program reads back.
"""

import os
import sys
import threading
import types

from dryrun import clock, images, ndtiff_writer, trace

FRAME_TIME_S = 0.05  # virtual seconds per frame (exposure + readout)


class _Scope:
    def __init__(self):
        self.lock = threading.Lock()
        self.positions = {"ZDrive": 3600.0, "DA Z Stage": 100.0}
        self.xy = (0.0, 0.0)
        self.shutter = False


SCOPE = _Scope()

# Device properties as strings, like MMCore; piezo travel from Elm's MMConfig_Ti2E-xc2.cfg.
PROPERTIES = {
    ("DA Z Stage", "Stage Low Position(um)"): "0.0000",
    ("DA Z Stage", "Stage High Position(um)"): "400.0000",
}


class Core:
    def __init__(self, *args, **kwargs):
        trace.record("core_new")

    def set_position(self, *args):
        if len(args) == 2:
            dev, val = args
        else:
            dev, val = "<focus>", args[0]
        with SCOPE.lock:
            SCOPE.positions[dev] = float(val)
        trace.record("core", call="set_position", dev=dev, value=round(float(val), 3))

    def set_xy_position(self, *args):
        x, y = args[-2], args[-1]
        with SCOPE.lock:
            SCOPE.xy = (float(x), float(y))
        trace.record("core", call="set_xy_position", x=round(float(x), 2), y=round(float(y), 2))

    def wait_for_device(self, dev):
        trace.record("core", call="wait_for_device", dev=dev)

    def stop_stage_sequence(self, dev):
        trace.record("core", call="stop_stage_sequence", dev=dev)

    def set_shutter_open(self, *args):
        trace.record("core", call="set_shutter_open", args=list(args))

    def get_property(self, dev, prop):
        trace.record("core", call="get_property", dev=dev, args=[prop])
        return PROPERTIES.get((dev, prop))

    def get_position(self, dev=None):
        with SCOPE.lock:
            return SCOPE.positions.get(dev or "DA Z Stage", 0.0)

    def __getattr__(self, item):
        def _unknown(*args, **kwargs):
            trace.record("core_unexpected_call", call=item, args=[str(a) for a in args])
            return None
        return _unknown


def _next_dataset_dir(directory, name):
    k = 1
    while os.path.exists(os.path.join(directory, f"{name}_{k}")):
        k += 1
    return os.path.join(directory, f"{name}_{k}")


class Acquisition:
    def __init__(self, directory=None, name=None, show_display=True, **kwargs):
        self.directory = os.path.abspath(directory)
        self.name = name
        self.events = []
        self.finished = False
        self.extra_kwargs = sorted(kwargs)

    def __enter__(self):
        return self

    def acquire(self, events):
        if isinstance(events, dict):
            events = [events]
        self.events.extend(events)

    def mark_finished(self):
        self.finished = True

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._write()
        return False

    def _write(self):
        out_dir = _next_dataset_dir(self.directory, self.name)
        is_focus = os.path.basename(self.directory).lower().startswith("focus")
        with SCOPE.lock:
            zdrive = SCOPE.positions.get("ZDrive", 0.0)
            xy = SCOPE.xy
        surface = images.begin_focus_acquisition(self.name) if is_focus else None
        frames, seen = [], {}
        best = None
        for i, ev in enumerate(self.events):
            axes = dict(ev.get("axes", {}))
            ch = axes.get("channel", ev.get("config_group", ["", ""])[-1])
            z = float(ev.get("z", SCOPE.positions.get("DA Z Stage", 0.0)))
            key = (ch, axes.get("z"))
            occ = seen.get(key, 0)
            seen[key] = occ + 1
            if is_focus:
                defocus = zdrive + z - surface
                gain = images.SECOND_PASS_GAIN ** occ
                img = images.render(self.name, ch, defocus, gain=gain,
                                    noise_seed=images._seed(self.directory, self.name, i))
                if best is None or abs(defocus) < best[1]:
                    best = (z, abs(defocus))
            else:
                img = images.render_tile(self.name, ch)
            md = {"Axes": axes, "Channel": "Default", "Exposure": ev.get("exposure"),
                  "ZPosition_um_Intended": z, "Core-Focus": "DA Z Stage"}
            frames.append((axes, img, md))
        clock.sleep(FRAME_TIME_S * len(frames))
        ndtiff_writer.write_dataset(out_dir, self.name, frames)
        zs = [round(float(e.get("z", 0)), 3) for e in self.events]
        chans = []
        for e in self.events:
            c = e.get("axes", {}).get("channel")
            if c not in chans:
                chans.append(c)
        trace.record("acquisition", directory=self.directory, dataset=os.path.basename(out_dir), name=self.name,
                     n_events=len(self.events), channels=chans,
                     z_first=zs[0] if zs else None, z_last=zs[-1] if zs else None,
                     exposures=sorted({str(e.get("exposure")) for e in self.events}),
                     zdrive=round(zdrive, 3), xy=[round(xy[0], 1), round(xy[1], 1)],
                     surface=None if surface is None else round(surface, 3),
                     true_best_piezo=None if best is None else round(best[0], 3),
                     kwargs=self.extra_kwargs)


def multi_d_acquisition_events(*args, **kwargs):
    trace.record("core_unexpected_call", call="multi_d_acquisition_events")
    return []


def install():
    mod = types.ModuleType("pycromanager")
    mod.__dryrun_fake__ = True
    mod.Core = Core
    mod.Acquisition = Acquisition
    mod.multi_d_acquisition_events = multi_d_acquisition_events
    sys.modules["pycromanager"] = mod
    return mod
