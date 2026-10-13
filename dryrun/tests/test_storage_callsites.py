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
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


class TestExperimentCreationBlock(unittest.TestCase):
    def _app(self, aws=0, server=0):
        return types.SimpleNamespace(storage=None, upload_aws_value=FakeVar(aws), change_server_value=FakeVar(server),
                                     parent_window=types.SimpleNamespace(update=lambda: None))

    def _run(self, write_json, aws=0, server=0, runner=None):
        with stubbed_front_end() as (_st, ws, logged), tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "config_file"))
            if write_json is not None:
                with open(os.path.join(tmp, "config_file", "storage.json"), "w") as f:
                    json.dump(write_json, f)
            dialogs = []
            ws.messagebox = types.SimpleNamespace(showerror=lambda **kw: dialogs.append(kw),
                                                  showinfo=lambda **kw: dialogs.append(kw))
            app = self._app(aws, server)
            old = os.getcwd()
            os.chdir(tmp)
            try:
                with mock.patch.object(cc, "run_command", runner or (lambda a, t=20: (0, "", ""))):
                    ok = ws.WorkspacePanel(app)._storage_ok("u@h")
            finally:
                os.chdir(old)
        return ok, app, dialogs, logged

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


if __name__ == "__main__":
    unittest.main()
