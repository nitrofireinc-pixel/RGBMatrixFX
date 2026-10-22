"""Opt-in timing trace for diagnostics (IPC "trace"). Off by default and costs nothing then.

Events are (monotonic_time, kind, duration_ms, extra) tuples in a bounded ring; the monotonic
clock is system-wide, so traces from add-ons can be lined up with the engine's."""
import collections
import gc
import time

RING = None          # collections.deque while tracing
SEQ = 0              # engine tick sequence of the frame being handed to the devices
_gc_t = [0.0]


def ev(kind, t, dur_ms=0.0, extra=None):
    r = RING
    if r is not None:
        r.append((round(t, 5), kind, round(dur_ms, 2), extra))


def _gc_cb(phase, info):
    if RING is None:
        return
    if phase == "start":
        _gc_t[0] = time.monotonic()
    else:
        ev("gc", _gc_t[0], (time.monotonic() - _gc_t[0]) * 1000, info.get("generation"))


def start(maxlen=40000):
    global RING
    RING = collections.deque(maxlen=maxlen)
    if _gc_cb not in gc.callbacks:
        gc.callbacks.append(_gc_cb)


def stop():
    global RING
    out, RING = list(RING or ()), None
    if _gc_cb in gc.callbacks:
        gc.callbacks.remove(_gc_cb)
    return out
