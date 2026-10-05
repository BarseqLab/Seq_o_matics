"""Fluidics control panel for the Seq-o-Matic GUI.

Handles priming, pumping individual reagents, washing, starting automation,
and monitoring fluidics sequences.
"""

import os
import time
import json
import tkinter as tk
from tkinter import messagebox, END
from threading import Thread

from front_end.logwindow import (
    add_highlight_mainwindow, add_fluidics_status, widge_attr,
)
from system.fluidics_exchange_system import FluidicsConstants
from system.fluidics.sequence_runner import SequenceState


def _get_time():
    """Import and call the get_time helper from the main Widgets module."""
    from front_end.Widgets import get_time
    return get_time()


class FluidicsControlPanel:
    """Manages fluidics priming, single-reagent pumping, washing, and automation start.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    def __init__(self, app):
        self.app = app

    def _pump_speed_or_prompt(self):
        """Return the pump speed typed by the operator, or None after asking for one.

        The value must be a positive number (mL/min). An empty or invalid field
        used to raise ValueError inside the handler.
        """
        text = self.app.pump_speed_input.get().strip()
        try:
            speed = float(text)
            if speed > 0:
                return speed
        except ValueError:
            pass
        messagebox.showinfo(title="Pump speed",
                            message="Please enter the measured pump speed (mL/min) before starting.")
        return None

    def prime_btn_check(self):
        """Show a confirmation popup for the pump speed before priming the lines."""
        self.app.prime_popup = tk.Tk()
        self.app.prime_popup.geometry("500x100")
        self.app.prime_popup.title("Pump speed check point")
        self.app.pump_speed_label_prime = tk.Label(
            self.app.prime_popup,
            text=" Please confirm the current pump speed is " + self.app.pump_speed_input.get() + " ml/min!",
        )
        self.app.pump_speed_label_prime.place(x=15, y=10)
        self.app.pump_speed_confirm_prime = tk.Button(
            self.app.prime_popup, text="Confirm", command=self.prime_btn_handler,
        )
        self.app.pump_speed_confirm_prime.place(x=150, y=50)
        self.app.cancel_button_prime = tk.Button(
            self.app.prime_popup, text="Cancel", command=self.app.prime_popup.destroy,
        )
        self.app.cancel_button_prime.place(x=350, y=50)

    def prime_btn_handler(self):
        """Prime all fluidics lines by running the fill-all sequence through the pump, selector, and relay."""
        self.app.prime_popup.destroy()
        speed = self._pump_speed_or_prompt()
        if speed is None:
            return
        self.app.fluidics.pumprate = speed
        print(self.app.fluidics.pumprate)
        if 0 in [
            self.app.device_status['selector_group'],
            self.app.device_status['pump_group'],
            self.app.device_status['relay_group'],
        ]:
            messagebox.showinfo(title="Config device", message="Please config selectors,pump and relay first!")
        else:
            self.app.all_autobtn_disable()
            self.app.cancel_sequence_btn['state'] = "normal"
            self.app.fluidics.sequenceStatus = 0
            self.app.fluidics.connect_pump()
            self.app.fluidics.connect_relay()
            self.app.fluidics.connect_selector()
            self.app.fluidics.connect_heater()
            self.app.fluidics.select_chamber(not FluidicsConstants.SELECT_CHAMBER_STATE)
            self.app.fluidics.loadSequence(self.app.fluidics.Fill_ALL_SEQUENCE)
            t1 = Thread(target=self.app.fluidics.startSequence)
            t1.start()
            txt = _get_time() + "Fill reagents into tubes!\n"
            add_highlight_mainwindow(txt)
            self.app.write_log(txt)
            t2 = Thread(target=self.sensor_fluidics_process)
            t2.start()

    def sensor_fluidics_process(self):
        """Wait until the fluidics cycle completes, then flush the in-chamber line with PBST and disconnect devices."""
        # Wait for cycle completion using event instead of polling
        self.app.fluidics.cycle_done_event.wait()
        if self.app.fluidics.sequenceStatus == SequenceState.CANCELLED:
            # Cancel stops here: no in-chamber PBST flush. Cancel already released the devices.
            txt = _get_time() + "Wash/Prime cancelled, in-chamber PBST flush skipped\n"
            add_highlight_mainwindow(txt)
            self.app.write_log(txt)
            return
        txt = _get_time() + "Now starting in chamber line\n"
        add_fluidics_status(txt)
        self.app.write_log(txt)
        self.app.fluidics.select_chamber(FluidicsConstants.SELECT_CHAMBER_STATE)
        self.app.fluidics.setSource("PBST")
        self.app.fluidics.pumpVol(4, self.app.fluidics.pumprate)
        time.sleep((float(4) / self.app.fluidics.pumprate) * 60 + 5)
        if self.app.fluidics.sequenceStatus == SequenceState.CANCELLED:
            return  # cancelled during the flush; Cancel already stopped and released the devices
        txt = _get_time() + "Finish in chamber line! Wash/Prime line Done!\n"
        add_highlight_mainwindow(txt)
        self.app.write_log(txt)
        self.app.fluidics.disconnect_pump()
        self.app.fluidics.disconnect_relay()
        self.app.fluidics.disconnect_selector()
        self.app.fluidics.disconnect_heater()
        self.app.all_autobtn_normal()
        self.app.cancel_sequence_btn['state'] = "disable"

    def create_reagent_list(self):
        """Load the reagent configuration JSON and return a list of reagent names and a name-to-address dictionary."""
        with open(os.path.join("config_file", 'Fluidics_Reagent_Components.json'), 'r') as r:
            reagent = json.load(r)
        reagent_ls = []
        reagent_hardwareID = []
        for i in reagent:
            reagent_ls.append(i['solution'])
            reagent_hardwareID.append(i['address'])
        reagent_dict = dict(zip(reagent_ls, reagent_hardwareID))
        return reagent_ls, reagent_dict

    def fill_single_reagent(self):
        """Validate device configuration and start a background thread to pump a single reagent."""
        self.app.pump_popup.destroy()
        if self._pump_speed_or_prompt() is None:
            return
        if 0 in [
            self.app.device_status['selector_group'],
            self.app.device_status['pump_group'],
            self.app.device_status['relay_group'],
        ]:
            messagebox.showinfo(title="Config device", message="Please config selectors,pump and relay first!")
        else:
            t1 = Thread(target=self.pump_reagent)
            t1.start()

    def pump_reagent(self):
        """Connect to fluidics hardware, pump the selected reagent at the specified volume and rate, then disconnect."""
        self.app.fluidics.pumprate = float(self.app.pump_speed_input.get().strip())
        reagent = self.app.reagent.get()
        vol = self.app.reagent_amount.get()
        if reagent == "":
            add_highlight_mainwindow("Please select reagent!\n")
        else:
            self.app.fill_single_btn['state'] = 'disable'
            self.app.fluidics.connect_relay()
            self.app.fluidics.connect_selector()
            self.app.fluidics.connect_pump()
            print(reagent)
            self.app.fluidics.setSource(reagent)
            if self.app.inchamber_path.get() == 1:
                self.app.fluidics.select_chamber(FluidicsConstants.SELECT_CHAMBER_STATE)
            else:
                self.app.fluidics.select_bypass(FluidicsConstants.SELECT_BYPASS_STATE)
            txt = _get_time() + "fill with " + reagent + "\n"
            add_highlight_mainwindow(txt)
            self.app.write_log(txt)
            self.app.fluidics.pumpVol(vol, self.app.fluidics.pumprate)
            time.sleep((float(vol) / 1.5) * 60 + 10)
            self.app.fluidics.disconnect_pump()
            self.app.fluidics.disconnect_relay()
            self.app.fluidics.disconnect_selector()
            time.sleep(1)
            txt = _get_time() + "fill with " + reagent + " is done!\n"
            self.app.fill_single_btn['state'] = 'normal'
            add_highlight_mainwindow(txt)
            self.app.write_log(txt)

    def pump_btn_check(self):
        """Show a confirmation popup for the pump speed before filling a single reagent."""
        self.app.pump_popup = tk.Tk()
        self.app.pump_popup.geometry("500x100")
        self.app.pump_popup.title("Pump speed check point")
        self.app.pump_speed_label_pump = tk.Label(
            self.app.pump_popup,
            text=" Please confirm the current pump speed is " + self.app.pump_speed_input.get() + " ml/min!",
        )
        self.app.pump_speed_label_pump_2 = tk.Label(
            self.app.pump_popup,
            text=" For calibration: Pump the same amount of your speed, it will give you 1 min pumping! ",
        )
        self.app.pump_speed_label_pump.grid(row=0)
        self.app.pump_speed_label_pump_2.grid(row=1)
        self.app.pump_speed_confirm_pump = tk.Button(
            self.app.pump_popup, text="Confirm", command=self.fill_single_reagent,
        )
        self.app.pump_speed_confirm_pump.place(x=150, y=70)
        self.app.cancel_button_pump = tk.Button(
            self.app.pump_popup, text="Cancel", command=self.app.pump_popup.destroy,
        )
        self.app.cancel_button_pump.place(x=350, y=70)

    def wash_btn_check(self):
        """Show a confirmation popup for the pump speed before washing tubes."""
        self.app.wash_popup = tk.Tk()
        self.app.wash_popup.geometry("500x100")
        self.app.wash_popup.title("Pump speed check point")
        self.app.pump_speed_label_wash = tk.Label(
            self.app.wash_popup,
            text=" Please confirm the current pump speed is " + self.app.pump_speed_input.get() + " ml/min!",
        )
        self.app.pump_speed_label_wash.place(x=15, y=10)
        self.app.pump_speed_confirm_wash = tk.Button(
            self.app.wash_popup, text="Confirm", command=self.wash_btn_handler,
        )
        self.app.pump_speed_confirm_wash.place(x=150, y=50)
        self.app.cancel_button_wash = tk.Button(
            self.app.wash_popup, text="Cancel", command=self.app.wash_popup.destroy,
        )
        self.app.cancel_button_wash.place(x=350, y=50)

    def wash_btn_handler(self):
        """Flush all fluidics lines with water by running the flush-all sequence."""
        self.app.wash_popup.destroy()
        speed = self._pump_speed_or_prompt()
        if speed is None:
            return
        self.app.fluidics.pumprate = speed
        if 0 in [
            self.app.device_status['selector_group'],
            self.app.device_status['pump_group'],
            self.app.device_status['relay_group'],
        ]:
            messagebox.showinfo(title="Config device", message="Please config selectors,pump and relay first!")
        else:
            self.app.fluidics.sequenceStatus = 0
            self.app.fluidics.connect_pump()
            self.app.fluidics.connect_relay()
            self.app.fluidics.connect_selector()
            self.app.fluidics.connect_heater()
            self.app.fluidics.select_chamber(not FluidicsConstants.SELECT_CHAMBER_STATE)
            self.app.fluidics.loadSequence(self.app.fluidics.FLUSH_ALL_SEQUENCE)
            t1 = Thread(target=self.app.fluidics.startSequence)
            t1.start()
            txt = _get_time() + "Wash with water\n"
            add_fluidics_status(txt)
            self.app.write_log(txt)
            t2 = Thread(target=self.sensor_fluidics_process)
            t2.start()

    def start_btn_check(self):
        """Confirmation window before an automated run: pump speed, z-stack settings and disk space.

        scope.json is read again here, so edits to the z-stack keys take effect
        without creating the experiment again. Confirm is disabled while a check
        fails, unless the override box is ticked.
        """
        with open(os.path.join("config_file", "scope.json"), 'r') as r:
            self.app.scope_cfg = json.load(r)
        self.app.imwidth = self.app.scope_cfg[0]["imwidth"]
        report = self.app.start_report = self.app.start_check()

        popup = self.app.start_popup = tk.Toplevel(self.app.parent_window)
        popup.title("Start check point")
        self.app.pump_speed_label_start = tk.Label(
            popup, text=" Please confirm the current pump speed is " + self.app.pump_speed_input.get() + " ml/min!",
        )
        self.app.pump_speed_label_start.pack(anchor="w", padx=10, pady=(10, 4))
        rows = ([(line, "black") for line in report["lines"]]
                + [("Warning: " + line, "darkorange") for line in report["warnings"]]
                + [("Check failed: " + line, "red") for line in report["errors"]])
        for text, colour in rows:
            tk.Label(popup, text=text, fg=colour, justify="left", wraplength=560).pack(anchor="w", padx=10)
        if report["lines"] or report["warnings"] or report["errors"]:
            verdict = "Checks failed" if report["errors"] else "All checks passed"
            tk.Label(popup, text=verdict, fg="red" if report["errors"] else "darkgreen").pack(anchor="w", padx=10, pady=4)
        buttons = tk.Frame(popup)
        self.app.pump_speed_confirm_start = tk.Button(buttons, text="Confirm", command=self.start_btn_handler)
        self.app.cancel_button_start = tk.Button(buttons, text="Cancel", command=popup.destroy)
        if report["errors"]:
            self.app.start_override = tk.IntVar(master=popup, value=0)
            self.app.pump_speed_confirm_start["state"] = "disabled"
            tk.Checkbutton(
                popup, text="Start anyway (override the failed checks)", variable=self.app.start_override,
                command=lambda: self.app.pump_speed_confirm_start.config(
                    state="normal" if self.app.start_override.get() else "disabled"),
            ).pack(anchor="w", padx=10)
        buttons.pack(pady=10)
        self.app.pump_speed_confirm_start.pack(side="left", padx=40)
        self.app.cancel_button_start.pack(side="left", padx=40)

    def start_btn_handler(self):
        """Save the calibrated pump speed, verify all devices are configured, and launch the automation sequence thread."""
        self.app.start_popup.destroy()
        speed = self._pump_speed_or_prompt()
        if speed is None:
            return
        # Save the value cleanly (one line, no stray newline) so it pre-fills the field next time.
        with open(os.path.join(self.app.cwd, "device", 'pump_speed_calibration.txt'), 'w') as fp:
            fp.write(self.app.pump_speed_input.get().strip() + "\n")
        self.app.fluidics.pumprate = speed
        if sum(self.app.device_status.values()) != len(self.app.device_status):
            messagebox.showinfo(title="config", message="Please config all devis!")
        else:
            self.app.process_index = 0
            self.app.process_index_limite = len(self.app.process_ls) - 1
            self.app.process_cycle = self.app.process_ls[self.app.process_index]
            self.app.cancel = 0
            self.app.fluidics.sequenceStatus = 0
            self.app.check_files()
            if self.app.check_file == 1:
                report = getattr(self.app, "start_report", None)
                if report is not None and report["lines"]:
                    self.app.record_start_settings(report)
                self.app.fluidics.connect_pump()
                self.app.fluidics.connect_relay()
                self.app.fluidics.connect_selector()
                self.app.fluidics.connect_heater()
                self.app.all_autobtn_disable()
                self.app.cancel_sequence_btn['state'] = 'normal'
                tt = Thread(target=self.app.start_sequence)
                tt.start()
            else:
                print("Missing files!")

    def run_fluidics_cycle(self, sequence):
        """Load and execute a single fluidics sequence on the fluidics system."""
        self.app.fluidics.loadSequence(sequence)
        self.app.fluidics.startSequence()
