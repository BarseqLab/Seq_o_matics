"""Choosing the focus plane from a sharpness curve (one value per focus plane)."""
import numpy as np


def peak_plane(sharpness):
    """Index of the sharpest plane."""
    return int(np.argmax(sharpness))


def smooth_median3(values):
    """Moving median over 3 planes, with the end values repeated at the edges."""
    s = np.asarray(values, dtype=float)
    if len(s) < 3:
        return s
    padded = np.pad(s, 1, mode="edge")
    return np.median(np.stack([padded[:-2], padded[1:-1], padded[2:]]), axis=0)


def band_center_plane(sharpness, frac):
    """Middle of the sharp band around the peak, for thick sections.

    The curve is smoothed, the baseline is its 10th percentile, and the band is
    the run of planes at or above baseline + frac * (peak - baseline) that
    contains the peak. Returns (plane, first, last), with first..last the band.
    """
    s = smooth_median3(sharpness)
    peak = int(np.argmax(s))
    base = float(np.percentile(s, 10))
    above = s >= base + frac * (s[peak] - base)
    first = peak
    while first > 0 and above[first - 1]:
        first -= 1
    last = peak
    while last < len(s) - 1 and above[last + 1]:
        last += 1
    return (first + last) // 2, first, last
