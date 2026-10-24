"""Hypothetical battery presets for one-click scenario selection."""

from __future__ import annotations

from dataclasses import dataclass


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


# Presets are chosen to differ in BOTH scale and duration (capacity ÷ power), so
# each produces a visibly different dispatch shape on the chart — not just a
# scaled copy of the same 4-hour curve. They're also spread across the slider
# ranges (power 1-1000 MW, capacity 1-5000 MWh).
# Presets scale up by place (home -> neighborhood -> city -> region) while also
# varying duration (capacity ÷ power), so each produces a visibly different
# dispatch shape on the chart — not just a scaled copy of the same curve. They
# also spread across the slider ranges (power 1-1000 MW, capacity 1-5000 MWh).
PRESETS: list[Preset] = [
    # Small, short-duration: brief shallow discharges.
    Preset("Home battery (25 MW / 50 MWh, 2h)", 25.0, 50.0),
    # Mid, 4-hour: the "typical" grid battery.
    Preset("Neighborhood (150 MW / 600 MWh, 4h)", 150.0, 600.0),
    # Big tank, long duration: wide, sustained discharges across the evening.
    Preset("Grid-scale (400 MW / 3,200 MWh, 8h)", 400.0, 3200.0),
]


def get_preset(name: str) -> Preset:
    """Look up a preset by name."""
    for p in PRESETS:
        if p.name == name:
            return p
    raise KeyError(f"Unknown preset: {name}")
