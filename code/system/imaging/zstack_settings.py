"""Z-stack thickness settings (scope.json) and every value derived from them.

Focus, max projection, the disk check and the start confirmation window all
read these values from here. A key missing from scope.json falls back to a
default that reproduces the behaviour before the settings existed.
"""
from dataclasses import dataclass, fields

import numpy as np

FOCUS_METHODS = ("peak", "band_center", "auto")
# The focus sweep is always at least this much wider than the stack.
FOCUS_MARGIN_UM = 30


@dataclass(frozen=True)
class SubstackGroup:
    """One max-projection group: imaging planes first..last (inclusive)."""
    index: int
    first: int
    last: int

    @property
    def n_planes(self):
        return self.last - self.first + 1

    @property
    def dic_plane(self):
        # Middle plane, rounded down: plane 9 of 20, as before the settings existed.
        return self.first + (self.n_planes - 1) // 2


@dataclass(frozen=True)
class ZStackSettings:
    z_stack_thickness_um: float = 30
    z_step_um: float = 1.5
    focus_step_um: float = 1.5
    focus_step_thick_um: float = 3
    thick_section_um: float = 50
    focus_range_cap_um: float = 300
    focus_method: str = "peak"
    focus_extreme_change_frac: float = 1 / 3
    band_center_frac: float = 0.5
    maxproj_split_above_um: float = 30
    maxproj_substack_um: float = 30
    storage_margin: float = 1.10

    @classmethod
    def from_config(cls, cfg):
        """Build from the scope.json dictionary (scope_cfg[0])."""
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in cfg.items() if k in names})

    def as_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}

    # ------------------------------------------------------------ imaging stack

    @property
    def n_planes(self):
        """N, the number of imaging planes."""
        return int(round(self.z_stack_thickness_um / self.z_step_um))

    def imaging_planes(self, middle):
        """Absolute piezo positions of the imaging stack, centred on middle."""
        return _planes(middle - self.z_stack_thickness_um / 2, self.z_step_um, self.n_planes)

    # ------------------------------------------------------------ focus sweep

    @property
    def focus_range_um(self):
        """R, the width of the focus sweep."""
        t = self.z_stack_thickness_um
        return min(max(1.2 * t, t + FOCUS_MARGIN_UM), self.focus_range_cap_um)

    @property
    def is_thick(self):
        return self.z_stack_thickness_um >= self.thick_section_um

    @property
    def focus_step(self):
        return self.focus_step_thick_um if self.is_thick else self.focus_step_um

    @property
    def n_focus_planes(self):
        """N_f, the number of planes in each focus pass."""
        return int(round(self.focus_range_um / self.focus_step))

    def focus_planes(self, middle):
        """Absolute piezo positions of one focus pass, centred on middle."""
        return _planes(middle - self.focus_range_um / 2, self.focus_step, self.n_focus_planes)

    def focus_method_for(self):
        """The autofocus method in effect: 'peak' or 'band_center'."""
        if self.focus_method == "auto":
            return "band_center" if self.is_thick else "peak"
        return self.focus_method

    def extreme_threshold(self):
        """Focus change (um) that counts as extreme: a fraction of R (20 um at the defaults)."""
        return round(self.focus_extreme_change_frac * self.focus_range_um, 1)

    # ------------------------------------------------------------ sub-stacks

    @property
    def n_substack_planes(self):
        return int(round(self.maxproj_substack_um / self.z_step_um))

    @property
    def split_enabled(self):
        return self.z_stack_thickness_um > self.maxproj_split_above_um

    def substack_groups(self):
        """Max-projection groups.

        Fixed groups of n_sub planes. A leftover of half a group or less joins
        the last full group; a larger leftover becomes its own, shorter group.
        """
        n, n_sub = self.n_planes, self.n_substack_planes
        if not self.split_enabled or n <= n_sub:
            return [SubstackGroup(0, 0, n - 1)]
        q, r = divmod(n, n_sub)
        bounds = [[i * n_sub, (i + 1) * n_sub - 1] for i in range(q)]
        if r > n_sub / 2:
            bounds.append([q * n_sub, n - 1])
        elif r > 0:
            bounds[-1][1] = n - 1
        return [SubstackGroup(i, a, b) for i, (a, b) in enumerate(bounds)]

    # ------------------------------------------------------------ checks

    def validate(self, piezo_limits=None, middles=()):
        """Return (errors, warnings), each a list of messages.

        piezo_limits: (low, high) travel of the piezo in um, or None if unknown.
        middles: piezo positions the stacks will be centred on.
        """
        errors, warnings = [], []
        if self.z_stack_thickness_um <= 0 or self.z_step_um <= 0 or self.focus_step <= 0:
            errors.append("z_stack_thickness_um, z_step_um and the focus steps must be positive.")
            return errors, warnings
        if self.focus_method not in FOCUS_METHODS:
            errors.append(f"focus_method must be one of {', '.join(FOCUS_METHODS)}, not {self.focus_method!r}.")
        cap = self.focus_range_cap_um
        if self.z_stack_thickness_um > cap:
            errors.append(f"Z-stack {self.z_stack_thickness_um:g} um is thicker than the focus sweep cap {cap:g} um.")
        elif self.z_stack_thickness_um > cap - FOCUS_MARGIN_UM:
            warnings.append(f"Focus sweep {self.focus_range_um:g} um leaves less than {FOCUS_MARGIN_UM} um "
                            f"of margin around the {self.z_stack_thickness_um:g} um stack.")
        if piezo_limits is not None and len(middles):
            low, high = piezo_limits
            for what, planes in (("Focus sweep", self.focus_planes), ("Imaging stack", self.imaging_planes)):
                lo = min(float(planes(m)[0]) for m in middles)
                hi = max(float(planes(m)[-1]) for m in middles)
                if lo < low or hi > high:
                    warnings.append(f"{what} {lo:.1f} to {hi:.1f} um is outside the piezo travel "
                                    f"{low:g} to {high:g} um.")
        return errors, warnings

    def describe(self):
        """Lines for the log and the confirmation window."""
        groups = self.substack_groups()
        sizes = "/".join(str(g.n_planes) for g in groups)
        return [
            f"Z-stack: {self.z_stack_thickness_um:g} um, {self.n_planes} planes at {self.z_step_um:g} um",
            f"Focus sweep: {self.focus_range_um:g} um, {self.n_focus_planes} planes at {self.focus_step:g} um "
            f"per pass, method {self.focus_method_for()}",
            f"Extreme focus change: {self.extreme_threshold():g} um",
            f"Max projections per tile: {len(groups)} ({sizes} planes)",
        ]


