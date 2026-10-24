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


def test_charging_sources_identifies_fuels():
    from src import carbon_battery as cb
    ts = pd.date_range("2025-08-18 00:00", periods=24, freq="h")
    # A clear duck curve: carbon lowest midday (solar), highest in the evening,
    # so the battery charges midday and solar is present during charging.
    carbon = [500 + abs(h - 12) * 20 for h in range(24)]  # min at noon
    solar = [max(0.0, 900 - abs(h - 12) * 130) for h in range(24)]
    day = pd.DataFrame({
        "timestamp": ts,
        "carbon_lbs_per_mwh": carbon,
        "solar_mw": solar,
        "Solar": solar,
        "Wind": [300.0] * 24,
        "Nuclear": [3000.0] * 24,
        "Hydro": [100.0] * 24,
    })
    res = cb.simulate_carbon(day["carbon_lbs_per_mwh"].tolist(), 200, 800, 0.9)
    charge_hours = [i for i, c in enumerate(res.charge) if c > 1e-9]
    assert charge_hours, "battery should charge somewhere"
    sources = app._charging_sources(day, res)
    # Nuclear always dominates MWh; solar appears because midday is cleanest.
    assert any("Nuclear" in s for s in sources)
    assert any("Solar" in s for s in sources)


def test_contiguous_windows_formats_ranges():
    ts = list(pd.date_range("2025-08-18 00:00", periods=24, freq="h"))
    flags = [False] * 24
    for h in (9, 10, 11):      # one block 09:00-12:00
        flags[h] = True
    for h in (18, 19):         # another block 18:00-20:00
        flags[h] = True
    windows = app._contiguous_windows(ts, flags)
    assert windows == ["09:00–12:00", "18:00–20:00"]


def test_contiguous_windows_handles_trailing_block():
    ts = list(pd.date_range("2025-08-18 00:00", periods=24, freq="h"))
    flags = [False] * 24
    flags[22] = True
    flags[23] = True  # block runs to end of day -> 22:00-00:00
    windows = app._contiguous_windows(ts, flags)
    assert windows == ["22:00–00:00"]


def test_aggregate_chart_serializes_all_freqs():
    dates = pd.date_range("2025-01-01", periods=120, freq="D")
    daily = pd.DataFrame({
        "date": dates,
        "kg": [1000.0 + i for i in range(120)],
        "cycled": [True] * 120,
    })
    scale = app._co2_scale(daily["kg"].sum())
    for freq in app.AGG_FREQS:
        assert app.aggregate_chart(daily, freq, scale).to_dict() is not None


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
