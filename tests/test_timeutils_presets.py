import pandas as pd
import pytest

from src import presets, timeutils


def _make_df():
    ts = pd.date_range("2025-01-01 00:00", periods=48, freq="h")
    demand = [100.0] * 48
    demand[30] = 999.0  # peak on the second day
    return pd.DataFrame({"timestamp": ts, "demand_mw": demand})


def test_worst_day():
    df = _make_df()
    day = timeutils.worst_day(df)
    assert day == pd.Timestamp("2025-01-02")


def test_available_days():
    df = _make_df()
    days = timeutils.available_days(df)
    assert days[0] == pd.Timestamp("2025-01-01")
    assert days[1] == pd.Timestamp("2025-01-02")
    assert len(days) == 2


def test_filter_day():
    df = _make_df()
    day2 = timeutils.filter_day(df, pd.Timestamp("2025-01-02"))
    assert len(day2) == 24
    assert (day2["timestamp"].dt.day == 2).all()


def test_worst_day_empty_raises():
    with pytest.raises(ValueError):
        timeutils.worst_day(pd.DataFrame({"timestamp": [], "demand_mw": []}))


def test_presets_lookup_and_duration():
    # Look up each preset by its exact name and check duration = capacity/power.
    for preset in presets.PRESETS:
        looked_up = presets.get_preset(preset.name)
        assert looked_up is preset
        assert looked_up.duration_hours == pytest.approx(
            preset.capacity_mwh / preset.power_mw
        )


def test_presets_span_a_range_of_durations():
    # The whole point of the new presets: they should NOT all be the same
    # duration (that made every graph look identical).
    durations = {round(p.duration_hours, 1) for p in presets.PRESETS}
    assert len(durations) > 1, "presets should vary in duration, not just scale"


def test_presets_within_slider_ranges():
    # Power slider is 1-1000 MW, capacity 1-5000 MWh.
    for p in presets.PRESETS:
        assert 1 <= p.power_mw <= 1000
        assert 1 <= p.capacity_mwh <= 5000


def test_presets_unknown_raises():
    with pytest.raises(KeyError):
        presets.get_preset("nope")
