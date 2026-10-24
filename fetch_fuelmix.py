"""Incremental fetch of ISO-NE generation fuel mix: 2025-01-01 through latest.

Uses the open-source ``gridstatus`` library (no API key) to pull the ISO New
England generation fuel mix, resamples the sub-hourly data to clean HOURLY rows,
and maintains a single growing cache at ``data/isone_fuelmix.csv``.

INCREMENTAL: the cache is append-only. Each run reads what's already cached,
finds the last timestamp, and fetches only the days AFTER that up to today, then
appends. The already-cached history (e.g. all of 2025) is never re-downloaded.

First run seeds from the existing ``data/isone_fuelmix_2025.csv`` if present, so
the original full-year 2025 pull is reused rather than re-fetched.

Why cache: the live pull makes one request per day (~1.3-1.6 days/sec). Caching
a tidy CSV makes the app start instantly and work offline during a demo.

Usage:
    python fetch_fuelmix.py            # append any new days since last run
    python fetch_fuelmix.py --rebuild  # wipe and re-fetch everything from 2025-01-01

Output CSV columns:
    timestamp, Coal, Hydro, Landfill Gas, Natural Gas, Nuclear, Oil, Other,
    Refuse, Solar, Wind, Wood
All fuel values are average MW generated during that hour.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
CACHE_CSV = DATA_DIR / "isone_fuelmix.csv"
LEGACY_2025_CSV = DATA_DIR / "isone_fuelmix_2025.csv"

EPOCH_START = "2025-01-01"

FUEL_COLUMNS = [
    "Coal", "Hydro", "Landfill Gas", "Natural Gas", "Nuclear",
    "Oil", "Other", "Refuse", "Solar", "Wind", "Wood",
]


def _read_cache() -> pd.DataFrame | None:
    """Load the existing cache, seeding from the legacy 2025 file if needed."""
    if CACHE_CSV.exists():
        return pd.read_csv(CACHE_CSV, parse_dates=["timestamp"])
    if LEGACY_2025_CSV.exists():
        print(f"Seeding cache from existing {LEGACY_2025_CSV.name} "
              "(2025 will not be re-fetched).")
        return pd.read_csv(LEGACY_2025_CSV, parse_dates=["timestamp"])
    return None


def fetch_hourly_fuelmix(start: str, end: str) -> pd.DataFrame:
    """Fetch sub-hourly fuel mix via gridstatus and resample to hourly means."""
    import gridstatus

    iso = gridstatus.ISONE()
    print(f"Fetching ISO-NE fuel mix {start} -> {end} "
          "(one request per day)...")
    raw = iso.get_fuel_mix(start=start, end=end)

    time_col = "Time" if "Time" in raw.columns else raw.columns[0]
    ts = pd.to_datetime(raw[time_col])
    try:
        ts = ts.dt.tz_localize(None)
    except (TypeError, AttributeError):
        pass

    fuels = [c for c in FUEL_COLUMNS if c in raw.columns]
    tidy = raw[fuels].copy()
    tidy.insert(0, "timestamp", ts)

    hourly = (
        tidy.set_index("timestamp")
        .resample("h")
        .mean()
        .dropna(how="all")
        .reset_index()
    )
    for c in fuels:
        hourly[c] = hourly[c].fillna(0.0).round(2)
    return hourly


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Incrementally fetch & cache ISO-NE fuel mix.")
    parser.add_argument("--rebuild", action="store_true",
                        help="Wipe the cache and re-fetch from 2025-01-01.")
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    existing = None if args.rebuild else _read_cache()

    # Decide the fetch start: the day after the last cached hour, or the epoch.
    if existing is not None and not existing.empty:
        last_ts = pd.to_datetime(existing["timestamp"]).max()
        start_date = (last_ts.normalize() + pd.Timedelta(days=1))
    else:
        start_date = pd.Timestamp(EPOCH_START)

    today = pd.Timestamp.now().normalize()
    if start_date >= today:
        print(f"Cache is already up to date (through {existing['timestamp'].max()}). "
              "Nothing to fetch.")
        return 0

    start = start_date.strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    try:
        new_rows = fetch_hourly_fuelmix(start, end)
    except ImportError:
        print("ERROR: gridstatus is not installed. Run: pip install gridstatus")
        return 1
    except Exception as e:
        print(f"ERROR fetching fuel mix: {e}")
        return 1

    if existing is not None and not existing.empty:
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows

    combined = (
        combined.drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    combined.to_csv(CACHE_CSV, index=False)
    added = len(combined) - (len(existing) if existing is not None else 0)
    print(f"Wrote {CACHE_CSV} with {len(combined)} hourly rows "
          f"(+{added} new) ({combined['timestamp'].min()} -> {combined['timestamp'].max()}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
