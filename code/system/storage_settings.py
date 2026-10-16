"""Lab-specific storage settings (AWS bucket and storage server), read from config_file/storage.json.

There are deliberately no built-in defaults: a missing file, a missing or unknown key or an invalid value
raises StorageSettingsError listing every problem, so data can never silently go to another lab's bucket.
"""

import json
import os
import re
from dataclasses import dataclass

STORAGE_FILE = "storage.json"

_STR_KEYS = ("aws_bucket", "aws_storage_class", "server_user", "server_host", "server_root")
_ALL_KEYS = _STR_KEYS + ("aws_prefix", "aws_upload_retries")
MAX_RETRIES = 10

# The values `aws s3 cp --storage-class` accepts (AWS CLI v2).
STORAGE_CLASSES = ("STANDARD", "REDUCED_REDUNDANCY", "STANDARD_IA", "ONEZONE_IA", "INTELLIGENT_TIERING",
                   "GLACIER", "DEEP_ARCHIVE", "GLACIER_IR")

# The server values go unquoted into os.system scp/ssh command lines and the bucket and prefix into S3 URIs,
# so only characters that need no quoting are accepted (no spaces, quotes, ';', '$', '@', ':'). A leading '-'
# is refused too: scp/ssh would read it as an option.
_NAME = r"[A-Za-z0-9._-]+"
_PATTERNS = {
    "aws_bucket": (r"[A-Za-z0-9][A-Za-z0-9._-]*",
                   "letters, digits, '.', '_' and '-' only, starting with a letter or digit (no 's3://' or '/')"),
    "aws_storage_class": ("|".join(STORAGE_CLASSES), "one of " + ", ".join(STORAGE_CLASSES)),
    "server_user": (r"[A-Za-z0-9._][A-Za-z0-9._-]*", "letters, digits, '.', '_' and '-' only, not starting with '-'"),
    "server_host": (r"[A-Za-z0-9.][A-Za-z0-9.-]*",
                    "a host name or IPv4 address (no user@ or :port, not starting with '-')"),
    "server_root": (rf"/({_NAME}/)*", "an absolute folder that starts and ends with '/' (e.g. /data/images/), "
                                      "with no spaces, quotes or '//'"),
}


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
            with open(path, "r", encoding="utf-8-sig") as f:  # tolerate a BOM (Notepad)
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
            if k not in cfg:
                continue
            v = cfg[k]
            if not (isinstance(v, str) and v.strip()):
                problems.append(f"'{k}' must be a non-empty string")
                continue
            pattern, rule = _PATTERNS[k]
            if not re.fullmatch(pattern, v):
                problems.append(f"'{k}' is {v!r}; it must be {rule}")
        if "aws_prefix" in cfg:
            v = cfg["aws_prefix"]
            if not isinstance(v, str) or (v and not re.fullmatch(rf"{_NAME}(/{_NAME})*/?", v)):
                problems.append(f"'aws_prefix' is {v!r}; it must be empty or folder names separated by '/' "
                                "(no leading '/', no spaces or '//')")
        if "aws_upload_retries" in cfg:
            v = cfg["aws_upload_retries"]
            if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= MAX_RETRIES:
                problems.append(f"'aws_upload_retries' must be an integer from 1 to {MAX_RETRIES}")
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
