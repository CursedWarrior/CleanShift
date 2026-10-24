"""Hourly timelines combining demand, carbon intensity, and the forecast.

Two regimes, two jobs:
  * HISTORICAL (2025-01-01 -> latest cached): demand + carbon, for the
    duck-curve and carbon-battery views. Demand (NEMA) only exists for 2025, so
    for 2026 historical hours ``demand_mw`` may be NaN — that's fine, those views
    that need demand filter to where it exists.
  * FORECAST (next 48h): carbon-only estimate from ``forecast.py``.

The carbon columns use naive, start-of-hour local timestamps throughout.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import carbon, data_loader


def load_carbon_history(fuelmix_path: str | Path | None = None) -> pd.DataFrame:
    """Historical carbon timeline (all cached hours), with demand where available.

    Columns: ``timestamp``, fuel columns, ``carbon_lbs_per_mwh``, ``solar_mw``,
    ``clean_share``, ``demand_mw`` (NaN where no demand data), ``is_forecast=False``.
    """
    carbon_df = carbon.load_carbon(fuelmix_path)
    try:
        demand = data_loader.load_demand(month=None)[["timestamp", "demand_mw"]]
        merged = carbon_df.merge(demand, on="timestamp", how="left")
    except data_loader.DataFileNotFoundError:
        merged = carbon_df.copy()
        merged["demand_mw"] = pd.NA
    merged["is_forecast"] = False
    return merged.sort_values("timestamp").reset_index(drop=True)


def build_timeline(
    demand_path: str | Path | None = None,
    fuelmix_path: str | Path | None = None,
) -> pd.DataFrame:
    """Historical rows where BOTH demand and carbon exist (for battery/duck views).

    Columns: ``timestamp``, ``demand_mw``, ``carbon_lbs_per_mwh``, ``solar_mw``,
    ``clean_share`` (+ raw fuels). Inner-join, sorted.
    """
    demand = data_loader.load_demand(demand_path, month=None)[
        ["timestamp", "demand_mw"]
    ]
    carbon_df = carbon.load_carbon(fuelmix_path)
    merged = demand.merge(carbon_df, on="timestamp", how="inner")
    merged = merged.dropna(subset=["demand_mw", "carbon_lbs_per_mwh"])
    return merged.sort_values("timestamp").reset_index(drop=True)


def filter_month(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Return rows within the given calendar month."""
    mask = (df["timestamp"].dt.year == year) & (df["timestamp"].dt.month == month)
    return df.loc[mask].reset_index(drop=True)
