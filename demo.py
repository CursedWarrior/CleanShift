"""Command-line demo of the Clean Shift engine.

Usage:
    python demo.py

Loads the aligned demand + carbon timeline and prints:
  * the grid's cleanest/dirtiest hour of day,
  * a load-shift example (EV charging) on a sunny day,
  * a carbon-battery example over the year.

Useful for sanity-checking without launching the Streamlit UI.
"""

from __future__ import annotations

import pandas as pd

from src import carbon_battery as cb
from src import carbon, data_loader, loadshift, timeline

EFFICIENCY = 0.90


def main():
    try:
        df = timeline.build_timeline()
    except (data_loader.DataFileNotFoundError, carbon.FuelMixNotFoundError) as e:
        print(e)
        print("Make sure both data files exist in data/ "
              "(run `python fetch_fuelmix.py` for the fuel mix).")
        return

    print("=== Grid carbon rhythm (2025 average by hour of day) ===")
    by_hour = df.assign(h=df["timestamp"].dt.hour).groupby("h")["carbon_lbs_per_mwh"].mean()
    print(f"  cleanest hour: {int(by_hour.idxmin()):02d}:00  ({by_hour.min():.0f} lbs CO2/MWh)")
    print(f"  dirtiest hour: {int(by_hour.idxmax()):02d}:00  ({by_hour.max():.0f} lbs CO2/MWh)")
    print()

    # Load-shift example on a sunny June day.
    day = df[df["timestamp"].dt.normalize() == pd.Timestamp("2025-06-15")]
    day = day.sort_values("timestamp").reset_index(drop=True)
    res = loadshift.optimize_window(day, energy_kwh=50, duration_h=4, baseline_hour=19)
    print("=== Load-shift: charge a 50 kWh EV (4h) on 2025-06-15 ===")
    print(f"  cleanest window: {res.best_start.strftime('%H:%M')}–"
          f"{(res.best_end + pd.Timedelta(hours=1)).strftime('%H:%M')}  "
          f"=> {res.best_kg:.2f} kg CO2")
    print(f"  usual 7pm start: => {res.baseline_kg:.2f} kg CO2")
    print(f"  avoided: {res.kg_avoided:.2f} kg ({res.pct_avoided:.0f}% less)")
    print()

    # Carbon-battery example over the full year.
    ci = df["carbon_lbs_per_mwh"].tolist()
    print("=== Carbon battery (charge clean, discharge dirty), full year ===")
    for pw, cap in [(50, 200), (100, 400)]:
        r = cb.simulate_carbon(ci, pw, cap, EFFICIENCY)
        print(f"  {pw} MW / {cap} MWh: net CO2 avoided "
              f"{r.net_co2_avoided_kg/1000:.1f} tonnes over {r.cycles:.0f} cycles")


if __name__ == "__main__":
    main()
