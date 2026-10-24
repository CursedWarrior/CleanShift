import pytest

from src import carbon_battery as cb


def test_charges_clean_discharges_dirty():
    # Clean hours first (low intensity), then dirty hours (high intensity).
    intensity = [100, 100, 100, 900, 900, 900]
    res = cb.simulate_carbon(
        intensity, power_mw=10, capacity_mwh=30, efficiency=1.0,
        charge_pct=0.49, discharge_pct=0.5,
    )
    # Should charge during the first (clean) hours.
    assert sum(res.charge[:3]) > 0
    # Should discharge during the later (dirty) hours.
    assert sum(res.discharge[3:]) > 0


def test_soc_bounds():
    intensity = [100, 200, 300, 800, 900, 150, 850]
    res = cb.simulate_carbon(intensity, power_mw=20, capacity_mwh=40, efficiency=0.9)
    for s in res.soc:
        assert -1e-9 <= s <= 40 + 1e-9


def test_net_co2_avoided_positive_with_gap():
    # Big clean/dirty gap, lossless -> net CO2 avoided should be positive.
    intensity = [100] * 4 + [900] * 4
    res = cb.simulate_carbon(
        intensity, power_mw=10, capacity_mwh=40, efficiency=1.0,
        charge_pct=0.49, discharge_pct=0.5,
    )
    assert res.net_co2_avoided_lbs > 0
    assert res.net_co2_avoided_kg == pytest.approx(
        res.net_co2_avoided_lbs * cb.LB_TO_KG
    )


def test_efficiency_reduces_benefit():
    intensity = [100] * 4 + [900] * 4
    lossless = cb.simulate_carbon(
        intensity, 10, 40, 1.0, charge_pct=0.49, discharge_pct=0.5
    )
    lossy = cb.simulate_carbon(
        intensity, 10, 40, 0.80, charge_pct=0.49, discharge_pct=0.5
    )
    # Losses mean less energy delivered -> less CO2 displaced.
    assert lossy.co2_displaced_lbs <= lossless.co2_displaced_lbs + 1e-9


def test_net_never_negative_on_flat_day():
    # A nearly flat carbon profile: cycling would lose to efficiency, so the
    # battery should stay idle and net avoided must be >= 0 (not negative).
    intensity = [500 + (i % 2) for i in range(24)]  # tiny 1-unit wiggle
    res = cb.simulate_carbon(intensity, 100, 400, 0.90)
    assert res.net_co2_avoided_lbs >= -1e-6


def test_net_never_negative_random_profiles():
    import random
    random.seed(0)
    for _ in range(50):
        intensity = [random.uniform(400, 650) for _ in range(24)]
        res = cb.simulate_carbon(intensity, 200, 800, 0.90)
        assert res.net_co2_avoided_lbs >= -1e-6, "net CO2 avoided must never be negative"


def test_discharge_never_exceeds_power():
    intensity = [100, 100, 900, 900]
    res = cb.simulate_carbon(intensity, power_mw=5, capacity_mwh=100, efficiency=1.0,
                             charge_pct=0.49, discharge_pct=0.5)
    assert all(d <= 5 + 1e-9 for d in res.discharge)
