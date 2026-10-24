"""Smoke tests: the Clean Shift app module imports and its chart helpers run."""

import pandas as pd

import app
from src import loadshift


def _sample_day(intensities=None, solar=None):
    n = 24
    intensities = intensities or [500 + (abs(h - 13) * 15) for h in range(n)]
    solar = solar or [max(0.0, 400 - abs(h - 13) * 60) for h in range(n)]
    ts = pd.date_range("2025-06-15 00:00", periods=n, freq="h")
    return pd.DataFrame(
        {"timestamp": ts, "carbon_lbs_per_mwh": intensities, "solar_mw": solar}
    )


def test_app_imports():
    assert hasattr(app, "main")
    assert hasattr(app, "carbon_chart")
    assert hasattr(app, "solar_carbon_chart")
    assert hasattr(app, "shift_window_chart")
    assert hasattr(app, "battery_dispatch_chart")
    assert hasattr(app, "pick_day")
    assert hasattr(app, "render_loadshift_tab")
    # The forecast module is wired in.
    from src import forecast  # noqa: F401


def test_carbon_chart_serializes():
    day = _sample_day()
    assert app.carbon_chart(day).to_dict() is not None


def test_carbon_chart_large_window_serializes():
    # Year-sized window must serialize (downsamples to daily means).
    n = 8760
    ts = pd.date_range("2025-01-01", periods=n, freq="h")
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "carbon_lbs_per_mwh": [500 + (i % 200) for i in range(n)],
            "solar_mw": [0.0] * n,
        }
    )
    assert app.carbon_chart(df).to_dict() is not None


def test_solar_and_shift_charts_serialize():
    day = _sample_day()
    assert app.solar_carbon_chart(day).to_dict() is not None
    res = loadshift.optimize_window(day, energy_kwh=50, duration_h=4, baseline_hour=19)
    assert app.shift_window_chart(day, res).to_dict() is not None


def test_battery_dispatch_chart_responds_to_size():
    from src import carbon_battery as cb
    day = _sample_day()
    ci = day["carbon_lbs_per_mwh"].tolist()
    small = cb.simulate_carbon(ci, 10, 40, 0.9)
    big = cb.simulate_carbon(ci, 200, 800, 0.9)
    # Both serialize...
    assert app.battery_dispatch_chart(day, small).to_dict() is not None
    assert app.battery_dispatch_chart(day, big).to_dict() is not None
    # ...and a bigger battery dispatches more energy (so the chart differs).
    assert sum(big.discharge) > sum(small.discharge)
