"""Snapshot the ISO-NE 48-hour grid forecast to a static CSV.

The load-shift advisor's "Today / Tomorrow" needs a forward forecast. Rather
than fetch it live on every app load (slow, network-dependent, and it would
drift as the clock advances mid-demo), we snapshot it ONCE to
``data/forecast_snapshot.csv``. The app then reads that file statically — the
snapshot's "today" stays fixed until you re-run this script.

Usage:
    python fetch_forecast.py          # take / refresh the snapshot

Requires the historical fuel-mix cache (run fetch_fuelmix.py first) for the
baseload profile used in the dispatch-based estimate.
"""

from __future__ import annotations

import sys

from src import carbon, data_loader, forecast, timeline


def main() -> int:
    try:
        history = timeline.load_carbon_history()
    except (data_loader.DataFileNotFoundError, carbon.FuelMixNotFoundError) as e:
        print(e)
        print("Run `python fetch_fuelmix.py` first to build the historical cache.")
        return 1

    try:
        path = forecast.save_forecast_snapshot(history)
    except ImportError:
        print("ERROR: gridstatus is not installed. Run: pip install gridstatus")
        return 1
    except Exception as e:
        print(f"ERROR building forecast snapshot: {e}")
        return 1

    fc = forecast.load_forecast_snapshot(path)
    if fc.empty:
        print("Snapshot written but empty — check the forecast source.")
        return 1
    print(f"Wrote {path} with {len(fc)} hourly rows "
          f"({fc['timestamp'].min()} -> {fc['timestamp'].max()}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
