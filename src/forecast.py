"""Forward carbon-intensity forecast (next 48h) via grid-dispatch logic.

A free official *full fuel-mix* forecast doesn't exist for ISO-NE, so we build
one the way the grid actually dispatches:

  1. Start from the forecasted DEMAND for each hour (ISO-NE load forecast, 48h).
  2. Subtract forecasted CLEAN SUPPLY that the grid takes as given:
       * solar + wind  — from ISO-NE's 7-day forecasts,
       * nuclear + hydro — near-constant; held at their recent hour-of-day means.
  3. Whatever DEMAND remains must be met by dispatchable FOSSIL plants
     (natural gas, oil, coal, plus the smaller refuse/landfill/wood/other). We
     fill that residual, split across those fuels in their recent typical
     proportions.
  4. Recompute carbon intensity from the assembled mix with the standard
     emission factors.

This mirrors real merit-order dispatch: clean/cheap generation runs first, and
fossil plants ramp to cover the gap. When demand is high and solar/wind are low,
more gas runs and intensity rises — exactly the signal the load-shift advisor
needs.

Horizon: 48 hours (today + tomorrow), limited by ISO-NE's load forecast. It is a
FORECAST / ESTIMATE, not an official projection. Clearly labeled in the UI.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import carbon

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_FILE = "forecast_snapshot.csv"

# Clean sources the grid takes as given (not dispatched to meet residual demand).
GIVEN_CLEAN = ["Solar", "Wind", "Nuclear", "Hydro"]
# Dispatchable fuels that ramp to fill the residual demand, carbon-emitting.
DISPATCHABLE = ["Natural Gas", "Oil", "Coal", "Refuse", "Landfill Gas", "Wood", "Other"]


def _tz_naive(series: pd.Series) -> pd.Series:
    s = pd.to_datetime(series)
    try:
        return s.dt.tz_localize(None)
    except (TypeError, AttributeError):
        return s


def _fetch_forecasts(iso):
    """Fetch ISO-NE load (48h), solar (7d) and wind (7d) forecasts."""
    load = iso.get_load_forecast("today")
    solar = iso.get_solar_forecast("today")
    wind = iso.get_wind_forecast("today")

    load_df = pd.DataFrame({
        "timestamp": _tz_naive(load["Interval Start"]).dt.floor("h"),
        "demand_mw": load["Load Forecast"].astype(float),
    })
    solar_df = pd.DataFrame({
        "timestamp": _tz_naive(solar["Interval Start"]).dt.floor("h"),
        "Solar": solar["Solar Forecast"].astype(float),
    })
    wind_df = pd.DataFrame({
        "timestamp": _tz_naive(wind["Interval Start"]).dt.floor("h"),
        "Wind": wind["Wind Forecast"].astype(float),
    })
    return load_df, solar_df, wind_df


def _hourly_profiles(history: pd.DataFrame, cols: list[str], days: int = 30) -> pd.DataFrame:
    """Mean MW by hour-of-day for the given fuels over the most recent N days."""
    cutoff = history["timestamp"].max() - pd.Timedelta(days=days)
    recent = history[history["timestamp"] >= cutoff].copy()
    recent["hour"] = recent["timestamp"].dt.hour
    present = [c for c in cols if c in recent.columns]
    return recent.groupby("hour")[present].mean()


def build_forecast_timeline(history: pd.DataFrame) -> pd.DataFrame:
    """Build a 48h forward carbon-intensity estimate via dispatch logic.

    Parameters
    ----------
    history:
        The cached historical fuel mix (with fuel columns), used for the
        near-constant clean baseload profile and the fossil fuel split.

    Returns
    -------
    DataFrame with ``timestamp``, all fuel columns, ``carbon_lbs_per_mwh``,
    ``solar_mw``, ``clean_share``, ``demand_mw`` and ``is_forecast=True``.
    Raises on fetch failure (callers handle gracefully).
    """
    import gridstatus

    iso = gridstatus.ISONE()
    load_df, solar_df, wind_df = _fetch_forecasts(iso)

    # Clamp to the load-forecast horizon (48h) — the binding constraint.
    df = load_df.merge(solar_df, on="timestamp", how="left")
    df = df.merge(wind_df, on="timestamp", how="left")
    df[["Solar", "Wind"]] = df[["Solar", "Wind"]].fillna(0.0)

    # Recent typical hour-of-day profiles.
    baseload = _hourly_profiles(history, ["Nuclear", "Hydro"])        # given clean
    fossil_profile = _hourly_profiles(history, DISPATCHABLE)          # for the split

    rows = []
    for _, r in df.iterrows():
        hour = r["timestamp"].hour
        row = {"timestamp": r["timestamp"], "demand_mw": float(r["demand_mw"])}
        row["Solar"] = float(r["Solar"])
        row["Wind"] = float(r["Wind"])

        # Near-constant clean baseload from recent history.
        nuc = float(baseload.loc[hour, "Nuclear"]) if hour in baseload.index else 0.0
        hyd = float(baseload.loc[hour, "Hydro"]) if hour in baseload.index else 0.0
        row["Nuclear"] = nuc
        row["Hydro"] = hyd

        # Residual demand to be met by dispatchable fossil plants.
        given_clean = row["Solar"] + row["Wind"] + nuc + hyd
        residual = max(r["demand_mw"] - given_clean, 0.0)

        # Split the residual across fossil fuels by their recent proportions.
        if hour in fossil_profile.index:
            shares = fossil_profile.loc[hour]
            total = shares.sum()
            if total > 0:
                for fuel in DISPATCHABLE:
                    frac = float(shares.get(fuel, 0.0)) / total
                    row[fuel] = residual * frac
            else:
                for fuel in DISPATCHABLE:
                    row[fuel] = 0.0
        else:
            for fuel in DISPATCHABLE:
                row[fuel] = 0.0
        rows.append(row)

    fc = pd.DataFrame(rows).fillna(0.0)
    fc = carbon.with_intensity(fc)
    fc["is_forecast"] = True
    return fc.sort_values("timestamp").reset_index(drop=True)


def default_snapshot_path() -> Path:
    return DEFAULT_DATA_DIR / SNAPSHOT_FILE


def save_forecast_snapshot(history: pd.DataFrame, path: str | Path | None = None) -> Path:
    """Build the live 48h forecast once and write it to a CSV snapshot.

    After this, the app reads the snapshot statically (no live fetch). Re-run to
    refresh "today". Returns the path written.
    """
    path = Path(path) if path is not None else default_snapshot_path()
    fc = build_forecast_timeline(history)
    path.parent.mkdir(parents=True, exist_ok=True)
    fc.to_csv(path, index=False)
    return path


def load_forecast_snapshot(path: str | Path | None = None) -> pd.DataFrame:
    """Read the forecast snapshot CSV. Returns an empty DataFrame if missing."""
    path = Path(path) if path is not None else default_snapshot_path()
    if not path.exists():
        return pd.DataFrame()
    fc = pd.read_csv(path, parse_dates=["timestamp"])
    return fc.sort_values("timestamp").reset_index(drop=True)
