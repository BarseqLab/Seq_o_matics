"""Call sites of storage.json: no hardcoded lab values left, the AWS upload commands, and the experiment-creation block."""

import contextlib
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CODE = os.path.join(ROOT, "code")

GOOD = {"aws_bucket": "labB-bucket", "aws_prefix": "labB", "aws_storage_class": "STANDARD",
        "aws_upload_retries": 2, "server_user": "u", "server_host": "h", "server_root": "/data/x/"}


def _load_system(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(CODE, "system", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("system", types.ModuleType("system")).__path__ = [os.path.join(CODE, "system")]
    sys.modules["system." + name] = mod
    spec.loader.exec_module(mod)
    return mod


ss = _load_system("storage_settings")
cc = _load_system("connection_check")
S = ss.StorageSettings.from_dict(GOOD)


class TestNoHardcodedLabValues(unittest.TestCase):
    def test_literals_only_in_storage_json(self):
        needles = ("barseq-acquisition", "10.128.30.152", "/mnt/imagestorage", "aixin.zhang")
        hits = []
        for dirpath, dirs, files in os.walk(CODE):
            dirs[:] = [d for d in dirs if d not in ("supplementary", "__pycache__")]
            for f in files:
                if not f.endswith((".py", ".json")) or f == "storage.json":
                    continue
                with open(os.path.join(dirpath, f), encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
                hits += [(os.path.join(dirpath, f), n) for n in needles if n in text]
        self.assertEqual(hits, [])


@contextlib.contextmanager
def stubbed_front_end():
    """Import front_end.panels.* with the GUI-heavy modules replaced by stubs; yields (status_panel, workspace_panel)."""
    logged = []
    logwindow = types.ModuleType("front_end.logwindow")
    logwindow.add_highlight_mainwindow = lambda t: logged.append(("log", t))
    logwindow.update_error = lambda t: logged.append(("error", t))
    logwindow.widge_attr = types.SimpleNamespace(normal_color="", disable_color="")
    logwindow.clear_error = logwindow.clear_log = lambda: None
    logwindow.Log_window = types.SimpleNamespace(warning_stw=types.SimpleNamespace(delete=lambda *a: None))
    zstd = types.ModuleType("zstandard")

    class Comp:
        def __init__(self, **kw):
            pass

        def stream_writer(self, f):
            return contextlib.nullcontext(f)
    zstd.ZstdCompressor = Comp
    stubs = {
        "front_end": types.ModuleType("front_end"), "front_end.panels": types.ModuleType("front_end.panels"),
        "front_end.logwindow": logwindow, "front_end.experiment_profile": types.SimpleNamespace(Exp_profile=None),
        "zstandard": zstd,
    }
    stubs["front_end"].__path__ = [os.path.join(CODE, "front_end")]
    stubs["front_end.panels"].__path__ = [os.path.join(CODE, "front_end", "panels")]
    with mock.patch.dict(sys.modules, stubs):
        mods = []
        for name in ("status_panel", "workspace_panel"):
            spec = importlib.util.spec_from_file_location(
                "front_end.panels." + name, os.path.join(CODE, "front_end", "panels", name + ".py"))
            mod = importlib.util.module_from_spec(spec)
            sys.modules["front_end.panels." + name] = mod
            spec.loader.exec_module(mod)
            mods.append(mod)
        mods[0]._get_time = lambda: ""
        yield mods[0], mods[1], logged


class TestAwsUpload(unittest.TestCase):
    def test_commands_use_storage_settings(self):
        with stubbed_front_end() as (status_panel, _ws, logged), tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "expA_maxprojection", "c1"))
            with open(os.path.join(tmp, "expA_maxprojection", "c1", "f.txt"), "w") as f:
                f.write("x")
            app = types.SimpleNamespace(pos_path="X:\\expA", storage=S,
                                        scope=types.SimpleNamespace(maxprojection_drive=tmp))
            calls = []

            def fake_run(args, **kw):
                calls.append(args)
                return types.SimpleNamespace(returncode=1)  # always fails: exercises the retry count
            with mock.patch.object(status_panel.subprocess, "run", fake_run):
                status_panel.StatusPanel(app).upload_aws_handler()
        self.assertEqual(len(calls), 2)  # aws_upload_retries
        self.assertEqual(calls[0][:4], ["aws", "s3", "cp", calls[0][3]])
        self.assertEqual(calls[0][4], "s3://labB-bucket/labB/expA_maxprojection/c1.tar.zst")
        self.assertIn("STANDARD", calls[0])
        self.assertIn("SHA256", calls[0])
        self.assertTrue(any("labB-bucket" in t for k, t in logged))  # effective destination is logged


class FakeVar:
    """A Tk variable, or an Entry (get() plus a widget state)."""
    def __init__(self, v):
        self.v = v
        self.state = "normal"

    def get(self):
        return self.v

    def set(self, v):
        self.v = v

    def cget(self, key):
        return self.state

    def config(self, state):
        self.state = state


LOCKED = ("info_btn_auto", "info_btn_manual", "upload_aws_auto", "upload_aws_manual", "change_server_auto_cb",
          "change_server_manual_cb", "account_field_auto", "account_field_manual", "server_field_auto",
          "server_field_manual")


class FakeWidget:
    def __init__(self, state="normal"):
        self.state = state

    def cget(self, key):
        return self.state

    def config(self, state):
        self.state = state


class FakeBusy:
    """Stands in for the "Checking connections..." window; records its texts and when it was closed."""
    def __init__(self, events, text):
        self.events, self.texts = events, [text]
        events.append(("busy open", text))
        self.label = types.SimpleNamespace(config=lambda text: self.texts.append(text))

    def update_idletasks(self):
        pass

    def destroy(self):
        self.events.append(("busy closed", self.texts[-1]))


def add_fake_widgets(app, ws, events):
    """Give a fake app the widgets the check grays out, and replace the busy window by FakeBusy."""
    for name in LOCKED:
        if not hasattr(app, name):
            setattr(app, name, FakeWidget())
    app.widget_states = lambda: {n: getattr(app, n).state for n in LOCKED}
    ws.WorkspacePanel._open_busy_window = lambda self, text: FakeBusy(events, text)


class TestExperimentCreationBlock(unittest.TestCase):
    def _app(self, aws=0, server=0, user="u", host="h"):
        return types.SimpleNamespace(storage=None, storage_shown=None,
                                     upload_aws_value=FakeVar(aws), change_server_value=FakeVar(server),
                                     account=FakeVar(user), server_host_var=FakeVar(host),
                                     aws_bucket_var=FakeVar(""), server_root_var=FakeVar(""),
                                     parent_window=types.SimpleNamespace(update=lambda: None))

    def _run(self, write_json, aws=0, server=0, runner=None, app=None, check_connections=True, check_all=None):
        with stubbed_front_end() as (_st, ws, logged), tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "config_file"))
            if write_json is not None:
                with open(os.path.join(tmp, "config_file", "storage.json"), "w") as f:
                    json.dump(write_json, f)
            dialogs = []
            self.events = events = []
            ws.messagebox = types.SimpleNamespace(showerror=lambda **kw: dialogs.append(kw) or events.append("dialog"),
                                                  showinfo=lambda **kw: dialogs.append(kw))
            app = app or self._app(aws, server)
            add_fake_widgets(app, ws, events)
            old = os.getcwd()
            os.chdir(tmp)
            try:
                with mock.patch.object(cc, "run_command", runner or (lambda a, t=20: (0, "", ""))), \
                        mock.patch.object(cc, "check_all", check_all or cc.check_all):
                    ok = ws.WorkspacePanel(app)._storage_ok(check_connections=check_connections)
            finally:
                os.chdir(old)
        return ok, app, dialogs, logged

    def test_check_grays_out_inputs_and_create_then_restores_them(self):
        """While the check runs, Create (both tabs), the upload boxes and the user/host fields are grayed out and a
        "Checking connections..." window is shown; on failure both are undone before the error dialog."""
        seen = []
        app = self._app(aws=1, server=1)
        app.account_field_auto = FakeWidget("disabled")  # restored to what it was, not to "normal"

        def runner(args, timeout=20):
            seen.append(app.widget_states())
            return (255, "", "nope")
        ok, app, dialogs, _l = self._run(GOOD, app=app, runner=runner)
        self.assertFalse(ok)
        self.assertTrue(seen and all(all(st == "disabled" for st in states.values()) for states in seen))
        before = {n: "normal" for n in LOCKED}
        before["account_field_auto"] = "disabled"
        self.assertEqual(app.widget_states(), before)
        self.assertEqual(self.events, [("busy open", "Checking connections..."),
                                       ("busy closed", "Checking connections..."), "dialog"])

    def test_no_boxes_ticked_shows_no_window(self):
        ok, app, dialogs, _l = self._run(GOOD)
        self.assertTrue(ok)
        self.assertEqual(self.events, [])
        self.assertTrue(all(st == "normal" for st in app.widget_states().values()))

    def test_missing_file_blocks(self):
        ok, app, dialogs, logged = self._run(None)
        self.assertFalse(ok)
        self.assertEqual(len(dialogs), 1)
        self.assertIn("storage.json", dialogs[0]["message"])
        self.assertTrue(any(k == "error" for k, _ in logged))

    def test_typo_key_blocks(self):
        bad = dict(GOOD)
        bad["aws_bucked"] = bad.pop("aws_bucket")
        ok, _app, dialogs, _l = self._run(bad)
        self.assertFalse(ok)
        self.assertIn("aws_bucked", dialogs[0]["message"])

    def test_valid_file_without_uploads_passes_and_loads_settings(self):
        ok, app, dialogs, _l = self._run(GOOD)
        self.assertTrue(ok)
        self.assertEqual(dialogs, [])
        self.assertEqual(app.storage.aws_bucket, "labB-bucket")

    def test_connection_failure_blocks(self):
        def runner(args, timeout=20):
            return (255, "", "ssh: connect to host h port 22: Connection timed out") if args[0] == "ssh" else (0, "", "")
        ok, _app, dialogs, logged = self._run(GOOD, aws=1, server=1, runner=runner)
        self.assertFalse(ok)
        self.assertIn("Connection test failed", dialogs[0]["message"])
        self.assertIn("server u@h", dialogs[0]["message"])

    def test_connection_success_passes(self):
        ok, _app, dialogs, logged = self._run(GOOD, aws=1, server=1)
        self.assertTrue(ok)
        self.assertEqual(dialogs, [])
        self.assertEqual(len([t for k, t in logged if "OK" in t]), 2)

    def test_fields_left_empty_by_a_bad_startup_file_are_filled(self):
        """storage.json was bad at startup and fixed later: the empty user/host get the file's values, the check
        uses them (not '@'), and the read-only bucket / folder show what will be used."""
        calls = []

        def runner(args, timeout=20):
            calls.append(args)
            return (0, "", "")
        app = self._app(server=1, user="", host="")
        ok, app, _d, _l = self._run(GOOD, runner=runner, app=app)
        self.assertTrue(ok)
        self.assertEqual((app.account.get(), app.server_host_var.get()), ("u", "h"))
        self.assertEqual((app.aws_bucket_var.get(), app.server_root_var.get()), ("labB-bucket", "/data/x/"))
        self.assertEqual(calls[0][5], "u@h")

    def test_manual_mode_skips_connection_checks_but_still_loads_the_file(self):
        calls = []

        def runner(args, timeout=20):
            calls.append(args)
            return (255, "", "would fail")
        ok, app, dialogs, _l = self._run(GOOD, aws=1, server=1, runner=runner, check_connections=False)
        self.assertTrue(ok)
        self.assertEqual((calls, dialogs), ([], []))
        self.assertEqual(app.storage.aws_bucket, "labB-bucket")
        bad = dict(GOOD)
        bad["aws_bucked"] = bad.pop("aws_bucket")
        ok, _app, dialogs, _l = self._run(bad, aws=1, server=1, check_connections=False)
        self.assertFalse(ok)  # a bad storage.json still blocks manual mode
        self.assertIn("aws_bucked", dialogs[0]["message"])

    def test_crashed_check_blocks(self):
        def boom(*a, **kw):
            raise RuntimeError("unexpected")
        ok, _app, dialogs, logged = self._run(GOOD, aws=1, check_all=boom)
        self.assertFalse(ok)
        self.assertIn("RuntimeError: unexpected", dialogs[0]["message"])
        self.assertTrue(any(k == "error" for k, _ in logged))

    def test_missing_results_block(self):
        ok, _app, dialogs, _l = self._run(GOOD, aws=1, server=1, check_all=lambda *a, **kw: [])
        self.assertFalse(ok)
        self.assertIn("Connection test failed", dialogs[0]["message"])

    def test_fields_still_showing_the_previous_file_are_refreshed(self):
        """storage.json edited while the GUI is open: user/host that still show the previously loaded values
        follow the file, so the old server is not checked against the new server_root."""
        calls = []

        def runner(args, timeout=20):
            calls.append(args)
            return (0, "", "")
        app = self._app(server=1, user="old", host="oldhost")
        app.storage_shown = ss.StorageSettings.from_dict({**GOOD, "server_user": "old", "server_host": "oldhost"})
        ok, app, _d, _l = self._run(GOOD, runner=runner, app=app)
        self.assertTrue(ok)
        self.assertEqual((app.account.get(), app.server_host_var.get()), ("u", "h"))
        self.assertEqual(calls[0][5], "u@h")
        self.assertEqual(app.storage_shown.server_user, "u")

    def test_failed_check_keeps_the_previous_settings(self):
        """A failed Create must not change what an experiment created earlier uploads with."""
        app = self._app(aws=1)
        app.storage = previous = object()
        ok, app, dialogs, _l = self._run(GOOD, app=app, runner=lambda a, t=20: (255, "", "nope"))
        self.assertFalse(ok)
        self.assertIs(app.storage, previous)

    def test_block_dialog_says_how_to_go_on_without_the_upload(self):
        ok, _app, dialogs, _l = self._run(GOOD, aws=1, server=1, runner=lambda a, t=20: (255, "", "nope"))
        self.assertFalse(ok)
        self.assertIn("untick", dialogs[0]["message"])
        self.assertIn("'upload to AWS'", dialogs[0]["message"])
        self.assertIn("'Send to storage server'", dialogs[0]["message"])

    def test_server_edited_in_the_gui_is_kept(self):
        calls = []

        def runner(args, timeout=20):
            calls.append(args)
            return (0, "", "")
        ok, app, _d, _l = self._run(GOOD, server=1, runner=runner, app=self._app(server=1, user="me", host="box"))
        self.assertTrue(ok)
        self.assertEqual((app.account.get(), app.server_host_var.get()), ("me", "box"))
        self.assertEqual(calls[0][5], "me@box")


