"""Backward-compatible shim. Import from system.imaging instead."""
import warnings

# As in the reference, which silenced warnings process-wide when this module was imported.
warnings.filterwarnings("ignore")

from system.imaging import *
from system.imaging.position_utils import *
from system.imaging.imaging_system import ImagingSystem as scope
