"""Minimal NDTiff v3 writer (uncompressed uint16), readable by tifffile like real data.

Produces `<dir>/<name>_NDTiffStack.tif` + `<dir>/NDTiff.index`, the layout
Micro-Manager/pycromanager writes. tifffile builds the dataset shape from the
index axes, so - exactly as with real Elm focus stacks - frames whose axes
repeat (same channel name swept twice) collapse to the LAST written frame.
"""

import json
import os
import struct

import numpy as np

MM_MAGIC = 483729
MM_SUMMARY_MAGIC = 2355492
TAG_MM_METADATA = 51123


def _ifd(entries, next_offset):
    """entries: list of (tag, type, count, value_or_offset). Sorted by tag."""
    out = struct.pack("<H", len(entries))
    for tag, typ, count, value in sorted(entries):
        if typ == 3 and count == 1:  # SHORT stored left-justified in the 4-byte field
            out += struct.pack("<HHIHH", tag, typ, count, value, 0)
        else:
            out += struct.pack("<HHII", tag, typ, count, value)
    out += struct.pack("<I", next_offset)
    return out


def write_dataset(directory, name, frames, summary=None):
    """frames: list of (axes_dict, 2-D uint16 array, metadata_dict), in acquisition order."""
    os.makedirs(directory, exist_ok=True)
    fname = f"{name}_NDTiffStack.tif"
    path = os.path.join(directory, fname)
    summary_bytes = json.dumps(summary or {"Prefix": name}).encode()
    index = bytearray()
    with open(path, "wb") as f:
        f.write(b"II*\x00" + struct.pack("<I", 0))
        f.write(struct.pack("<IIIII", MM_MAGIC, 3, 0, MM_SUMMARY_MAGIC, len(summary_bytes)))
        f.write(summary_bytes)
        prev_ptr = 4
        n_entries = 13
        for axes, img, md in frames:
            img = np.ascontiguousarray(img, dtype="<u2")
            h, w = img.shape
            if f.tell() % 2:
                f.write(b"\0")
            ifd_off = f.tell()
            ifd_size = 2 + n_entries * 12 + 4
            res_off = ifd_off + ifd_size
            data_off = res_off + 16
            data = img.tobytes()
            md_bytes = json.dumps(md).encode() + b"\0"
            md_off = data_off + len(data)
            entries = [
                (256, 4, 1, w), (257, 4, 1, h), (258, 3, 1, 16), (259, 3, 1, 1), (262, 3, 1, 1),
                (273, 4, 1, data_off), (277, 3, 1, 1), (278, 4, 1, h), (279, 4, 1, len(data)),
                (282, 5, 1, res_off), (283, 5, 1, res_off + 8), (296, 3, 1, 3),
                (TAG_MM_METADATA, 2, len(md_bytes), md_off),
            ]
            # link previous IFD pointer to this IFD
            here = f.tell()
            f.seek(prev_ptr)
            f.write(struct.pack("<I", ifd_off))
            f.seek(here)
            f.write(_ifd(entries, 0))
            prev_ptr = ifd_off + 2 + n_entries * 12
            f.write(struct.pack("<IIII", 30303, 1, 30303, 1))
            f.write(data)
            f.write(md_bytes)
            axes_json = json.dumps(axes).encode()
            fn = fname.encode()
            index += struct.pack("<i", len(axes_json)) + axes_json
            index += struct.pack("<i", len(fn)) + fn
            index += struct.pack("<IiiiiIii", data_off, w, h, 1, 0, md_off, len(md_bytes) - 1, 0)
    with open(os.path.join(directory, "NDTiff.index"), "wb") as f:
        f.write(bytes(index))
    return path
