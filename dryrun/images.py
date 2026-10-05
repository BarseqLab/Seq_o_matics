"""Synthetic microscope images with a known best-focus plane.

Focus model: a position is in focus when ZDrive + piezo == its sample surface S.
S comes from the experiment's cycle00.pos (ZDrive + piezo of each position) plus
a per-position offset, and drifts by +1.5 um every time that position is focused
again. Blur grows with |defocus|, so the sharpness metric peaks at the plane
closest to focus. Everything is deterministic (seeded by names), so two program
versions that acquire the same events get identical pixels.
"""

import hashlib
import threading

import cv2
import numpy as np

IMWIDTH = 1024
POSITION_OFFSETS_UM = [-4.5, 0.0, 3.0, 6.0]  # applied to Pos0..Pos3 (cyclic)
DRIFT_PER_FOCUS_UM = 1.5
SECOND_PASS_GAIN = 0.97  # second sweep of the same channel is slightly bleached

_lock = threading.Lock()
_base_cache = {}
_surfaces = {}
_focus_count = {}


def _seed(*parts):
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def _base(name):
    with _lock:
        if name in _base_cache:
            return _base_cache[name]
    rng = np.random.default_rng(_seed("base", name))
    img = np.full((IMWIDTH, IMWIDTH), 400.0, np.float32)
    n = 1500
    ys = rng.integers(0, IMWIDTH, n)
    xs = rng.integers(0, IMWIDTH, n)
    amp = rng.uniform(1500, 6000, n).astype(np.float32)
    img[ys, xs] += amp * 20
    img = cv2.GaussianBlur(img, (0, 0), 2.0)
    with _lock:
        _base_cache[name] = img
    return img


def set_surfaces(positions):
    """positions: list of (name, zdrive, piezo) from cycle00.pos."""
    for i, (name, z, p) in enumerate(positions):
        _surfaces[name] = z + p + POSITION_OFFSETS_UM[i % len(POSITION_OFFSETS_UM)]


def begin_focus_acquisition(name):
    """Called once per focus stack; returns the surface used for this stack."""
    with _lock:
        n = _focus_count.get(name, 0)
        _focus_count[name] = n + 1
    return _surfaces.get(name, 0.0) + n * DRIFT_PER_FOCUS_UM


def render(name, channel, defocus_um, gain=1.0, noise_seed=None):
    base = _base(name)
    sigma = 0.6 + 0.6 * abs(defocus_um) / 1.5
    img = cv2.GaussianBlur(base, (0, 0), sigma) * gain
    if noise_seed is not None:
        rng = np.random.default_rng(noise_seed)
        img = img + rng.normal(0, 15, img.shape).astype(np.float32)
    return np.clip(img, 0, 65535).astype(np.uint16)


def render_tile(name, channel):
    """Max-projection tiles: content only matters for the live view and MAX files."""
    return render(name + "|" + channel, channel, 1.5, gain=1.0)
