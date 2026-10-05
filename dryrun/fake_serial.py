"""Fake `serial` (pyserial) module with emulators for the Elm serial devices.

Physical setup emulated (Elm, as seen on this PC on 2026-10-05):
  COM9   Ismatec IPC pump (pump config; the KMtronic relay config also names COM9
         but the relay driver never opens a port)
  COM10  Elveflow MUX distributor 2
  COM11  Elveflow MUX distributor 1
  COM6   another FTDI device that Micro-Manager holds open -> "Access is denied"
  COM1, COM2, COM4  present, unrelated (accept writes, never answer)
Any other port does not exist.

Like Windows, a port can be open only once at a time. Like pyserial, a Serial
object that is garbage-collected closes its port.
"""

import sys
import threading
import types
import weakref

from dryrun import clock, trace

PARITY_NONE = "N"
EIGHTBITS = 8
STOPBITS_ONE = 1


class SerialException(IOError):
    pass


class SerialTimeoutException(SerialException):
    pass


_open_lock = threading.Lock()
_open_ports = {}


class IsmatecEmulator:
    """Ismatec IPC protocol subset used by driver/ismatec_ipc.py."""

    MAX_RATE = 10.50  # mL/min at 100 %, reported by '!'

    def __init__(self, port):
        self.port = port
        self.pct = 100.0
        self.mode = None
        self.duration_s = None
        self.run_until = None
        self.running_forever = False
        self.remote = False

    def is_running(self):
        if self.running_forever:
            return True
        return self.run_until is not None and clock.vnow() < self.run_until

    def handle(self, raw):
        text = raw.decode(errors="replace")
        if not text.endswith("\r") or len(text) < 2:
            trace.record("pump_bad_command", dev="pump", raw=text)
            return b""
        addr, cmd = text[0], text[1:-1]
        resp = "*"
        meaning = None
        if cmd == "#":
            resp = "IPC 405 dryrun"
            meaning = "identify"
        elif cmd == "!":
            resp = "%.2f ml/min" % self.MAX_RATE
            meaning = "query calibrated max rate"
        elif cmd == "?":
            resp = "%.2f" % self.MAX_RATE
        elif cmd == "E":
            resp = "+" if self.is_running() else "-"
            meaning = "is running?"
        elif cmd == "A":
            self.remote = False
            meaning = "manual control"
        elif cmd == "B" or cmd.startswith("DA-"):
            self.remote = True
            meaning = "remote control"
        elif cmd.startswith("+"):
            meaning = "tubing %s" % cmd[1:]
        elif cmd.startswith('"'):
            meaning = "zero cycles"
        elif cmd.startswith("S"):
            self.pct = int(cmd[1:]) / 100.0
            meaning = "set rate %.2f%% = %.3f mL/min" % (self.pct, self.pct * self.MAX_RATE / 100.0)
        elif cmd == "N":
            self.mode = "time"
            meaning = "time-dispense mode"
        elif cmd == "W":
            meaning = "reset volume counter"
        elif cmd.startswith("VM"):
            self.duration_s = int(cmd[2:]) * 60.0
            meaning = "dispense time %d min" % int(cmd[2:])
        elif cmd.startswith("VH"):
            self.duration_s = int(cmd[2:]) * 3600.0
            meaning = "dispense time %d h" % int(cmd[2:])
        elif cmd.startswith("V"):
            self.duration_s = int(cmd[1:]) / 10.0
            meaning = "dispense time %.1f s" % self.duration_s
        elif cmd == "H":
            if self.mode == "time" and self.duration_s:
                self.run_until = clock.vnow() + self.duration_s
                self.running_forever = False
                flow = self.pct * self.MAX_RATE / 100.0
                meaning = "start"
                trace.record("pump_dispense", dev="pump", duration_s=round(self.duration_s, 1),
                             rate_ml_min=round(flow, 3), volume_ml=round(flow * self.duration_s / 60.0, 3))
            else:
                self.running_forever = True
                meaning = "start (continuous)"
        elif cmd == "I":
            was = self.is_running()
            self.run_until = None
            self.running_forever = False
            meaning = "stop" + (" (was running)" if was else "")
        elif cmd in ("J", "K"):
            meaning = "direction"
        elif cmd == ":":
            resp = "0.00"
        else:
            meaning = "unknown"
        if cmd not in ("E",):
            trace.record("pump", dev="pump", cmd=cmd, meaning=meaning)
        return resp.encode()


