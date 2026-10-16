"""Workspace and directory selection panel for the Seq-o-Matic GUI.

Handles browsing for work directories and opening experiment profile editors
in both auto and manual modes.
"""

import os
from tkinter import filedialog, messagebox

from front_end.experiment_profile import Exp_profile


class WorkspacePanel:
    """Manages workspace directory selection and experiment profile creation.

    Args:
        app: The main window_widgets instance providing shared state and widget references.
    """

    # Grayed out while the connection check runs and until Create finishes: Create on both tabs (no second Create
    # inside the first) and everything the check depends on (upload boxes, server user/host fields).
    _LOCKED_DURING_CHECK = (
        "info_btn_auto", "info_btn_manual", "upload_aws_auto", "upload_aws_manual",
        "change_server_auto_cb", "change_server_manual_cb", "account_field_auto", "account_field_manual",
        "server_field_auto", "server_field_manual",
    )

    def __init__(self, app):
        self.app = app
        self._locked = []
        self._busy = None

    def browse_handler_auto(self):
        """Open a directory chooser dialog and set the selected path in the auto tab work path field."""
        self.app.tempdir = self.search_for_file_path()
        self.app.path.set(self.app.tempdir)
        self.app.work_path_field_auto.config(textvariable=self.app.path)

    def browse_handler_manual(self):
        """Open a directory chooser dialog and set the selected path in the manual tab work path field."""
        self.app.tempdir = self.search_for_file_path()
        self.app.path.set(self.app.tempdir)
        self.app.work_path_field_manual.config(textvariable=self.app.path)

    def search_for_file_path(self):
        """Display a tkinter directory selection dialog and return the chosen path."""
        self.app.currdir = os.getcwd()
        self.app.tempdir = filedialog.askdirectory(
            parent=self.app.parent_window,
            initialdir=self.app.currdir,
            title='Please select a directory',
        )
        if len(self.app.tempdir) > 0:
            print("You chose: %s" % self.app.tempdir)
        return self.app.tempdir

    def exp_btn_handler(self):
        """Open the experiment profile editor for the auto tab's work directory."""
        if self.app.work_path_field_auto.get() == "":
            messagebox.showinfo(title="Miss Input", message="Please fill the work dirctory first!")
        else:
            work_path = self.app.work_path_field_auto.get()
            Exp_profile(work_path)

    def exp_btn_handler_manual(self):
        """Open the experiment profile editor for the manual tab's work directory."""
        if self.app.work_path_field_manual.get() == "":
            messagebox.showinfo(title="Miss Input", message="Please fill the work dirctory first!")
        else:
            work_path = self.app.work_path_field_manual.get()
            Exp_profile(work_path)

    def _show_storage(self, settings):
        """Show freshly loaded settings in the GUI: the read-only bucket / folder always, and the server user/host
        where the field is empty (a bad file at startup) or still shows the previously loaded file's value
        (storage.json edited while the GUI is open). A value the operator typed is kept."""
        shown = self.app.storage_shown
        self.app.aws_bucket_var.set(settings.aws_bucket)
        self.app.server_root_var.set(settings.server_root)
        for var, new, old in ((self.app.account, settings.server_user, shown and shown.server_user),
                              (self.app.server_host_var, settings.server_host, shown and shown.server_host)):
            if not var.get().strip() or var.get() == old:
                var.set(new)
        self.app.storage_shown = settings

    def _open_busy_window(self, text):
        """A small modal window showing ``text``: until _end_busy destroys it, the rest of the program cannot be
        clicked (Start, Prime, Wash, Fill included) and the window itself cannot be closed."""
        import tkinter as tk
        win = tk.Toplevel(self.app.parent_window)
        win.title("Please wait")
        win.transient(self.app.parent_window)
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        win.label = tk.Label(win, text=text, padx=40, pady=20)
        win.label.pack()
        win.update_idletasks()
        try:
            win.grab_set()  # released when the window is destroyed
        except tk.TclError:  # not viewable (e.g. hidden by the dry-run harness): it stays non-modal
            pass
        return win

    def _begin_busy(self, text):
        """Gray out the _LOCKED_DURING_CHECK widgets (remembering their states) and show the busy window."""
        self._locked = [(w, w.cget("state")) for w in (getattr(self.app, n) for n in self._LOCKED_DURING_CHECK)]
        for w, _state in self._locked:
            w.config(state="disabled")
        self._busy = self._open_busy_window(text)

    def _end_busy(self):
        """Undo _begin_busy: restore each widget's earlier state and close the busy window. Safe to call twice."""
        import tkinter as tk
        for w, state in self._locked:
            try:
                w.config(state=state)
            except tk.TclError:  # the main window is being closed
                pass
        self._locked = []
        if self._busy is not None:
            try:
                self._busy.destroy()
            except tk.TclError:
                pass
            self._busy = None

    def _storage_ok(self, check_connections=True):
        """Load config_file/storage.json and test the AWS / server connections the operator ticked.

        The server tested is the user@host in the GUI fields (shared by both tabs). Returns False (after showing
        an error dialog and writing to the warning panel) when storage.json is missing or invalid, or when a
        connection check fails or does not report; the experiment is then not created. With
        ``check_connections=False`` (manual mode, which never uploads images) only the file is checked.
        """
        import threading
        from front_end.logwindow import add_highlight_mainwindow, update_error
        from system import connection_check
        from system.storage_settings import StorageSettings, StorageSettingsError, default_path

        try:
            settings = StorageSettings.load(default_path())
        except StorageSettingsError as e:
            msg = "storage.json error: " + str(e)
            messagebox.showerror(title="Storage settings", message=msg)
            update_error(msg + "\n")
            return False
        self._show_storage(settings)
        server = self.app.account.get() + "@" + self.app.server_host_var.get()
        use_aws = self.app.upload_aws_value.get() == 1
        use_server = self.app.change_server_value.get() == 1
        if not check_connections or not (use_aws or use_server):
            self.app.storage = settings
            return True
        add_highlight_mainwindow("Testing connections...\n")
        # Gray out Create and the inputs the check depends on, so the values used are the values checked. On success
        # they stay grayed out until create_exp_auto finishes (it calls _end_busy).
        self._begin_busy("Checking connections...")
        results = []

        def run_checks():
            try:
                results.extend(connection_check.check_all(settings, server, use_aws, use_server))
            except Exception as e:  # a crash must block, not pass with no results
                results.append(connection_check.CheckResult("connection test", False,
                                                            f"crashed: {type(e).__name__}: {e}"))
        worker = threading.Thread(target=run_checks, daemon=True)
        worker.start()
        while worker.is_alive():  # keep the window responsive while ssh / aws run
            self.app.parent_window.update()
            worker.join(timeout=0.05)
        for r in results:
            add_highlight_mainwindow(str(r) + "\n")
        failed = [r for r in results if not r.ok]
        expected = int(use_aws) + int(use_server)
        if not failed and len(results) != expected:
            failed = [connection_check.CheckResult("connection test", False,
                                                   f"{len(results)} of {expected} checks reported")]
        if failed:
            # Name the box(es) whose check failed; a crashed or incomplete test names every ticked box.
            names = [r.name for r in failed]
            aws_failed = use_aws and any(not n.startswith("server ") for n in names)
            server_failed = use_server and any(not n.startswith("AWS bucket ") for n in names)
            boxes = [b for b, on in (("'upload to AWS'", aws_failed), ("'Send to storage server'", server_failed))
                     if on]
            msg = ("Connection test failed:\n" + "\n".join(str(r) for r in failed)
                   + "\n\nTo create the experiment without this upload, untick " + " or ".join(boxes) + ".")
            self._end_busy()  # so the boxes can be unticked
            messagebox.showerror(title="Connection test failed", message=msg)
            update_error(msg + "\n")
            return False
        # Only now: a failed storage.json or connection check must not change what an experiment created earlier
        # uploads with. (A later failure in create_exp_*, e.g. Micro-Manager not running, still replaces it, as it
        # replaces pos_path and server, as on main.)
        self.app.storage = settings
        self._busy.label.config(text="Creating experiment...")
        self._busy.update_idletasks()
        return True

    def create_exp_auto(self):
        """Validate auto tab inputs, initialize the microscope and fluidics systems, and prepare the full automation protocol.

        The busy window and grayed-out inputs opened by the connection check close when Create finishes, however it ends.
        """
        try:
            self._create_exp_auto()
        finally:
            self._end_busy()

    def _create_exp_auto(self):
        import json
        import pandas as pd
        from front_end.logwindow import (
            Log_window, clear_error, clear_log,
            add_highlight_mainwindow, update_error,
        )
        from system.fluidics_exchange_system import FluidicSystem
        from system.image_acquisition_and_analysis_system import scope

        clear_error()
        clear_log()
        self.app.clear_align_canvas()
        self.app.clear_tile_canvas()
        self.app.clear_focus_canvas()
        self.app.slice_per_slide_reformat()
        self.app.cancel = 0
        self.app.skip_alignment = self.app.mock_alignment.get()
        Log_window.warning_stw.delete('1.0', 'end')
        if self.app.work_path_field_auto.get() == "":
            messagebox.showinfo(title="Wrong Input", message="work directory can't be empty")
            return
        if not self._storage_ok():
            return
        self.app.pos_path = self.app.work_path_field_auto.get()
        if not os.path.exists(os.path.join(self.app.pos_path, "temp.txt")):
            open(os.path.join(self.app.pos_path, "temp.txt"), 'w')
        if not os.path.exists(os.path.join(self.app.pos_path, "log.txt")):
            open(os.path.join(self.app.pos_path, "log.txt"), 'w')
        # log.txt holds only the program's own log lines, once each (as in the reference);
        # the extra logging messages go to the GUI panels and the console.
        self.app.server = self.app.account_field_auto.get() + "@" + self.app.server_field_auto.get()
        self.app.assign_cycle_detail()
        with open(os.path.join("config_file", "scope.json"), 'r') as r:
            self.app.scope_cfg = json.load(r)
            self.app.imwidth = self.app.scope_cfg[0]["imwidth"]
        try:
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
                storage=self.app.storage,
            )
        except Exception as e:
            messagebox.showinfo(title="Config failure ",
                                message="Please run micromanager first!")
            update_error("Please run micromanager first!")
            return
        if self.app.assigned_heater == 0:
            self.app.heater_dict = {
                'chamber1': "heatstage1",
                'chamber2': "heatstage2",
                'chamber3': "heatstage3",
            }
            self.app.chamber_number = 3
        self.app.fluidics = FluidicSystem(
            system_path=self.app.system_path,
            pos_path=self.app.pos_path,
            slide_hearter_dictionary=self.app.heater_dict,
        )
        self.app.check_sequence(self.app.chamber_number)
        # End-of-run uploads follow these two boxes, read once when the experiment is created.
        self.app.AWS = 1 if self.app.upload_aws_value.get() == 1 else 0
        self.app.Local_upload = 1 if self.app.change_server_value.get() == 1 else 0

    def create_exp_manual(self):
        """Validate manual tab inputs, initialize the microscope scope, and prepare for manual imaging of a single cycle."""
        import json
        import pandas as pd
        from front_end.logwindow import (
            clear_error, clear_log, add_highlight_mainwindow, update_error,
        )
        from system.image_acquisition_and_analysis_system import scope

        clear_error()
        clear_log()
        self.app.clear_align_canvas()
        self.app.clear_tile_canvas()
        self.app.clear_focus_canvas()
        self.app.cycle_number = self.app.sb1_cycle_number.get()
        self.app.current_cycle = self.app.current_c.get() + self.app.sb1_cycle_number.get().zfill(2)
        if "00" in self.app.current_cycle:
            self.app.current_cycle = "cycle00"

        self.app.skip_alignment = self.app.mock_alignment.get()
        self.app.protocol_list_index = 0
        self.app.server = self.app.account_field_manual.get() + "@" + self.app.server_field_manual.get()
        if self.app.work_path_field_manual.get() == "":
            messagebox.showinfo(title="Wrong Input", message="work directory can't be empty")
            return
        self.app.pos_path = self.app.work_path_field_manual.get()
        if self.app.current_c.get() == "":
            messagebox.showinfo(title="Wrong Input", message="current cycle type can't be empty")
            return
        if self.app.slice_number_field_manual.get() == "":
            messagebox.showinfo(title="Wrong Input", message="slice per slide can't be empty")
            return
        # Manual mode never uploads images (only the note, by the "Send note to server" button), so no connection
        # checks; a bad storage.json still blocks.
        if not self._storage_ok(check_connections=False):
            return
        # Again after _storage_ok, which may have refreshed the user/host fields from storage.json.
        self.app.server = self.app.account_field_manual.get() + "@" + self.app.server_field_manual.get()
        self.app.slice_per_slide_reformat_manual()
        self.app.protocol_list = [self.app.current_cycle]
        if "00" in self.app.current_cycle:
            self.app.align_btn["state"] = "disable"
            self.app.tile_btn["state"] = "disable"
            self.app.max_btn["state"] = "disable"
        else:
            self.app.align_btn["state"] = "normal"
            self.app.tile_btn["state"] = "normal"
            self.app.max_btn["state"] = "normal"
        if not os.path.exists(os.path.join(self.app.pos_path, "log.txt")):
            open(os.path.join(self.app.pos_path, "log.txt"), 'a').close()
        print(self.app.slice_per_slide)
        with open(os.path.join("config_file", "scope.json"), 'r') as r:
            self.app.scope_cfg = json.load(r)
            self.app.imwidth = self.app.scope_cfg[0]["imwidth"]
        try:
            self.app.scope = scope(
                self.app.scope_cfg, self.app.pos_path, self.app.slice_per_slide,
                self.app.server, self.app.skip_alignment, 0,
                system_path=self.app.system_path,
                storage=self.app.storage,
            )
        except Exception as e:
            messagebox.showinfo(title="Config failure ",
                                message="Please run micromanager first!")
            update_error("Please run micromanager first!")
            return
        from front_end.Widgets import get_time
        txt = (get_time() + "\n" + "work directory: " + self.app.pos_path + "\n"
               + "Current cycle: " + self.app.protocol_list[self.app.protocol_list_index] + "\n")
        print(txt)
        self.app.write_log(txt)
        add_highlight_mainwindow(txt)
        if not os.path.exists(os.path.join(self.app.pos_path, "manual_process_record.csv")):
            df = pd.DataFrame(columns=["protocol"])
            df["protocol"] = "imagecycle_" + self.app.current_cycle
            df.to_csv(os.path.join(self.app.pos_path, "manual_process_record.csv"), index=False)
        else:
            df = pd.read_csv(os.path.join(self.app.pos_path, "manual_process_record.csv"))
            df.loc[len(df.index)] = ["imagecycle_" + self.app.current_cycle]
            df.to_csv(os.path.join(self.app.pos_path, "manual_process_record.csv"), index=False)
        self.app.focus_btn["state"] = "normal"
        self.app.scope.move_to_image()
