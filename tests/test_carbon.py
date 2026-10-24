import pandas as pd
import pytest

from src import carbon


def _fixture():
    # Two hours: one gas-heavy (dirty), one solar+nuclear-heavy (clean).
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2025-06-01 19:00", "2025-06-01 13:00"]),
            "Natural Gas": [1000.0, 100.0],
            "Solar": [0.0, 500.0],
            "Nuclear": [0.0, 400.0],
            "Coal": [0.0, 0.0],
            "Oil": [0.0, 0.0],
            "Hydro": [0.0, 0.0],
            "Wind": [0.0, 0.0],
            "Refuse": [0.0, 0.0],
            "Landfill Gas": [0.0, 0.0],
            "Wood": [0.0, 0.0],
            "Other": [0.0, 0.0],
        }
    )


def test_carbon_intensity_hand_computed():
    df = _fixture()
    ci = carbon.carbon_intensity(df)
    # Hour 0: all gas -> exactly the gas factor (900).
    assert ci.iloc[0] == pytest.approx(900.0)
    # Hour 1: 100 gas (*900) / (100+500+400) total = 90000/1000 = 90.
    assert ci.iloc[1] == pytest.approx(90.0)


def test_clean_hour_is_cleaner_than_dirty_hour():
    df = _fixture()
    ci = carbon.carbon_intensity(df)
    assert ci.iloc[1] < ci.iloc[0]


def test_clean_share():
    df = _fixture()
    cs = carbon.clean_share(df)
    # Hour 0: 0 clean / 1000 = 0.
    assert cs.iloc[0] == pytest.approx(0.0)
    # Hour 1: (500 solar + 400 nuclear) / 1000 = 0.9.
    assert cs.iloc[1] == pytest.approx(0.9)


def test_zero_carbon_fuels_contribute_nothing():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2025-06-01 13:00"]),
            "Solar": [500.0],
            "Wind": [300.0],
            "Hydro": [200.0],
            "Nuclear": [100.0],
            "Natural Gas": [0.0],
            "Coal": [0.0],
            "Oil": [0.0],
            "Refuse": [0.0],
            "Landfill Gas": [0.0],
            "Wood": [0.0],
            "Other": [0.0],
        }
    )
    ci = carbon.carbon_intensity(df)
    assert ci.iloc[0] == pytest.approx(0.0)


def test_with_intensity_adds_columns():
    df = _fixture()
    out = carbon.with_intensity(df)
    for col in ("carbon_lbs_per_mwh", "solar_mw", "clean_share"):
        assert col in out.columns


def test_missing_file_raises():
    with pytest.raises(carbon.FuelMixNotFoundError):
        carbon.load_fuelmix("nonexistent_fuelmix_file.csv")
