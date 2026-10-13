"""storage.json loading and validation, and the AWS / server connection checks (fake command runners)."""

import importlib.util
import os
import subprocess
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
        for part in ("missing key 'aws_bucket'", "unknown key 'aws_bucked'", "aws_upload_retries", "must end with '/'"):
            self.assertIn(part, m)

    def test_invalid_values(self):
        for bad in ({"aws_bucket": ""}, {"server_host": 5}, {"aws_prefix": "/p"}, {"aws_upload_retries": True},
                    {"aws_upload_retries": "3"}):
            with self.assertRaises(ss.StorageSettingsError, msg=str(bad)):
                S(**bad)

    def test_not_an_object(self):
        with self.assertRaises(ss.StorageSettingsError):
            ss.StorageSettings.from_dict([GOOD])


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


class TestAll(unittest.TestCase):
    def test_only_requested_checks_run(self):
        r = fake({})
        self.assertEqual(cc.check_all(S(), "u@h", False, False, r), [])
        self.assertEqual(r.calls, [])
        self.assertEqual(len(cc.check_all(S(), "u@h", True, True, r)), 2)
        self.assertEqual(len(cc.check_all(S(), "u@h", False, True, fake({}))), 1)


if __name__ == "__main__":
    unittest.main()
