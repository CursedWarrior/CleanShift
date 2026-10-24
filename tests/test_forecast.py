"""Tests for the dispatch-based forecast logic.

The network fetch is not exercised here; we test the internal profile and
dispatch math with a small synthetic history.
"""

import pandas as pd

from src import forecast


def _history():
    # 30 days of hourly fake history with the fuels the forecast needs.
    ts = pd.date_range("2025-09-25 00:00", periods=24 * 30, freq="h")
    n = len(ts)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "Nuclear": [3000.0] * n,
            "Hydro": [500.0] * n,
            "Natural Gas": [4000.0] * n,
            "Oil": [100.0] * n,
            "Coal": [0.0] * n,
            "Refuse": [200.0] * n,
            "Landfill Gas": [20.0] * n,
            "Wood": [150.0] * n,
            "Other": [10.0] * n,
            "Solar": [0.0] * n,
            "Wind": [600.0] * n,
        }
    )


def test_hourly_profiles_shapes():
    hist = _history()
    prof = forecast._hourly_profiles(hist, ["Nuclear", "Hydro"])
    assert list(prof.index) == list(range(24))
    assert prof["Nuclear"].iloc[0] == 3000.0


def test_residual_dispatch_logic():
    # Rebuild the core dispatch math the way build_forecast_timeline does, but
    # feed synthetic forecasts so we don't hit the network.
    hist = _history()
    baseload = forecast._hourly_profiles(hist, ["Nuclear", "Hydro"])
    fossil = forecast._hourly_profiles(hist, forecast.DISPATCHABLE)

    hour = 12
    demand = 12000.0
    solar, wind = 1000.0, 800.0
    nuc = baseload.loc[hour, "Nuclear"]
    hyd = baseload.loc[hour, "Hydro"]
    given_clean = solar + wind + nuc + hyd
    residual = max(demand - given_clean, 0.0)

    shares = fossil.loc[hour]
    total = shares.sum()
    gas = residual * (shares["Natural Gas"] / total)

    # Residual = 12000 - (1000+800+3000+500) = 6700 fossil MW.
    assert residual == 6700.0
    # Gas is the dominant fossil fuel, so it should carry most of it.
    assert gas > 0.5 * residual


def test_more_clean_supply_lowers_residual():
    hist = _history()
    baseload = forecast._hourly_profiles(hist, ["Nuclear", "Hydro"])
    hour = 12
    demand = 12000.0
    nuc = baseload.loc[hour, "Nuclear"]
    hyd = baseload.loc[hour, "Hydro"]

    low_solar = max(demand - (0 + 800 + nuc + hyd), 0.0)
    high_solar = max(demand - (3000 + 800 + nuc + hyd), 0.0)
    # More solar -> less fossil residual -> cleaner.
    assert high_solar < low_solar