def _planes(start, step, n):
    # Same arithmetic as np.arange(start, stop, step), so the default positions
    # are bit-identical to the hard-coded sweeps they replace.
    return np.arange(start, start + (n - 0.5) * step, step)


def estimate_storage(settings, round_channels, n_tiles, n_focus_positions, n_focus_rounds, imwidth):
    """Bytes needed by an automated run, before the safety margin.

    round_channels: channel count of each image round, in protocol order.
    Returns a dict with:
      projections: permanent, on the max-projection drive;
      raw_tiles: peak of the raw tile stacks, on the work-folder drive (each
                 cycle's raw folder is deleted once its projections are verified);
      raw_focus: permanent raw focus stacks (2 passes each), on the work-folder drive.
    """
    frame = imwidth * imwidth * 2
    k = len(settings.substack_groups())
    projections = sum(n_tiles * c * k * frame for c in round_channels)
    raw_tiles = max((n_tiles * c * settings.n_planes * frame for c in round_channels), default=0)
    raw_focus = n_focus_rounds * n_focus_positions * 2 * settings.n_focus_planes * frame
    return {"projections": projections, "raw_tiles": raw_tiles, "raw_focus": raw_focus}


def format_bytes(n):
    if n >= 1e12:
        return f"{n / 1e12:.2f} TB"
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB"
    return f"{n / 1e6:.0f} MB"


__all__ = ["ZStackSettings", "SubstackGroup", "estimate_storage", "format_bytes", "FOCUS_METHODS"]
