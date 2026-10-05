"""Unit tests for the dry-run fakes.  Run:  python -m unittest discover -s dryrun/tests -t ."""

import os
import shutil
import tempfile
import unittest

import numpy as np
import tifffile

from dryrun import clock, fake_nidaqmx, fake_serial, ndtiff_writer, trace


class TestNDTiffWriter(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_duplicate_channel_collapses_to_second_pass_like_real_elm_data(self):
        # Real Elm focus stacks: 80 frames (Hyb-DAPI swept twice), tifffile returns 40 = the 2nd pass.
        frames = [({"channel": "Hyb-DAPI", "z": z}, np.full((32, 32), 1000 * p + z, np.uint16), {})
                  for p in (0, 1) for z in range(40)]
        ndtiff_writer.write_dataset(os.path.join(self.dir, "Pos0_1"), "Pos0", frames)
        path = os.path.join(self.dir, "Pos0_1", "Pos0_NDTiffStack.tif")
        img = tifffile.imread(path)
        self.assertEqual(img.shape, (40, 32, 32))
        self.assertEqual(int(img[0, 0, 0]), 1000)
        self.assertEqual(int(img[39, 0, 0]), 1039)
        with tifffile.TiffFile(path) as t:
            self.assertTrue(t.is_ndtiff)
            self.assertEqual(len(t.pages), 80)

    def test_multichannel_stack_is_channel_z_y_x(self):
        chans = ["Hyb-GFP", "Hyb-YFP", "Hyb-TxRed", "Hyb-Cy5", "Hyb-DAPI", "DIC"]
        frames = [({"channel": c, "z": z}, np.full((16, 16), 100 * ci + z, np.uint16), {})
                  for ci, c in enumerate(chans) for z in range(20)]
        ndtiff_writer.write_dataset(os.path.join(self.dir, "T_1"), "T", frames)
        img = tifffile.imread(os.path.join(self.dir, "T_1", "T_NDTiffStack.tif"))
        self.assertEqual(img.shape, (6, 20, 16, 16))
        self.assertEqual(int(img[5, 9, 0, 0]), 509)


class TestPumpEmulator(unittest.TestCase):
    def test_timed_dispense_and_running_state(self):
        clock.install(1000)
        pump = fake_serial.IsmatecEmulator("COMX")
        for cmd in ("S001428", "N", "W", "V1520", "H"):
            self.assertEqual(pump.handle(("1" + cmd + "\r").encode()), b"*")
        self.assertEqual(pump.handle(b"1E\r"), b"+")
        disp = [e for e in trace.events() if e["kind"] == "pump_dispense"][-1]
        self.assertAlmostEqual(disp["duration_s"], 152.0)
        self.assertAlmostEqual(disp["rate_ml_min"], 1.499, places=3)
        clock.sleep(160)
        self.assertEqual(pump.handle(b"1E\r"), b"-")

    def test_port_can_be_open_only_once(self):
        a = fake_serial.Serial(port="COM10")
        with self.assertRaises(fake_serial.SerialException):
            fake_serial.Serial(port="COM10")
        a.close()
        fake_serial.Serial(port="COM10").close()

    def test_garbage_collected_port_is_released_like_pyserial(self):
        a = fake_serial.Serial(port="COM11")
        del a
        fake_serial.Serial(port="COM11").close()

    def test_missing_and_busy_ports_fail_like_on_elm(self):
        for port in ("COM5", "COM6"):
            with self.assertRaises(fake_serial.SerialException):
                fake_serial.Serial(port=port)


class TestDaqFake(unittest.TestCase):
    def setUp(self):
        clock.install(1000)
        fake_nidaqmx.install()

    def test_invalid_device_rejected(self):
        t = fake_nidaqmx.Task()
        with self.assertRaises(fake_nidaqmx.DaqError):
            t.ao_channels.add_ao_voltage_chan("Dev2/ao0")

    def test_heater_warms_in_heat_mode_only(self):
        ao, do, ai = fake_nidaqmx.Task(), fake_nidaqmx.Task(), fake_nidaqmx.Task()
        ao.ao_channels.add_ao_voltage_chan("Dev3/ao0")
        do.do_channels.add_do_chan("Dev3/port1/line0")
        ai.ai_channels.add_ai_voltage_chan("Dev3/ai0")
        start = ai.read()
        ao.write(5.6)
        do.write(True)  # image mode
        clock.sleep(120)
        self.assertAlmostEqual(ai.read(), start, places=2)
        do.write(False)  # heat mode
        clock.sleep(150)
        self.assertGreater(ai.read(), 5.6 - 0.15)

    def test_unclosed_task_keeps_resource_reserved(self):
        t1 = fake_nidaqmx.Task()
        t1.ao_channels.add_ao_voltage_chan("Dev3/ao0")
        t1.start()
        t2 = fake_nidaqmx.Task()
        t2.ao_channels.add_ao_voltage_chan("Dev3/ao0")
        with self.assertRaises(fake_nidaqmx.DaqError):
            t2.start()
        t1.close()
        t2.start()
        t2.close()


if __name__ == "__main__":
    unittest.main()
