"""Automation controller for the Seq-o-Matic system.

Orchestrates the full experiment automation loop: fluidics sequences,
imagecycle00 focusing, and multi-cycle imaging pipelines.
"""

import os
import time
import json
import shutil
from threading import Thread

import pandas as pd

from front_end.logwindow import (
    add_highlight_mainwindow, update_error,
)
from system.image_acquisition_and_analysis_system import scope, get_pos_data, single_createtiles
from system.fluidics_exchange_system import FluidicsConstants
from system.imaging.position_utils import image_channels_for_cycle
from system.imaging.zstack_settings import ZStackSettings, estimate_storage, format_bytes


def _get_time():
    """Import and call the get_time helper from the main Widgets module."""
    from front_end.Widgets import get_time
    return get_time()


def image_rounds(process_ls):
    """Cycle names of the protocol's image rounds, as start_sequence derives them ('imagecycle_hyb01' -> 'hyb01')."""
    return [c[11:] for c in process_ls if "Fluidics_sequence" not in c and "imagecycle00" not in c]


class AutomationController:
    """Orchestrates the full experiment automation: fluidics, focusing, alignment, tiling, and imaging.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    def __init__(self, app):
        self.app = app

    def start_sequence(self):
        """Recursively execute the next step in the protocol list (fluidics, imagecycle00, or imaging) until all rounds complete."""
        if self.app.process_index > self.app.process_index_limite:
            txt = _get_time() + "All rounds finished!\n"
            self.app.write_log(txt)
            add_highlight_mainwindow(txt)
            self.app.fluidics.disconnect_pump()
            self.app.fluidics.disconnect_selector()
            self.app.fluidics.disconnect_relay()
            self.app.fluidics.disconnect_heater()
            txt = _get_time() + "Upload data to server!\n"
            self.app.write_log(txt)
            add_highlight_mainwindow(txt)
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
            # Upload only what the operator ticked when the experiment was created.
            if getattr(self.app, "Local_upload", 0) == 1:
                if os.path.exists(os.path.join(
                    self.app.scope.maxprojection_drive,
                    self.app.pos_path[3:] + "_maxprojection",
                )):
                    txt = _get_time() + "Upload images to server!\n"
                    self.app.write_log(txt)
                    add_highlight_mainwindow(txt)
                    self.app.scope.send_to_server(self.app.pos_path)
                    txt = _get_time() + "Upload images is finished!\n"
                    self.app.write_log(txt)
                    add_highlight_mainwindow(txt)
            if getattr(self.app, "AWS", 0) == 1:
                self.app.upload_aws_handler()

            # The protocol-file upload (scope.send_protocol) is disabled, as in the reference.
            txt = _get_time() + "Upload files is finished!\n"
            self.app.write_log(txt)
            add_highlight_mainwindow(txt)
            self.app.all_autobtn_normal()
            self.app.cancel_sequence_btn['state'] = "disable"
            return

        self.app.process_cycle = self.app.process_ls[self.app.process_index]
        txt = _get_time() + "start " + self.app.process_cycle + "\n"
        self.app.write_log(txt)
        add_highlight_mainwindow(txt)
        self.app.fluidics.select_chamber(FluidicsConstants.SELECT_CHAMBER_STATE)
        if "Fluidics_sequence" in self.app.process_cycle:
            self.app.fluidics.pump.driver.setFlowRate(1.5)
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
            self.app.scope.move_to_fluidics()
            try:
                self.app.protocol = self.app.fluidics.find_protocol(self.app.process_cycle)
            except Exception:
                self.app.fluidics.disconnect_pump()
                self.app.fluidics.disconnect_selector()
                self.app.fluidics.disconnect_relay()
                self.app.fluidics.disconnect_heater()
                self.app.all_autobtn_normal()
                self.app.cancel_sequence_btn['state'] = "disable"
                from tkinter import messagebox
                messagebox.showinfo(title="Protocol issue", message="check protocol file, the format is wrong")
                return
            t = Thread(target=self.app.run_fluidics_cycle, args=(self.app.protocol,))
            t.start()
            # Wait for fluidics to signal imaging can start (or cancel)
            while not self.app.fluidics.start_image_event.wait(timeout=2):
                if self.app.cancel == 1:
                    break
            self.app.process_index = self.app.process_index + 1
            if self.app.cancel != 1:
                time.sleep(5)
                t1 = Thread(target=self.start_sequence)
                t1.start()
            else:
                pass
                return
        elif "imagecycle00" in self.app.process_cycle:
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
            self.app.scope.move_to_image()
            self.app.scope.cancel_process = 0
            self.app.current_cycle = "imagecycle00"
            t = Thread(target=self.app.do_focus_thread)
            t.start()
            # Wait for focus to complete (or cancel)
            while self.app.scope.focus_status != 1:
                if self.app.cancel == 1:
                    break
                time.sleep(2)
            self.app.process_index = self.app.process_index + 1
            if self.app.cancel != 1:
                time.sleep(5)
                t1 = Thread(target=self.start_sequence)
                t1.start()
            else:
                pass
                return
        else:
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
            )
            self.app.scope.move_to_image()
            self.app.scope.cancel_process = 0
            self.app.current_cycle = self.app.process_cycle[11:]
            self.image_auto()
            # Wait for max projection to complete (or cancel)
            while self.app.scope.max_projection_status != 1:
                if self.app.cancel == 1:
                    break
                time.sleep(2)
            self.app.process_index = self.app.process_index + 1
            if self.app.cancel != 1:
                time.sleep(10)
                t1 = Thread(target=self.start_sequence)
                t1.start()
            else:
                pass
                return

    def image_auto(self):
        """Execute the full automated imaging pipeline: focus, align, tile, then max-project with live view."""
        if self.app.cancel == 1:
            pass
        else:
            self.app.do_focus_thread()
            self.app.align_and_draw_thread()
            self.app.tile_and_draw_thread()
        if self.app.cancel == 1:
            pass
        else:
            t1 = Thread(target=self.app.maxprojection_thread)
            t1.start()
            t2 = Thread(target=self.app.plot_live_view_thread)
            t2.start()

    def check_files(self):
        """Validate that all required input files exist before starting the automation sequence."""
        self.check_imagecycle00()

    def check_imagecycle00(self):
        """Verify that cycle00 position files and reference folders exist when image cycles are in the protocol."""
        if "imagecycle00" in self.app.process_ls:
            if not os.path.exists(os.path.join(self.app.pos_path, "cycle00.pos")):
                from tkinter import messagebox
                messagebox.showinfo(title="Config failure ",
                                    message="Please create cycle00 coordinates first!")
                update_error("Please create cycle00 coordinates first!")
                return
            else:
                self.app.check_file = self.app.scope.check_cycle00()
        else:
            check = [1 for i in self.app.process_ls if "imagecycle" in i]
            if sum(check) == 0:
                self.app.check_file = 1
                return
            else:
                if not os.path.exists(os.path.join(self.app.pos_path, "dicfocuscycle00")):
                    update_error("Missing dicfocuscycle00")
                    return
                if not os.path.exists(os.path.join(self.app.pos_path, "pre_adjusted_pos.pos")):
                    update_error("Missing pre_adjusted_pos.pos")
                    return
                else:
                    self.app.check_file = 1

    def _start_positions(self):
        """Position list the run will image (cycle00.pos, else pre_adjusted_pos.pos), or None."""
        for name in ("cycle00.pos", "pre_adjusted_pos.pos"):
            path = os.path.join(self.app.pos_path, name)
            if os.path.exists(path):
                with open(path) as f:
                    d = json.load(f)
                return pd.DataFrame([get_pos_data(item, self.app.scope_cfg[0]["piezo"])
                                     for item in d['map']['StagePositions']['array']])
        return None

    def _piezo_limits(self):
        """Piezo travel (low, high) in um from Micro-Manager, or None if it can't be read."""
        try:
            core = self.app.scope.core
            return (float(core.get_property("DA Z Stage", "Stage Low Position(um)")),
                    float(core.get_property("DA Z Stage", "Stage High Position(um)")))
        except Exception:
            return None

    def start_check(self):
        """Z-stack settings, piezo travel and disk space for the automated run about to start.

        Returns a dict with 'lines' (summary text), 'errors' (block Start unless
        overridden), 'warnings', and 'settings' (the ZStackSettings in effect).
        """
        cfg = self.app.scope_cfg[0]
        zs = ZStackSettings.from_config(cfg)
        report = {"lines": [], "errors": [], "warnings": [], "settings": zs}
        rounds = image_rounds(self.app.process_ls)
        n_focus_rounds = len(rounds) + (1 if "imagecycle00" in self.app.process_ls else 0)
        if n_focus_rounds == 0:
            return report
        report["lines"] += zs.describe()
        positions = self._start_positions()
        middles = []
        if positions is not None and "piezo" in positions:
            middles = [float(positions["piezo"].iloc[0])]  # every stack is centred on the first position's piezo
            report["lines"].append(
                f"Piezo window: focus {zs.focus_planes(middles[0])[0]:.1f} to {zs.focus_planes(middles[0])[-1]:.1f} um, "
                f"stack {zs.imaging_planes(middles[0])[0]:.1f} to {zs.imaging_planes(middles[0])[-1]:.1f} um")
        limits = self._piezo_limits()
        if limits is None:
            report["warnings"].append("Piezo travel could not be read from Micro-Manager; not checked.")
        errors, warnings = zs.validate(limits, middles)
        report["errors"] += errors
        report["warnings"] += warnings

        if positions is None:
            report["warnings"].append("No cycle00.pos or pre_adjusted_pos.pos yet; disk space not checked.")
            return report
        n_tiles = len(single_createtiles(positions, cfg["imwidth"], cfg["overlap"], cfg["pixel_size"]))
        n_focus_positions = sum(self.app.slice_per_slide) * 4
        est = estimate_storage(zs, [len(image_channels_for_cycle(r)) for r in rounds], n_tiles,
                               n_focus_positions, n_focus_rounds, cfg["imwidth"])
        report["lines"].append(
            f"Data: projections {format_bytes(est['projections'])}, raw focus stacks {format_bytes(est['raw_focus'])} "
            f"(kept), raw tile stacks up to {format_bytes(est['raw_tiles'])} at a time "
            f"({n_tiles} tiles, {len(rounds)} image rounds)")
        need = {}
        for path, n in ((cfg["maxproject_drive"], est["projections"]),
                        (self.app.pos_path, est["raw_tiles"] + est["raw_focus"])):
            drive = os.path.splitdrive(os.path.abspath(path))[0].upper() or os.path.abspath(path)
            need.setdefault(drive, [path, 0])[1] += n
        for drive, (path, n) in need.items():
            n *= zs.storage_margin
            try:
                free = shutil.disk_usage(path).free
            except OSError:
                report["errors"].append(f"Disk {drive}: {path} not found.")
                continue
            ok = free >= n
            report["lines"].append(f"Disk {drive} needs {format_bytes(n)} (x{zs.storage_margin:g}), "
                                   f"free {format_bytes(free)}: {'OK' if ok else 'NOT ENOUGH'}")
            if not ok:
                report["errors"].append(f"Disk {drive} does not have enough free space.")
        return report

    def check_storage(self):
        """Return 1 if the disks have room for the automated run (see start_check), otherwise 0."""
        return 0 if any(e.startswith("Disk ") for e in self.start_check()["errors"]) else 1

    def record_start_settings(self, report):
        """Write the z-stack settings in effect to log.txt and zstack_settings_used.json."""
        zs = report["settings"]
        txt = _get_time() + "Z-stack settings: " + "; ".join(report["lines"] + report["warnings"]) + "\n"
        self.app.write_log(txt)
        add_highlight_mainwindow(txt)
        groups = [{"group": g.index, "first_plane": g.first, "last_plane": g.last, "n_planes": g.n_planes}
                  for g in zs.substack_groups()]
        used = {"settings": zs.as_dict(),
                "derived": {"n_planes": zs.n_planes, "focus_range_um": zs.focus_range_um,
                            "focus_step_um": zs.focus_step, "n_focus_planes": zs.n_focus_planes,
                            "focus_method": zs.focus_method_for(), "extreme_threshold_um": zs.extreme_threshold(),
                            "substack_groups": groups},
                "checks": {"lines": report["lines"], "warnings": report["warnings"], "errors": report["errors"]}}
        with open(os.path.join(self.app.pos_path, "zstack_settings_used.json"), "w") as f:
            json.dump(used, f, indent=2)

    def all_autobtn_disable(self):
        """Disable all primary action buttons to prevent user interaction during a running process."""
        self.app.browse_btn_auto['state'] = "disable"
        self.app.browse_btn_manual['state'] = "disable"
        self.app.exp_btn_manual['state'] = "disable"
        self.app.exp_btn_auto['state'] = "disable"
        self.app.recipe_btn['state'] = "disable"
        self.app.info_btn_auto['state'] = "disable"
        self.app.device_btn['state'] = "disable"
        self.app.brain_btn['state'] = "disable"
        self.app.prime_btn['state'] = "disable"
        self.app.start_sequence_btn['state'] = "disable"
        self.app.fill_single_btn['state'] = "disable"

    def all_autobtn_normal(self):
        """Re-enable all primary action buttons after a process completes or is cancelled."""
        self.app.browse_btn_auto['state'] = "normal"
        self.app.browse_btn_manual['state'] = "normal"
        self.app.exp_btn_manual['state'] = "normal"
        self.app.exp_btn_auto['state'] = "normal"
        self.app.recipe_btn['state'] = "normal"
        self.app.info_btn_auto['state'] = "normal"
        self.app.device_btn['state'] = "normal"
        self.app.brain_btn['state'] = "normal"
        self.app.prime_btn['state'] = "normal"
        self.app.start_sequence_btn['state'] = "normal"
        self.app.fill_single_btn['state'] = "normal"
        self.app.cancel_sequence_btn['state'] = "normal"

    def write_log(self, txt):
        """Append the given text to the log.txt file in the work directory."""
        try:
            f = open(os.path.join(self.app.pos_path, "log.txt"), "a")
            f.write(txt)
            f.close()
        except Exception as e:
            print(f"Error writing log: {e}")
