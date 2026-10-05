"""Read an NDTiff dataset (as written by Micro-Manager / pycromanager) one frame at a time.

Frames are looked up through NDTiff.index, so a stack that Micro-Manager split
across several ~4 GB files reads like one, and only the requested frame is
loaded. When the same axes were written twice, the later frame wins, as in ndtiff.
"""
import json
import os
import struct

import numpy as np

_DTYPES = {0: np.uint8, 1: np.uint16, 3: np.uint16, 4: np.uint16, 5: np.uint16, 6: np.uint16}


def _key(axes):
    return frozenset(axes.items())


class NDTiffStack:
    def __init__(self, dataset_dir):
        self.dataset_dir = dataset_dir
        self._entries = {}
        self._files = {}
        with open(os.path.join(dataset_dir, "NDTiff.index"), "rb") as f:
            data = f.read()
        pos = 0
        while pos + 4 <= len(data):
            (n,) = struct.unpack_from("<I", data, pos)
            if n == 0:
                break  # index not terminated cleanly; keep what was read
            try:
                axes = json.loads(data[pos + 4:pos + 4 + n].decode("utf-8"))
                pos += 4 + n
                (n,) = struct.unpack_from("<I", data, pos)
                filename = data[pos + 4:pos + 4 + n].decode("utf-8")
                pos += 4 + n
                offset, width, height, pixel_type, compression = struct.unpack_from("<5I", data, pos)
                pos += 32
            except (struct.error, ValueError):
                break  # truncated last entry
            self._entries[_key(axes)] = (filename, offset, width, height, pixel_type, compression)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        for f in self._files.values():
            f.close()
        self._files.clear()

    def __len__(self):
        return len(self._entries)

    def axes(self):
        return [dict(k) for k in self._entries]

    def has(self, **axes):
        return _key(axes) in self._entries

    def read(self, **axes):
        """The 2-D frame with exactly these axes, e.g. read(channel='G', z=3)."""
        try:
            filename, offset, width, height, pixel_type, compression = self._entries[_key(axes)]
        except KeyError:
            raise KeyError(f"No frame with axes {axes} in {self.dataset_dir}") from None
        if compression != 0 or pixel_type not in _DTYPES:
            raise ValueError(f"Unsupported NDTiff frame (pixel type {pixel_type}, compression {compression})")
        f = self._files.get(filename)
        if f is None:
            f = self._files[filename] = open(os.path.join(self.dataset_dir, filename), "rb")
        f.seek(offset)
        return np.fromfile(f, dtype=_DTYPES[pixel_type], count=width * height).reshape(height, width)
