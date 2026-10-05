"""Thread-safe event recorder shared by all fakes."""

import json
import threading

from dryrun import clock

_lock = threading.Lock()
_events = []
_extra = {}


def record(kind, **fields):
    """Append one event. `t` is virtual seconds since the run started."""
    ev = {"t": round(clock.vnow(), 3), "kind": kind, "thread": threading.current_thread().name}
    ev.update(fields)
    with _lock:
        _events.append(ev)
    return ev


def count():
    with _lock:
        return len(_events)


def events():
    with _lock:
        return list(_events)


def set_extra(key, value):
    with _lock:
        _extra[key] = value


def dump(path, **top):
    with _lock:
        data = {"events": list(_events)}
        data.update(_extra)
    data.update(top)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, default=str)
