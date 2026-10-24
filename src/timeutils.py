"""Time-window helpers for the demand series (worst-day selector, etc.)."""

from __future__ import annotations

import pandas as pd


def worst_day(df: pd.DataFrame) -> pd.Timestamp:
    """Return the calendar date (normalized to midnight) of the max-demand hour.

    Parameters
    ----------
    df:
        DataFrame with ``timestamp`` and ``demand_mw`` columns.
    """
    if df.empty:
        raise ValueError("Cannot find worst day of an empty DataFrame.")
    peak_idx = df["demand_mw"].idxmax()
    return pd.Timestamp(df.loc[peak_idx, "timestamp"]).normalize()


def available_days(df: pd.DataFrame) -> list[pd.Timestamp]:
    """Return the sorted unique calendar dates present in the series."""
    return sorted(df["timestamp"].dt.normalize().unique())


def filter_day(df: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """Return rows falling on the given calendar day."""
    day = pd.Timestamp(day).normalize()
    mask = df["timestamp"].dt.normalize() == day
    return df.loc[mask].reset_index(drop=True)
