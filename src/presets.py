"""Hypothetical battery presets for one-click scenario selection.

Presets are realistic, published-spec sizes spanning a home battery up to a
grid-scale installation. They're stored canonically in MW / MWh (what the
simulation uses), with helpers to express each as a human (value, unit) pair for
the kW / MW / GW UI controls.
"""

from __future__ import annotations

from dataclasses import dataclass

# Unit <-> MW multipliers.
UNIT_TO_MW = {"kW": 0.001, "MW": 1.0, "GW": 1000.0}
UNITS = ["kW", "MW", "GW"]


def to_mw(value: float, unit: str) -> float:
    return float(value) * UNIT_TO_MW[unit]


def nicest_unit(mw: float) -> tuple[float, str]:
    """Pick the unit that shows ``mw`` as a clean 1-999 number."""
    if mw >= 1000:
        return mw / 1000.0, "GW"
    if mw >= 1:
        return mw, "MW"
    return mw * 1000.0, "kW"


@dataclass(frozen=True)
class Preset:
    name: str
    power_mw: float
    capacity_mwh: float

    @property
    def duration_hours(self) -> float:
        if self.power_mw <= 0:
            return 0.0
        return self.capacity_mwh / self.power_mw

    @property
    def power_display(self) -> tuple[float, str]:
        return nicest_unit(self.power_mw)

    @property
    def capacity_display(self) -> tuple[float, str]:
        return nicest_unit(self.capacity_mwh)

    @property
    def spec(self) -> str:
        """Human-readable size string, e.g. '11.5 kW / 13.5 kWh'."""
        pv, pu = self.power_display
        cv, cu = self.capacity_display
        pv_s = f"{pv:,.1f}".rstrip("0").rstrip(".")
        cv_s = f"{cv:,.1f}".rstrip("0").rstrip(".")
        return f"{pv_s} {pu} / {cv_s} {cu}h"


# Realistic, published-spec sizes. Place-based names now match the actual scale.
# ``name`` is the short button label; ``spec`` (derived) is the full size shown
# as the button's tooltip so the label stays compact.
PRESETS: list[Preset] = [
    # Home battery (~Tesla Powerwall 3): 11.5 kW / 13.5 kWh.
    Preset("🏠 Home", 0.0115, 0.0135),
    # Commercial building: 250 kW / 500 kWh.
    Preset("🏢 Commercial", 0.25, 0.5),
    # Neighborhood / community storage: 5 MW / 20 MWh.
    Preset("🏘️ Neighborhood", 5.0, 20.0),
    # Grid-scale installation: 400 MW / 1,600 MWh (4-hour).
    Preset("🔋 Grid-scale", 400.0, 1600.0),
]


def get_preset(name: str) -> Preset:
    """Look up a preset by name."""
    for p in PRESETS:
        if p.name == name:
            return p
    raise KeyError(f"Unknown preset: {name}")