class MuxEmulator:
    """Elveflow MUX distributor: write-only '/1B<port>R\\r' moves."""

    def __init__(self, port, name):
        self.port = port
        self.name = name
        self.position = None

    def handle(self, raw):
        text = raw.decode(errors="replace")
        if text.startswith("/") and "B" in text and text.endswith("R\r"):
            pos = int(text[text.index("B") + 1:-2])
            self.position = pos
            trace.record("selector", dev=self.name, port=self.port, position=pos)
        else:
            trace.record("selector_bad_command", dev=self.name, port=self.port, raw=text)
        return b""


class SilentDevice:
    def __init__(self, port):
        self.port = port

    def handle(self, raw):
        trace.record("serial_write_unknown_device", port=self.port, raw=raw.decode(errors="replace"))
        return b""


_emulators = {
    "COM9": IsmatecEmulator("COM9"),
    "COM10": MuxEmulator("COM10", "selector2"),
    "COM11": MuxEmulator("COM11", "selector1"),
    "COM1": SilentDevice("COM1"),
    "COM2": SilentDevice("COM2"),
    "COM4": SilentDevice("COM4"),
}
_busy = {"COM6": "PermissionError(13, 'Access is denied.', None, 5)"}


class Serial:
    def __init__(self, port=None, baudrate=9600, bytesize=EIGHTBITS, parity=PARITY_NONE,
                 stopbits=STOPBITS_ONE, timeout=None, **kwargs):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._buf = b""
        self.is_open = False
        if port is not None:
            self.open()

    def open(self):
        port = str(self.port).upper()
        if port in _busy:
            trace.record("serial_open_failed", port=port, reason="busy")
            raise SerialException(f"could not open port '{self.port}': {_busy[port]}")
        if port not in _emulators:
            trace.record("serial_open_failed", port=port, reason="missing")
            raise SerialException(
                f"could not open port '{self.port}': FileNotFoundError(2, 'The system cannot find the file specified.', None, 2)")
        with _open_lock:
            holder = _open_ports.get(port)
            if holder is not None and holder() is not None and holder().is_open:
                trace.record("serial_open_failed", port=port, reason="already open")
                raise SerialException(f"could not open port '{self.port}': PermissionError(13, 'Access is denied.', None, 5)")
            # weak reference: like the OS handle in pyserial, the port is freed when the object is collected
            _open_ports[port] = weakref.ref(self)
        self.is_open = True
        self._dev = _emulators[port]
        trace.record("serial_open", port=port)

    def write(self, data):
        if not self.is_open:
            raise SerialException("Attempting to use a port that is not open")
        if isinstance(data, str):
            data = data.encode()
        self._buf += self._dev.handle(data)
        return len(data)

    def readline(self):
        out, self._buf = self._buf, b""
        return out

    def read(self, size=1):
        out, self._buf = self._buf[:size], self._buf[size:]
        return out

    @property
    def in_waiting(self):
        return len(self._buf)

    def reset_input_buffer(self):
        self._buf = b""

    flushInput = reset_input_buffer

    def close(self):
        if self.is_open:
            port = str(self.port).upper()
            with _open_lock:
                ref = _open_ports.get(port)
                if ref is not None and ref() in (self, None):
                    del _open_ports[port]
            self.is_open = False
            trace.record("serial_close", port=port)

    def __del__(self):
        # pyserial's SerialBase is an io.RawIOBase, whose finalizer closes the port.
        try:
            if self.is_open:
                trace.record("serial_close_by_gc", port=str(self.port).upper())
            self.close()
        except Exception:
            pass


def open_ports():
    with _open_lock:
        return sorted(p for p, r in _open_ports.items() if r() is not None and r().is_open)


def install():
    mod = types.ModuleType("serial")
    mod.__dryrun_fake__ = True
    for name in ("Serial", "SerialException", "SerialTimeoutException", "PARITY_NONE", "EIGHTBITS",
                 "STOPBITS_ONE"):
        setattr(mod, name, globals()[name])
    mod.PARITY_EVEN, mod.PARITY_ODD = "E", "O"
    mod.SEVENBITS, mod.STOPBITS_TWO = 7, 2
    sys.modules["serial"] = mod
    return mod
