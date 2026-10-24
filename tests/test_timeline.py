import pandas as pd

from src import timeline


def test_build_timeline_real_data():
    df = timeline.build_timeline()
    # Every row has both demand and carbon; no nulls in the key columns.
    assert len(df) > 8000
    assert df["demand_mw"].notna().all()
    assert df["carbon_lbs_per_mwh"].notna().all()
    assert "solar_mw" in df.columns
    assert "clean_share" in df.columns
    # Sorted ascending by timestamp.
    assert df["timestamp"].is_monotonic_increasing


def test_filter_month():
    df = timeline.build_timeline()
    jan = timeline.filter_month(df, 2025, 1)
    assert (jan["timestamp"].dt.month == 1).all()
    assert len(jan) > 700  # ~744 hours in January, minus a few gaps
