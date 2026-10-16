"""storage.json loading and validation, and the AWS / server connection checks (fake command runners)."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

CODE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "code")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(CODE, "system", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ss = _load("storage_settings")
cc = _load("connection_check")
GOOD = {"aws_bucket": "b", "aws_prefix": "", "aws_storage_class": "INTELLIGENT_TIERING",
        "aws_upload_retries": 3, "server_user": "u", "server_host": "h", "server_root": "/mnt/x/"}


def S(**kw):
    return ss.StorageSettings.from_dict({**GOOD, **kw})


class TestLoad(unittest.TestCase):
    def test_shipped_file_has_the_values_hardcoded_before(self):
        s = ss.StorageSettings.load(os.path.join(CODE, "config_file", "storage.json"))
        self.assertEqual((s.aws_bucket, s.aws_prefix, s.aws_storage_class, s.aws_upload_retries),
                         ("barseq-acquisition", "", "INTELLIGENT_TIERING", 3))
        self.assertEqual((s.server_user, s.server_host, s.server_root),
                         ("imagestorage", "10.128.30.152", "/mnt/imagestorage/"))
        self.assertEqual(s.server, "imagestorage@10.128.30.152")

    def test_missing_file(self):
        with self.assertRaisesRegex(ss.StorageSettingsError, "not found"):
            ss.StorageSettings.load(os.path.join(tempfile.gettempdir(), "nope_storage.json"))

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "storage.json")
            with open(p, "w") as f:
                f.write("{oops")
            with self.assertRaisesRegex(ss.StorageSettingsError, "JSON"):
                ss.StorageSettings.load(p)

    def test_all_problems_listed(self):
        cfg = dict(GOOD)
        del cfg["aws_bucket"]
        cfg["aws_bucked"] = "typo"
        cfg["aws_upload_retries"] = 0
        cfg["server_root"] = "/mnt/x"
        with self.assertRaises(ss.StorageSettingsError) as cm:
            ss.StorageSettings.from_dict(cfg)
        m = str(cm.exception)
        for part in ("missing key 'aws_bucket'", "unknown key 'aws_bucked'", "aws_upload_retries", "ends with '/'"):
            self.assertIn(part, m)

    def test_invalid_values(self):
        for bad in ({"aws_bucket": ""}, {"server_host": 5}, {"aws_prefix": "/p"}, {"aws_upload_retries": True},
                    {"aws_upload_retries": "3"}):
            with self.assertRaises(ss.StorageSettingsError, msg=str(bad)):
                S(**bad)

    def test_not_an_object(self):
        with self.assertRaises(ss.StorageSettingsError):
            ss.StorageSettings.from_dict([GOOD])

    def test_utf8_with_bom_loads(self):
        """Notepad can save UTF-8 with a byte-order mark; the file must still load."""
        import json
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "storage.json")
            with open(p, "w", encoding="utf-8-sig") as f:
                json.dump(GOOD, f)
            self.assertEqual(ss.StorageSettings.load(p).aws_bucket, "b")

    def test_values_that_would_break_commands_are_rejected(self):
        bad = (
            {"aws_bucket": " b "}, {"aws_bucket": "s3://b"}, {"aws_bucket": "b/c"},
            {"aws_prefix": " "}, {"aws_prefix": "a//b"}, {"aws_prefix": "a b"},
            {"aws_storage_class": "intelligent tiering"},
            {"aws_upload_retries": 11}, {"aws_upload_retries": -1},
            {"server_user": "a b"}, {"server_user": "u@h"},
            {"server_host": "u@h"}, {"server_host": "h h"}, {"server_host": "h:22"},
            {"server_root": "r/"}, {"server_root": "/mnt/my data/"}, {"server_root": "/mnt/o'x/"},
            {"server_root": "/mnt/a;rm/"}, {"server_root": "/mnt//x/"},
        )
        for kw in bad:
            with self.assertRaises(ss.StorageSettingsError, msg=str(kw)):
                S(**kw)

    def test_storage_class_must_be_one_aws_accepts(self):
        """A typo would otherwise only fail at the end-of-run `aws s3 cp`, hours later."""
        for good in ("STANDARD", "INTELLIGENT_TIERING", "GLACIER_IR", "DEEP_ARCHIVE"):
            S(aws_storage_class=good)
        for bad in ("INTELIGENT_TIERING", "STANDARD_IA_", "GLACIER_X"):
            with self.assertRaisesRegex(ss.StorageSettingsError, "INTELLIGENT_TIERING", msg=bad):
                S(aws_storage_class=bad)

    def test_leading_dash_is_rejected(self):
        """scp/ssh would read '-oProxyCommand=...' as an option."""
        for kw in ({"server_user": "-oProxyCommand=x"}, {"server_user": "-F"}, {"server_host": "-x"},
                   {"aws_bucket": "-b"}):
            with self.assertRaises(ss.StorageSettingsError, msg=str(kw)):
                S(**kw)

    def test_ordinary_values_are_accepted(self):
        for kw in ({"aws_bucket": "barseq-acquisition"}, {"aws_bucket": "lab.B_bucket"},
                   {"aws_prefix": "labA/sub/"}, {"aws_prefix": "labA/2026"}, {"aws_upload_retries": 10},
                   {"server_user": "image.storage_1"}, {"server_host": "10.128.30.152"},
                   {"server_host": "store-1.lab.org"}, {"server_root": "/"},
                   {"server_root": "/mnt/imagestorage/"}, {"server_root": "/data/lab_B/raw-2026/"}):
            S(**kw)


class TestPaths(unittest.TestCase):
    def test_remote_path_matches_previous_literals(self):
        s = S(server_root="/mnt/imagestorage/")
        pos = "E:\\exp1"
        self.assertEqual(s.remote_path(pos), '/mnt/imagestorage/' + pos[3:])
        self.assertEqual(s.remote_path(pos, "_maxprojection"), '/mnt/imagestorage/' + pos[3:] + "_maxprojection")

    def test_s3_uri_without_and_with_prefix(self):
        self.assertEqual(S().s3_uri("exp_maxprojection", "c1.tar.zst"), "s3://b/exp_maxprojection/c1.tar.zst")
        self.assertEqual(S(aws_prefix="labA/").s3_uri("e", "f"), "s3://b/labA/e/f")


def fake(script):
    """Runner returning scripted (rc, out, err) for the first key found in the command line; records calls."""
    calls = []

    def run(args, timeout):
        calls.append(args)
        for key, val in script.items():
            if key in " ".join(args):
                if isinstance(val, Exception):
                    raise val
                return val
        return (0, "", "")
    run.calls = calls
    return run


class TestAws(unittest.TestCase):
    def test_ok_runs_three_read_only_commands(self):
        r = fake({})
        self.assertTrue(cc.check_aws(S(), r).ok)
        self.assertEqual(len(r.calls), 3)
        self.assertEqual(r.calls[2], ["aws", "s3api", "head-bucket", "--bucket", "b"])

    def test_cli_missing(self):
        res = cc.check_aws(S(), fake({"--version": FileNotFoundError()}))
        self.assertFalse(res.ok)
        self.assertIn("not found on PATH", res.message)

    def test_no_credentials_stops_before_bucket(self):
        r = fake({"get-caller-identity": (253, "", "Unable to locate credentials")})
        res = cc.check_aws(S(), r)
        self.assertFalse(res.ok)
        self.assertIn("Unable to locate credentials", res.message)
        self.assertEqual(len(r.calls), 2)

    def test_bucket_missing(self):
        res = cc.check_aws(S(), fake({"head-bucket": (254, "", "An error occurred (404) when calling HeadBucket")}))
        self.assertFalse(res.ok)
        self.assertIn("404", res.message)

    def test_timeout(self):
        res = cc.check_aws(S(), fake({"sts": subprocess.TimeoutExpired("aws", 20)}))
        self.assertFalse(res.ok)
        self.assertIn("timed out", res.message)


class TestServer(unittest.TestCase):
    def test_ok_uses_batch_mode_and_gui_server(self):
        r = fake({})
        self.assertTrue(cc.check_server(S(), "me@box", r).ok)
        args = r.calls[0]
        self.assertEqual(args[:5], ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"])
        self.assertEqual(args[5], "me@box")
        self.assertIn("/mnt/x/", args[6])

    def test_defaults_to_settings_server(self):
        r = fake({})
        cc.check_server(S(), None, r)
        self.assertEqual(r.calls[0][5], "u@h")

    def test_failures(self):
        cases = ((3, "does not exist"), (4, "not writable"), (255, "key login failed"), (7, "exited with 7"))
        for rc, text in cases:
            res = cc.check_server(S(), None, fake({"ssh": (rc, "", "Permission denied (publickey)")}))
            self.assertFalse(res.ok)
            self.assertIn(text, res.message)

    def test_ssh_missing_and_timeout(self):
        self.assertIn("not found", cc.check_server(S(), None, fake({"ssh": FileNotFoundError()})).message)
        self.assertIn("timed out",
                      cc.check_server(S(), None, fake({"ssh": subprocess.TimeoutExpired("ssh", 20)})).message)


class TestRunCommand(unittest.TestCase):
    """The real runner, with a Python child process instead of aws / ssh."""

    def test_undecodable_output_does_not_fail_the_check(self):
        # e.g. a server login banner with bytes the Windows code page cannot decode
        rc, out, err = cc.run_command([sys.executable, "-c",
                                       "import sys; sys.stdout.buffer.write(b'\\x81\\x8d\\xff ok');"
                                       "sys.stderr.buffer.write(b'\\x9d')"], timeout=20)
        self.assertEqual(rc, 0)
        self.assertIn("ok", out)
        self.assertIsInstance(err, str)

    def test_child_gets_no_console_input(self):
        rc, out, _err = cc.run_command([sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"],
                                       timeout=20)
        self.assertEqual((rc, out.strip()), (0, "''"))


class TestAll(unittest.TestCase):
    def test_only_requested_checks_run(self):
        r = fake({})
        self.assertEqual(cc.check_all(S(), "u@h", False, False, r), [])
        self.assertEqual(r.calls, [])
        self.assertEqual(len(cc.check_all(S(), "u@h", True, True, r)), 2)
        self.assertEqual(len(cc.check_all(S(), "u@h", False, True, fake({}))), 1)


if __name__ == "__main__":
    unittest.main()