class TestCreateExperiment(unittest.TestCase):
    """create_exp_auto / create_exp_manual end to end, with the hardware, pandas and Tk replaced by stubs."""

    def _app(self, tmp, aws=1, server=1):
        f = FakeVar
        noop = lambda *a, **kw: None
        return types.SimpleNamespace(
            storage=None, storage_shown=None, upload_aws_value=f(aws), change_server_value=f(server),
            account=f("u"), server_host_var=f("h"), aws_bucket_var=f(""), server_root_var=f(""),
            account_field_auto=f("u"), server_field_auto=f("h"), account_field_manual=f("u"),
            server_field_manual=f("h"), work_path_field_auto=f(tmp), work_path_field_manual=f(tmp),
            parent_window=types.SimpleNamespace(update=noop), mock_alignment=f(0), system_path=tmp,
            clear_align_canvas=noop, clear_tile_canvas=noop, clear_focus_canvas=noop,
            slice_per_slide_reformat=noop, slice_per_slide_reformat_manual=noop, slice_per_slide=[1],
            assign_cycle_detail=noop, check_sequence=noop, assigned_heater=1, heater_dict={}, chamber_number=1,
            sb1_cycle_number=f("1"), current_c=f("geneseq"), slice_number_field_manual=f("1"),
            server=f("h"),  # the Tk host variable until Create replaces it with "user@host"
        )

    def _create(self, mode, app_kw=None, runner=None, edit_app=None):
        scopes = []
        hw = {
            "pandas": types.ModuleType("pandas"),
            "system.fluidics_exchange_system": types.SimpleNamespace(FluidicSystem=lambda **kw: "fluidics"),
            "system.image_acquisition_and_analysis_system": types.SimpleNamespace(
                scope=lambda *a, **kw: scopes.append((a, kw)) or "scope"),
            "front_end.Widgets": types.SimpleNamespace(get_time=lambda: ""),
        }
        with stubbed_front_end() as (_st, ws, logged), tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(sys.modules, hw):
            os.makedirs(os.path.join(tmp, "config_file"))
            with open(os.path.join(tmp, "config_file", "storage.json"), "w") as fh:
                json.dump(GOOD, fh)
            with open(os.path.join(tmp, "config_file", "scope.json"), "w") as fh:
                json.dump([{"imwidth": 10}], fh)
            dialogs = []
            ws.messagebox = types.SimpleNamespace(showerror=lambda **kw: dialogs.append(kw),
                                                  showinfo=lambda **kw: dialogs.append(kw))
            app = self._app(tmp, **(app_kw or {}))
            self.events = events = []
            add_fake_widgets(app, ws, events)
            if edit_app:
                edit_app(app)
            old = os.getcwd()
            os.chdir(tmp)
            try:
                with mock.patch.object(cc, "run_command", runner or (lambda a, t=20: (0, "", ""))):
                    getattr(ws.WorkspacePanel(app), "create_exp_" + mode)()
            except _Stop:
                pass
            finally:
                os.chdir(old)
        return app, scopes, dialogs

    def test_auto_success_creates_with_the_loaded_settings(self):
        app, scopes, dialogs = self._create("auto")
        self.assertEqual(dialogs, [])
        self.assertEqual(len(scopes), 1)
        self.assertIs(scopes[0][1]["storage"], app.storage)
        self.assertEqual(app.storage.aws_bucket, "labB-bucket")
        self.assertEqual((app.server, app.AWS, app.Local_upload), ("u@h", 1, 1))

    def test_auto_failed_check_creates_nothing(self):
        app, scopes, dialogs = self._create("auto", runner=lambda a, t=20: (255, "", "nope"))
        self.assertEqual(scopes, [])
        self.assertIsNone(app.storage)
        self.assertFalse(hasattr(app, "AWS"))
        self.assertIn("Connection test failed", dialogs[0]["message"])

    def test_window_and_gray_out_last_until_create_finishes(self):
        at_scope = []

        def edit(app):
            hw_scope = sys.modules["system.image_acquisition_and_analysis_system"]
            real = hw_scope.scope

            def scope(*a, **kw):
                at_scope.append((app.widget_states(), list(self.events)))
                return real(*a, **kw)
            hw_scope.scope = scope
        app, scopes, dialogs = self._create("auto", edit_app=edit)
        self.assertEqual(len(scopes), 1)
        states, events = at_scope[0]
        self.assertTrue(all(st == "disabled" for st in states.values()))  # still grayed out while Create works
        self.assertEqual(events, [("busy open", "Checking connections...")])
        self.assertTrue(all(st == "normal" for st in app.widget_states().values()))
        self.assertEqual(self.events[-1], ("busy closed", "Creating experiment..."))

    def test_window_closes_when_create_fails_after_the_check(self):
        def edit(app):
            def no_micromanager(*a, **kw):
                raise RuntimeError("Micro-Manager not running")
            sys.modules["system.image_acquisition_and_analysis_system"].scope = no_micromanager
        app, scopes, dialogs = self._create("auto", edit_app=edit)
        self.assertIn("micromanager", dialogs[0]["message"])
        self.assertEqual(self.events[-1][0], "busy closed")
        self.assertTrue(all(st == "normal" for st in app.widget_states().values()))

    def test_manual_ticked_boxes_run_no_checks(self):
        calls = []

        def runner(args, timeout=20):
            calls.append(args)
            return (255, "", "would fail")

        def stop_after_scope(app):  # the rest of manual Create (log, csv, buttons) is not under test
            app.align_btn, app.tile_btn, app.max_btn = {}, {}, {}

            def stop(_txt):
                raise _Stop
            app.write_log = stop
        app, scopes, dialogs = self._create("manual", runner=runner, edit_app=stop_after_scope)
        self.assertEqual(calls, [])
        self.assertEqual(len(scopes), 1)
        self.assertEqual(app.server, "u@h")

    def test_manual_uses_the_refreshed_fields(self):
        """As in Tk, both tabs' user/host Entries share one variable each. They start empty (bad startup file);
        manual Create fills them from storage.json and must then use them, not '@'."""
        def setup(app):
            app.account.set("")
            app.server_host_var.set("")
            app.account_field_auto = app.account_field_manual = app.account
            app.server_field_auto = app.server_field_manual = app.server_host_var
            app.align_btn, app.tile_btn, app.max_btn = {}, {}, {}

            def stop(_txt):
                raise _Stop
            app.write_log = stop
        app, scopes, dialogs = self._create("manual", edit_app=setup)
        self.assertEqual(len(scopes), 1)
        self.assertEqual(app.server, "u@h")
        self.assertEqual(scopes[0][0][3], "u@h")  # scope(cfg, pos_path, slice_per_slide, server, ...)

    def test_block_hint_names_only_the_failed_upload(self):
        def runner(args, timeout=20):
            return (255, "", "nope") if args[0] == "aws" else (0, "", "")
        app, scopes, dialogs = self._create("auto", runner=runner)
        msg = dialogs[0]["message"]
        self.assertIn("untick 'upload to AWS'.", msg)
        self.assertNotIn("Send to storage server", msg)

    def test_manual_early_return_still_sets_the_server_string(self):
        """As on main: "Send note to server" after an early return uses user@host, not the Tk variable."""
        app, scopes, dialogs = self._create("manual", edit_app=lambda a: setattr(a, "current_c", FakeVar("")))
        self.assertEqual(scopes, [])
        self.assertEqual(app.server, "u@h")
        self.assertIn("current cycle type", dialogs[0]["message"])


