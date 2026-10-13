"""Lab-specific storage settings (AWS bucket and storage server), read from config_file/storage.json.

There are deliberately no built-in defaults: a missing file, a missing or unknown key or an invalid value
raises StorageSettingsError listing every problem, so data can never silently go to another lab's bucket.
"""

import json
import os
from dataclasses import dataclass

STORAGE_FILE = "storage.json"

_STR_KEYS = ("aws_bucket", "aws_storage_class", "server_user", "server_host", "server_root")
_ALL_KEYS = _STR_KEYS + ("aws_prefix", "aws_upload_retries")


class StorageSettingsError(Exception):
    """storage.json is missing or invalid; the message lists every problem found."""


@dataclass(frozen=True)
class StorageSettings:
    aws_bucket: str
    aws_prefix: str
    aws_storage_class: str
    aws_upload_retries: int
    server_user: str
    server_host: str
    server_root: str

    @classmethod
    def load(cls, path):
        """Read and validate the file at ``path``; raise StorageSettingsError on any problem."""
        try:
            with open(path, "r") as f:
                cfg = json.load(f)
        except FileNotFoundError:
            raise StorageSettingsError(f"{path} not found")
        except (OSError, ValueError) as e:
            raise StorageSettingsError(f"{path} cannot be read as JSON: {e}")
        return cls.from_dict(cfg, source=path)

    @classmethod
    def from_dict(cls, cfg, source=STORAGE_FILE):
        if not isinstance(cfg, dict):
            raise StorageSettingsError(f"{source} must contain a JSON object")
        problems = []
        for k in _ALL_KEYS:
            if k not in cfg:
                problems.append(f"missing key '{k}'")
        for k in cfg:
            if k not in _ALL_KEYS:
                problems.append(f"unknown key '{k}'")
        for k in _STR_KEYS:
            if k in cfg and not (isinstance(cfg[k], str) and cfg[k].strip()):
                problems.append(f"'{k}' must be a non-empty string")
        if "aws_prefix" in cfg:
            v = cfg["aws_prefix"]
            if not isinstance(v, str) or v.startswith("/"):
                problems.append("'aws_prefix' must be a string without a leading '/'")
        if "aws_upload_retries" in cfg:
            v = cfg["aws_upload_retries"]
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                problems.append("'aws_upload_retries' must be an integer >= 1")
        if isinstance(cfg.get("server_root"), str) and cfg["server_root"].strip() \
                and not cfg["server_root"].endswith("/"):
            problems.append("'server_root' must end with '/'")
        if problems:
            raise StorageSettingsError(f"{source}: " + "; ".join(problems))
        return cls(**{k: cfg[k] for k in _ALL_KEYS})

    @property
    def server(self):
        """ssh/scp address user@host."""
        return f"{self.server_user}@{self.server_host}"

    def remote_path(self, pos_path, suffix=""):
        """Remote folder for an experiment: <server_root><pos_path without drive>[suffix]."""
        return self.server_root + pos_path[3:] + suffix

    def s3_folder(self, folder):
        """Key prefix inside the bucket for an experiment folder."""
        prefix = self.aws_prefix.strip("/")
        return f"{prefix}/{folder}" if prefix else folder

    def s3_uri(self, folder, filename):
        return f"s3://{self.aws_bucket}/{self.s3_folder(folder)}/{filename}"


def default_path():
    """config_file/storage.json relative to the working directory, as scope.json is read."""
    return os.path.join("config_file", STORAGE_FILE)
