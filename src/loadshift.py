"""Load-shift advisor: when should a flexible load run to minimize CO2?

Given a flexible load (energy in kWh, run duration in whole hours) and an
allowed window of hours, find the contiguous start hour whose hours have the
lowest average carbon intensity, and compare the emissions to running the load
at a "convenient" baseline time (e.g. plugging in after work).

Emissions for running ``energy_kwh`` over ``duration_h`` hours at a set of
carbon intensities (lbs CO2/MWh) is:

    per_hour_kwh = energy_kwh / duration_h
    lbs = sum( per_hour_kwh/1000 (MWh) * intensity_h )

We report results in kg CO2 (1 lb = 0.453592 kg) for a friendlier unit.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

LB_TO_KG = 0.453592


@dataclass
class ShiftResult:
    best_start: pd.Timestamp     # start of the first hour of the window
    best_end: pd.Timestamp       # start of the LAST hour of the window (inclusive)
    best_kg: float
    baseline_start: pd.Timestamp
    baseline_kg: float
    duration_h: int
    energy_kwh: float

    @property
    def best_end_exclusive(self) -> pd.Timestamp:
        """End of the window as a clock time (one hour past the last hour's start).

        A 1-hour run starting 10:00 spans 10:00–11:00, so this returns 11:00.
        Use this for display and for drawing the window band — it avoids the
        off-by-one of treating ``best_end`` (the last hour's *start*) as the end.
        """
        return self.best_end + pd.Timedelta(hours=1)

    @property
    def kg_avoided(self) -> float:
        return self.baseline_kg - self.best_kg

    @property
    def pct_avoided(self) -> float:
        if self.baseline_kg <= 0:
            return 0.0
        return 100.0 * self.kg_avoided / self.baseline_kg


def _emissions_kg(intensities: list[float], energy_kwh: float, duration_h: int) -> float:
    """CO2 (kg) to deliver energy_kwh spread evenly over duration_h hours."""
    per_hour_mwh = (energy_kwh / duration_h) / 1000.0
    lbs = sum(per_hour_mwh * ci for ci in intensities)
    return lbs * LB_TO_KG


def optimize_window(
    day: pd.DataFrame,
    energy_kwh: float,
    duration_h: int,
    baseline_hour: int,
    intensity_col: str = "carbon_lbs_per_mwh",
) -> ShiftResult:
    """Find the cleanest contiguous window to run the load within ``day``.

    Parameters
    ----------
    day:
        DataFrame for the allowed window (typically one calendar day), with
        ``timestamp`` and an intensity column, sorted ascending by hour.
    energy_kwh:
        Total energy the load needs.
    duration_h:
        How many whole hours the load runs.
    baseline_hour:
        The hour-of-day (0..23) a user would "conveniently" start the load;
        used as the comparison point.
    """
    day = day.sort_values("timestamp").reset_index(drop=True)
    intensities = day[intensity_col].tolist()
    times = list(day["timestamp"])
    n = len(day)
    duration_h = max(1, int(duration_h))

    if n < duration_h:
        raise ValueError(
            f"Window has {n} hours but the load needs {duration_h}."
        )

    # Find the start index minimizing total emissions over duration_h hours.
    best_idx = 0
    best_kg = float("inf")
    for i in range(0, n - duration_h + 1):
        window = intensities[i : i + duration_h]
        kg = _emissions_kg(window, energy_kwh, duration_h)
        if kg < best_kg:
            best_kg = kg
            best_idx = i

    # Baseline: start at the user's chosen hour and run from there. We do NOT
    # move the start to make the run fit — the user's habitual start time is
    # fixed regardless of run length. If the run would extend past the end of
    # the available window, we compare over the hours that remain from that
    # start (at least one hour), so changing the run time never shifts the
    # displayed start hour.
    base_candidates = [j for j, t in enumerate(times) if t.hour == baseline_hour]
    base_idx = base_candidates[0] if base_candidates else 0
    avail = n - base_idx
    base_hours = max(1, min(duration_h, avail))
    baseline_window = intensities[base_idx : base_idx + base_hours]
    # Scale emissions as if the full load's energy were delivered over the hours
    # available from the chosen start (keeps per-kWh comparison fair).
    baseline_kg = _emissions_kg(baseline_window, energy_kwh, len(baseline_window))

    return ShiftResult(
        best_start=times[best_idx],
        best_end=times[best_idx + duration_h - 1],
        best_kg=best_kg,
        baseline_start=times[base_idx],
        baseline_kg=baseline_kg,
        duration_h=duration_h,
        energy_kwh=energy_kwh,
    )