class TestBusyWindowRealTk(unittest.TestCase):
    """The gray-out and the busy window with real Tk widgets and a real event loop (a slow fake check)."""

    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as e:
            self.skipTest(f"no Tk display: {e}")
        self.root.geometry("200x100+-3000+-3000")  # shown (a grab needs a viewable window), but off screen
        self.root.update()
        self.tk = tk

    def tearDown(self):
        self.root.destroy()

    def test_create_is_grayed_out_and_the_window_shows_during_the_check(self):
        import threading
        tk, root = self.tk, self.root
        # The check waits until the probe has looked at the GUI. A plain Lock, not time.sleep or Event: other tests
        # (test_fakes) leave dryrun.clock's 1000x virtual time installed, which patches both.
        probed = threading.Lock()
        probed.acquire()
        clicks = []
        app = types.SimpleNamespace(parent_window=root, storage=None, storage_shown=None,
                                    upload_aws_value=tk.IntVar(root, 1), change_server_value=tk.IntVar(root, 0),
                                    account=tk.StringVar(root, "u"), server_host_var=tk.StringVar(root, "h"),
                                    aws_bucket_var=tk.StringVar(root), server_root_var=tk.StringVar(root))
        for name in LOCKED:
            if name.startswith("info_btn"):
                w = tk.Button(root, command=lambda: clicks.append("create"))
            elif name.endswith("_cb") or name.startswith("upload_aws"):
                w = tk.Checkbutton(root)
            else:
                w = tk.Entry(root, textvariable=app.account if "account" in name else app.server_host_var)
                w.config(state="disabled")  # server fields start locked (server box unticked)
            setattr(app, name, w)
        before = {n: str(getattr(app, n).cget("state")) for n in LOCKED}
        during = {}

        def probe():
            during["states"] = {n: str(getattr(app, n).cget("state")) for n in LOCKED}
            during["windows"] = [(w.title(), w.label.cget("text")) for w in root.winfo_children()
                                 if isinstance(w, tk.Toplevel)]
            grab = root.grab_current()
            during["grab"] = grab.title() if grab is not None else None
            app.info_btn_auto.invoke()  # a second Create click: a disabled button does nothing
            app.info_btn_manual.invoke()
            probed.release()

        def slow_check_all(settings, server, use_aws, use_server, runner=None):
            probed.acquire(timeout=10)
            return [cc.CheckResult("AWS bucket b", False, "nope")]

        with stubbed_front_end() as (_st, ws, logged), tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "config_file"))
            with open(os.path.join(tmp, "config_file", "storage.json"), "w") as fh:
                json.dump(GOOD, fh)
            dialogs = []
            ws.messagebox = types.SimpleNamespace(
                showerror=lambda **kw: dialogs.append(
                    [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]))
            old = os.getcwd()
            os.chdir(tmp)
            try:
                root.after(200, probe)
                with mock.patch.object(cc, "check_all", slow_check_all):
                    ok = ws.WorkspacePanel(app)._storage_ok()
            finally:
                os.chdir(old)
        self.assertFalse(ok)
        self.assertEqual(clicks, [])
        self.assertTrue(all(st == "disabled" for st in during["states"].values()), during["states"])
        self.assertEqual(during["windows"], [("Please wait", "Checking connections...")])
        self.assertEqual(during["grab"], "Please wait")  # modal: the rest of the program cannot be clicked
        self.assertEqual(dialogs, [[]])  # the window was closed before the error dialog
        root.update()
        self.assertEqual({n: str(getattr(app, n).cget("state")) for n in LOCKED}, before)
        self.assertEqual([w for w in root.winfo_children() if isinstance(w, tk.Toplevel)], [])
        self.assertIsNone(root.grab_current())


class _Stop(Exception):
    pass


if __name__ == "__main__":
    unittest.main()
