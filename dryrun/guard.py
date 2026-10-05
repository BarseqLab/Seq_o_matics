"""Hard guarantee that a dry run can never reach real hardware.

The fakes are placed in sys.modules under the real names, and an import hook
refuses to load ANY real module (or submodule) of the hardware libraries. If
the program ever tried to import, say, `serial.tools` or `pycromanager.core`,
the import fails loudly instead of silently talking to a device.
"""

import importlib.abc
import sys

BLOCKED = ("serial", "nidaqmx", "pycromanager", "pymmcore", "pymmcore_plus", "zmq", "ndtiff")


class _Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split(".")[0]
        if top in BLOCKED:
            raise ImportError(f"dry-run guard: real hardware module '{fullname}' must not be imported")
        return None


def install():
    for name, mod in list(sys.modules.items()):
        if name.split(".")[0] in BLOCKED and not getattr(mod, "__dryrun_fake__", False):
            raise RuntimeError(f"dry-run guard: real module '{name}' was imported before the fakes")
    sys.meta_path.insert(0, _Blocker())


def check():
    """Return a list of problems (empty when every hardware module is a fake)."""
    problems = []
    for name, mod in list(sys.modules.items()):
        if name.split(".")[0] in BLOCKED and mod is not None and not getattr(mod, "__dryrun_fake__", False):
            problems.append(name)
    return problems
