"""Fake `nidaqmx` with a thermal model of the Elm heat stages.

Physical setup emulated (from the Elm reference config_file/Heat_stage.json and
the NI devices present on this PC on 2026-10-05):
  Dev1 (PCIe-6323) present, nothing modelled on it
  Dev3 (USB-6001): ao0 = shared heater set-point voltage,
                   port1/line0..2 = per-stage mode (False = heat, True = image),
                   ai0, ai1, ai3 = per-stage temperature sensor voltage
Any other device name (e.g. Dev2) is invalid, as on the real PC.

Sensor model: first-order approach to the set-point voltage while the stage is in
heat mode, back to ambient otherwise. Times are virtual (dryrun.clock).

Like nidaqmx 0.9, a Task that is garbage-collected without close() keeps its
resources reserved.
"""

import math
import sys
import threading
import types

from dryrun import clock, trace

PRESENT_DEVICES = {"Dev1", "Dev3"}
AMBIENT_V = 2.0
TAU_HEAT_S = 30.0
TAU_COOL_S = 60.0
STAGES = [  # (name, do line, ai channel)
    ("heatstage1", "Dev3/port1/line0", "Dev3/ai0"),
    ("heatstage2", "Dev3/port1/line1", "Dev3/ai1"),
    ("heatstage3", "Dev3/port1/line2", "Dev3/ai3"),
]
AO_CHANNEL = "Dev3/ao0"


class DaqError(Exception):
    def __init__(self, message, error_code=-200220, task_name=""):
        super().__init__(message)
        self.error_code = error_code


class _Model:
    def __init__(self):
        self.lock = threading.Lock()
        self.ao = 0.0
        self.do = {line: True for _, line, _ in STAGES}
        self.temp = {ai: AMBIENT_V for _, _, ai in STAGES}
        self.t_last = clock.vnow()
        self.reserved = {}
        self.heat_starts = 0

    def _advance(self):
        now = clock.vnow()
        dt = max(0.0, now - self.t_last)
        self.t_last = now
        if dt == 0:
            return
        for _, line, ai in STAGES:
            heating = self.do[line] is False
            target = self.ao if heating else AMBIENT_V
            tau = TAU_HEAT_S if heating else TAU_COOL_S
            self.temp[ai] = target + (self.temp[ai] - target) * math.exp(-dt / tau)

    def write(self, channel, value):
        with self.lock:
            self._advance()
            if channel == AO_CHANNEL:
                if float(value) >= 5.0:
                    self.heat_starts += 1
                self.ao = float(value)
            elif channel in self.do:
                self.do[channel] = bool(value)

    def read(self, channel):
        with self.lock:
            self._advance()
            return round(self.temp.get(channel, 0.0), 4)


MODEL = None
# Optional injected fault, set by the scenario: the first read of `channel` during the
# `heat_start`-th heat start (counting every set-point write >= 5 V, including the heater
# self-test in device configuration) fails once.
FAULT = {}


def _check_device(name):
    dev = name.split("/")[0]
    if dev not in PRESENT_DEVICES:
        trace.record("daq_error", channel=name, reason="invalid device")
        raise DaqError(f"Device identifier is invalid.\nDevice Specified: {dev}\nSuggested Device(s): "
                       f"{', '.join(sorted(PRESENT_DEVICES))}", error_code=-200220)


class _ChannelCollection:
    def __init__(self, task, kind):
        self._task = task
        self._kind = kind

    def _add(self, physical_channel, **kwargs):
        _check_device(physical_channel)
        self._task._channels.append((self._kind, physical_channel))
        trace.record("daq_add_channel", task=self._task.name, ch_kind=self._kind, channel=physical_channel)

    def add_ao_voltage_chan(self, physical_channel, name_to_assign_to_channel="", min_val=-10.0, max_val=10.0, **kw):
        self._add(physical_channel, min_val=min_val, max_val=max_val)

    def add_ai_voltage_chan(self, physical_channel, *args, **kw):
        self._add(physical_channel)

    def add_do_chan(self, lines, *args, **kw):
        self._add(lines)


class Task:
    _counter = 0

    def __init__(self, new_task_name=""):
        Task._counter += 1
        self.name = new_task_name or f"_unnamedTask<{Task._counter}>"
        self._channels = []
        self._closed = False
        self._reserved = False
        self.ao_channels = _ChannelCollection(self, "ao")
        self.ai_channels = _ChannelCollection(self, "ai")
        self.do_channels = _ChannelCollection(self, "do")

    def _reserve(self):
        if self._reserved:
            return
        with MODEL.lock:
            for kind, ch in self._channels:
                owner = MODEL.reserved.get(ch)
                if owner is not None and owner is not self and not owner._closed:
                    trace.record("daq_error", channel=ch, reason="resource reserved", task=self.name)
                    raise DaqError(f"The specified resource is reserved. The operation could not be "
                                   f"completed as specified.\nChannel: {ch}", error_code=-50103)
            for kind, ch in self._channels:
                MODEL.reserved[ch] = self
        self._reserved = True

    def start(self):
        self._reserve()
        trace.record("daq_start", task=self.name)

    def write(self, data, auto_start=True, timeout=10.0):
        if self._closed:
            raise DaqError("Task specified is invalid or does not exist.", error_code=-200088)
        self._reserve()
        for kind, ch in self._channels:
            MODEL.write(ch, data)
            trace.record("daq_write", ch_kind=kind, channel=ch, value=data)
        return 1

    def read(self, number_of_samples_per_channel=None, timeout=10.0):
        if self._closed:
            raise DaqError("Task specified is invalid or does not exist.", error_code=-200088)
        self._reserve()
        for kind, ch in self._channels:
            if (kind == "ai" and FAULT.get("channel") == ch and not FAULT.get("fired")
                    and MODEL.heat_starts >= FAULT.get("heat_start", 10 ** 9)):
                FAULT["fired"] = True
                trace.record("daq_error", channel=ch, reason="injected read fault")
                raise DaqError("Injected fault: the hardware did not respond in time.", error_code=-200474)
        vals = [MODEL.read(ch) for kind, ch in self._channels if kind == "ai"]
        return vals[0] if len(vals) == 1 else vals

    def stop(self):
        pass

    def close(self):
        if not self._closed:
            self._closed = True
            with MODEL.lock:
                for kind, ch in self._channels:
                    if MODEL.reserved.get(ch) is self:
                        del MODEL.reserved[ch]
            trace.record("daq_close", task=self.name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        if not self._closed:
            try:
                trace.record("daq_task_gc_not_closed", task=self.name)
            except Exception:
                pass


class _Device:
    def __init__(self, name):
        self.name = name


class _System:
    @staticmethod
    def local():
        s = _System()
        s.devices = [_Device(d) for d in sorted(PRESENT_DEVICES)]
        return s


def reserved_channels():
    with MODEL.lock:
        return sorted(ch for ch, t in MODEL.reserved.items() if not t._closed)


def install():
    global MODEL
    MODEL = _Model()
    mod = types.ModuleType("nidaqmx")
    mod.__dryrun_fake__ = True
    mod.Task = Task
    mod.DaqError = DaqError
    errors = types.ModuleType("nidaqmx.errors")
    errors.__dryrun_fake__ = True
    errors.DaqError = DaqError
    system = types.ModuleType("nidaqmx.system")
    system.__dryrun_fake__ = True
    system.System = _System
    mod.errors = errors
    mod.system = system
    sys.modules["nidaqmx"] = mod
    sys.modules["nidaqmx.errors"] = errors
    sys.modules["nidaqmx.system"] = system
    return mod
