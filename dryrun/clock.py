"""Scaled clock: the program sees time pass SPEED times faster than real time.

Everything the program uses to measure or wait for time is patched consistently:
time.sleep, time.time, datetime.datetime.now, threading.Timer and
threading.Event.wait timeouts. Real concurrency between threads is preserved,
because every wait is still a real (shortened) wait.

The harness itself must use the REAL_* objects below.
"""

import datetime as _dt
import threading
import time

REAL_SLEEP = time.sleep
REAL_TIME = time.time
REAL_PERF = time.perf_counter
REAL_DATETIME = _dt.datetime
REAL_EVENT = threading.Event
REAL_TIMER = threading.Timer

SPEED = 1.0
_t0_perf = REAL_PERF()
_t0_wall = REAL_TIME()


def vnow():
    """Virtual seconds since the clock was installed."""
    return (REAL_PERF() - _t0_perf) * SPEED


def vtime():
    """Virtual wall-clock time (epoch seconds)."""
    return _t0_wall + vnow()


def sleep(seconds):
    if seconds is None or seconds <= 0:
        REAL_SLEEP(0)
    else:
        REAL_SLEEP(seconds / SPEED)


def real_sleep_virtual(seconds):
    """For harness code: wait `seconds` of virtual time."""
    sleep(seconds)


class FakeDatetime(REAL_DATETIME):
    @classmethod
    def now(cls, tz=None):
        return REAL_DATETIME.fromtimestamp(vtime(), tz)

    @classmethod
    def utcnow(cls):
        return REAL_DATETIME.utcfromtimestamp(vtime())

    @classmethod
    def today(cls):
        return REAL_DATETIME.fromtimestamp(vtime())


class ScaledEvent(REAL_EVENT):
    def wait(self, timeout=None):
        if timeout is not None:
            timeout = timeout / SPEED
        return super().wait(timeout)


class ScaledTimer(REAL_TIMER):
    def __init__(self, interval, function, args=None, kwargs=None):
        super().__init__(interval / SPEED, function, args=args, kwargs=kwargs)


def install(speed):
    global SPEED, _t0_perf, _t0_wall
    SPEED = float(speed)
    _t0_perf = REAL_PERF()
    _t0_wall = REAL_TIME()
    time.sleep = sleep
    time.time = vtime
    _dt.datetime = FakeDatetime
    threading.Event = ScaledEvent
    threading.Timer = ScaledTimer
