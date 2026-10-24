import pandas as pd
import pytest

from src import loadshift


def _day(intensities):
    ts = pd.date_range("2025-06-01 00:00", periods=len(intensities), freq="h")
    return pd.DataFrame({"timestamp": ts, "carbon_lbs_per_mwh": intensities})


def test_picks_cleanest_window():
    # Cleanest 2-hour block is hours 3-4 (values 100, 100).
    intensities = [900, 900, 900, 100, 100, 900, 900, 900] + [900] * 16
    day = _day(intensities)
    res = loadshift.optimize_window(day, energy_kwh=10, duration_h=2, baseline_hour=19)
    assert res.best_start.hour == 3
    assert res.best_end.hour == 4


def test_window_span_matches_duration():
    # Regression: the displayed window (best_start -> best_end_exclusive) must be
    # exactly `duration` hours wide. A 1-hour run must span 1 hour, not 0.
    day = _day([500 + abs(h - 13) * 10 for h in range(24)])
    for dur in (1, 2, 3, 6):
        res = loadshift.optimize_window(day, 10, dur, baseline_hour=19)
        span_h = (res.best_end_exclusive - res.best_start).total_seconds() / 3600
        assert span_h == dur, f"duration {dur} produced a {span_h}h window"
    # 1-hour window is the single cleanest hour (13:00) and is non-empty.
    one = loadshift.optimize_window(day, 10, 1, baseline_hour=19)
    assert one.best_start.hour == 13
    assert one.best_end_exclusive.hour == 14


def test_avoided_emissions_positive_and_hand_computed():
    # Clean window = 2h at 100 lbs/MWh; baseline 19:00 at 900 lbs/MWh.
    intensities = [900] * 24
    intensities[3] = 100
    intensities[4] = 100
    day = _day(intensities)
    res = loadshift.optimize_window(day, energy_kwh=10, duration_h=2, baseline_hour=19)
    # best: 10 kWh over 2h -> 5 kWh/h = 0.005 MWh/h; 2h * 0.005 * 100 = 1.0 lb
    assert res.best_kg == pytest.approx(1.0 * loadshift.LB_TO_KG, rel=1e-6)
    # baseline: 2h * 0.005 * 900 = 9.0 lb
    assert res.baseline_kg == pytest.approx(9.0 * loadshift.LB_TO_KG, rel=1e-6)
    assert res.kg_avoided > 0
    assert res.pct_avoided == pytest.approx(100 * (9 - 1) / 9, rel=1e-6)


def test_raises_when_window_too_short():
    day = _day([500, 500])
    with pytest.raises(ValueError):
        loadshift.optimize_window(day, energy_kwh=10, duration_h=3, baseline_hour=0)


def test_baseline_near_end_of_window_does_not_move_start():
    # baseline_hour 23 with a 2h run only has 1 hour available; the start must
    # STAY at 23:00 (we no longer relocate it to make the run fit).
    day = _day([500] * 24)
    res = loadshift.optimize_window(day, energy_kwh=10, duration_h=2, baseline_hour=23)
    assert res.baseline_start.hour == 23
    # All equal intensity -> no savings, but it must not crash.
    assert res.kg_avoided == pytest.approx(0.0)


def test_baseline_start_is_stable_across_run_times():
    # Regression: changing run time must NOT move the displayed baseline start.
    # Previously the baseline start was clamped earlier to make the run fit.
    day = _day([500 + abs(h - 13) * 10 for h in range(24)])
    starts = {
        dur: loadshift.optimize_window(day, 50, dur, baseline_hour=19).baseline_start.hour
        for dur in (1, 2, 4, 7, 10)
    }
    assert set(starts.values()) == {19}, f"baseline start moved with run time: {starts}"
