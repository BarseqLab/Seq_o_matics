"""Z-stack thickness settings, sub-stack groups, disk estimate, autofocus and the NDTiff reader."""

import importlib.util
import os
import struct
import tempfile
import unittest

import numpy as np

from dryrun import ndtiff_writer

CODE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "code")


def _load(name):
    # By file path: importing through the system.imaging package would pull in the GUI and pycromanager.
    spec = importlib.util.spec_from_file_location(name, os.path.join(CODE, "system", "imaging", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


zstack_settings = _load("zstack_settings")
autofocus = _load("autofocus")
ndtiff_stack = _load("ndtiff_stack")
position_utils = _load("position_utils")
Z = zstack_settings.ZStackSettings
MB = 1e6
FRAME = 3200 * 3200 * 2


class TestDefaults(unittest.TestCase):
    def test_missing_keys_give_previous_behaviour(self):
        s = Z.from_config({"imwidth": 3200, "piezo": 1})
        self.assertEqual(s, Z())
        self.assertEqual((s.n_planes, s.n_focus_planes, s.focus_range_um), (20, 40, 60))
        self.assertEqual(len(s.substack_groups()), 1)
        self.assertEqual(s.substack_groups()[0].dic_plane, 9)
        self.assertEqual(s.extreme_threshold(), 20)
        self.assertEqual(s.focus_method_for(), "peak")

    def test_plane_positions_identical_to_previous_arrays(self):
        s = Z()
        for middle in (100.0, 185.0, 200.0, 213.37, 3659.25):
            np.testing.assert_array_equal(s.focus_planes(middle), np.arange(middle - 30, middle + 30, 1.5))
            np.testing.assert_array_equal(s.imaging_planes(middle), np.arange(middle - 15, middle + 15, 1.5))

    def test_repo_scope_json_sets_every_key_validly(self):
        import json
        with open(os.path.join(CODE, "config_file", "scope.json")) as f:
            cfg = json.load(f)[0]
        self.assertEqual(sorted(k for k in Z().as_dict() if k not in cfg), [])
        errors, _ = Z.from_config(cfg).validate((0, 400), [200.0])
        self.assertEqual(errors, [])


class TestWorkedExamples(unittest.TestCase):
    # T: (N, R, focus step, N_f, group sizes, extreme threshold rounded) from the plan's table
    TABLE = {
        30: (20, 60, 1.5, 40, [20], 20),
        40: (27, 70, 1.5, 47, [27], 23),
        45: (30, 75, 1.5, 50, [30], 25),
        46: (31, 76, 1.5, 51, [20, 11], 25),
        50: (33, 80, 3, 27, [20, 13], 27),
        60: (40, 90, 3, 30, [20, 20], 30),
        70: (47, 100, 3, 33, [20, 27], 33),
        100: (67, 130, 3, 43, [20, 20, 27], 43),
        150: (100, 180, 3, 60, [20] * 5, 60),
        250: (167, 300, 3, 100, [20] * 7 + [27], 100),
        300: (200, 300, 3, 100, [20] * 10, 100),
    }

    def test_table(self):
        for t, (n, r, step, nf, groups, thr) in self.TABLE.items():
            s = Z(z_stack_thickness_um=t)
            with self.subTest(T=t):
                self.assertEqual(s.n_planes, n)
                self.assertAlmostEqual(s.focus_range_um, r)
                self.assertEqual(s.focus_step, step)
                self.assertEqual(s.n_focus_planes, nf)
                self.assertEqual([g.n_planes for g in s.substack_groups()], groups)
                self.assertEqual(round(s.extreme_threshold()), thr)

    def test_groups_tile_the_stack_on_fixed_spacing(self):
        for t in range(5, 301):
            s = Z(z_stack_thickness_um=t)
            groups = s.substack_groups()
            with self.subTest(T=t):
                self.assertEqual(groups[0].first, 0)
                self.assertEqual(groups[-1].last, s.n_planes - 1)
                for i, g in enumerate(groups):
                    self.assertEqual(g.index, i)
                    if len(groups) > 1:
                        self.assertEqual(g.first, i * s.n_substack_planes)
                for a, b in zip(groups, groups[1:]):
                    self.assertEqual(b.first, a.last + 1)
                if t <= 45:
                    self.assertEqual(len(groups), 1)

    def test_leftover_rule(self):
        self.assertEqual([(g.first, g.last) for g in Z(z_stack_thickness_um=45).substack_groups()], [(0, 29)])
        self.assertEqual([(g.first, g.last) for g in Z(z_stack_thickness_um=46).substack_groups()],
                         [(0, 19), (20, 30)])
        self.assertEqual([(g.first, g.last) for g in Z(z_stack_thickness_um=100).substack_groups()],
                         [(0, 19), (20, 39), (40, 66)])
        self.assertEqual([g.dic_plane for g in Z(z_stack_thickness_um=46).substack_groups()], [9, 25])

    def test_focus_method_auto(self):
        self.assertEqual(Z(z_stack_thickness_um=49, focus_method="auto").focus_method_for(), "peak")
        self.assertEqual(Z(z_stack_thickness_um=50, focus_method="auto").focus_method_for(), "band_center")
        self.assertEqual(Z(z_stack_thickness_um=100).focus_method_for(), "peak")


class TestValidate(unittest.TestCase):
    def test_limits(self):
        self.assertEqual(Z().validate((0, 400), [200.0]), ([], []))
        errors, _ = Z(z_stack_thickness_um=301).validate()
        self.assertEqual(len(errors), 1)
        errors, warnings = Z(z_stack_thickness_um=280).validate()
        self.assertEqual((len(errors), len(warnings)), (0, 1))
        errors, _ = Z(focus_method="sharpest").validate()
        self.assertEqual(len(errors), 1)

    def test_piezo_travel(self):
        _, warnings = Z(z_stack_thickness_um=150).validate((0, 400), [100.0])  # sweep 10..190 fits
        self.assertEqual(warnings, [])
        _, warnings = Z(z_stack_thickness_um=250).validate((0, 400), [100.0])  # sweep -50..247 does not
        self.assertEqual(len(warnings), 2)
        self.assertIn("Focus sweep", warnings[0])


class TestStorage(unittest.TestCase):
    def test_per_tile_sizes_match_plan(self):
        s = Z()
        est = zstack_settings.estimate_storage(s, [6], n_tiles=1, n_focus_positions=1, n_focus_rounds=1, imwidth=3200)
        self.assertAlmostEqual(est["projections"] / MB, 122.88, places=2)    # 123 MB
        self.assertAlmostEqual(est["raw_tiles"] / MB, 2457.6, places=1)      # 2.5 GB
        self.assertAlmostEqual(est["raw_focus"] / MB, 1638.4, places=1)      # 1.6 GB
        s = Z(z_stack_thickness_um=100)
        est = zstack_settings.estimate_storage(s, [6], 1, 1, 1, 3200)
        self.assertAlmostEqual(est["projections"] / MB, 368.64, places=2)    # 369 MB
        self.assertAlmostEqual(est["raw_tiles"] / 1e9, 8.23, places=2)       # 8.2 GB
        self.assertAlmostEqual(est["raw_focus"] / 1e9, 1.76, places=2)       # 1.8 GB

    def test_whole_run(self):
        s = Z()
        rounds = [5, 4, 6]  # geneseq01, geneseq02, hyb01
        est = zstack_settings.estimate_storage(s, rounds, n_tiles=10, n_focus_positions=8, n_focus_rounds=4,
                                               imwidth=3200)
        self.assertEqual(est["projections"], 10 * 15 * FRAME)
        self.assertEqual(est["raw_tiles"], 10 * 6 * 20 * FRAME)
        self.assertEqual(est["raw_focus"], 4 * 8 * 2 * 40 * FRAME)
        self.assertEqual(zstack_settings.estimate_storage(s, [], 10, 8, 1, 3200)["raw_tiles"], 0)


class TestChannels(unittest.TestCase):
    def test_same_as_previous_rule(self):
        def previous(cycle):
            if ('geneseq' in cycle or 'bcseq' in cycle or 'user_defined' in cycle) and '01' in cycle:
                return ["G", "T", "A", "C", "Hyb-DAPI"]
            elif ('geneseq' in cycle or 'bcseq' in cycle or 'user_defined' in cycle) and ~('01' in cycle):
                return ["G", "T", "A", "C"]
            return ["Hyb-GFP", "Hyb-YFP", "Hyb-TxRed", "Hyb-Cy5", "Hyb-DAPI", "DIC"]
        for c in ["geneseq01", "geneseq02", "bcseq01", "bcseq11", "user_defined01", "user_defined02", "hyb01",
                  "hyb02", "cycle00"]:
            self.assertEqual(position_utils.image_channels_for_cycle(c), previous(c), c)


class TestAutofocus(unittest.TestCase):
    def test_peak(self):
        self.assertEqual(autofocus.peak_plane([1, 5, 3, 9, 2]), 3)

    def test_band_center_ignores_off_centre_peak(self):
        z = np.arange(60)
        curve = 1.0 + 9.0 * ((z >= 20) & (z <= 39))  # sharp tissue band, planes 20-39
        curve[23] = 12.0  # sharpest single plane near the bottom of the band
        plane, first, last = autofocus.band_center_plane(curve, 0.5)
        self.assertEqual((first, last), (20, 39))
        self.assertEqual(plane, 29)
        self.assertEqual(autofocus.peak_plane(curve), 23)

    def test_band_center_rejects_single_spike(self):
        curve = np.ones(40)
        curve[10:15] = [3, 6, 8, 6, 3]
        curve[30] = 50.0  # one-plane spike from debris: removed by the 3-plane median
        plane, first, last = autofocus.band_center_plane(curve, 0.5)
        self.assertEqual((plane, first, last), (12, 11, 13))

    def test_band_center_symmetric_curve_is_peak(self):
        z = np.arange(41)
        curve = np.exp(-((z - 17) / 5.0) ** 2)
        self.assertEqual(autofocus.band_center_plane(curve, 0.5)[0], 17)


class TestNDTiffStack(unittest.TestCase):
    def _frames(self, axes_list, seed):
        rng = np.random.default_rng(seed)
        return [(axes, rng.integers(0, 65535, (8, 6), dtype=np.uint16), {}) for axes in axes_list]

    def test_reads_by_axes_and_later_frame_wins(self):
        with tempfile.TemporaryDirectory() as d:
            axes = [{"channel": "A", "z": 0}, {"channel": "A", "z": 1}, {"channel": "B", "z": 0},
                    {"channel": "A", "z": 1}]
            frames = self._frames(axes, 1)
            ndtiff_writer.write_dataset(d, "Pos0", frames)
            with ndtiff_stack.NDTiffStack(d) as s:
                self.assertEqual(len(s), 3)
                np.testing.assert_array_equal(s.read(channel="B", z=0), frames[2][1])
                np.testing.assert_array_equal(s.read(channel="A", z=1), frames[3][1])
                self.assertFalse(s.has(channel="B", z=1))
                with self.assertRaises(KeyError):
                    s.read(channel="B", z=1)

    def test_stack_split_across_files(self):
        with tempfile.TemporaryDirectory() as d:
            first = self._frames([{"channel": "A", "z": z, "focus_pass": 0} for z in range(3)], 2)
            second = self._frames([{"channel": "A", "z": z, "focus_pass": 1} for z in range(3)], 3)
            ndtiff_writer.write_dataset(d, "Pos0", first)
            with open(os.path.join(d, "NDTiff.index"), "rb") as f:
                index = f.read()
            ndtiff_writer.write_dataset(d, "Pos0_1", second)
            with open(os.path.join(d, "NDTiff.index"), "rb") as f:
                index += f.read()
            with open(os.path.join(d, "NDTiff.index"), "wb") as f:
                f.write(index + struct.pack("<I", 0))
            with ndtiff_stack.NDTiffStack(d) as s:
                self.assertEqual(len(s), 6)
                for z in range(3):
                    np.testing.assert_array_equal(s.read(channel="A", z=z, focus_pass=0), first[z][1])
                    np.testing.assert_array_equal(s.read(channel="A", z=z, focus_pass=1), second[z][1])

    def test_matches_tifffile(self):
        import tifffile
        with tempfile.TemporaryDirectory() as d:
            axes = [{"channel": c, "z": z} for c in ("G", "T") for z in range(4)]
            frames = self._frames(axes, 4)
            path = ndtiff_writer.write_dataset(d, "Pos1", frames)
            whole = tifffile.imread(path)  # (channel, z, y, x), as the max projection used to read it
            with ndtiff_stack.NDTiffStack(d) as s:
                for ci, c in enumerate(("G", "T")):
                    for z in range(4):
                        np.testing.assert_array_equal(s.read(channel=c, z=z), whole[ci, z])


if __name__ == "__main__":
    unittest.main()
