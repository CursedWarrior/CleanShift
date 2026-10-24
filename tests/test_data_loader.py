import pandas as pd
import pytest

from src import data_loader


FIXTURE = """Date,Hr_End,DA_Demand,RT_Demand,DA_LMP,DA_EC,DA_CC,DA_MLC,RT_LMP,RT_EC,RT_CC,RT_MLC,Dry_Bulb,Dew_Point
1/1/2025,01,"2,268.70","2,260.96",37.82,37.17,0.00,0.65,56.54,55.51,0.00,1.03,42,40
1/1/2025,24,"3,100.00","3,090.50",40.00,39.00,0.00,1.00,60.00,58.00,0.00,2.00,38,35
2/1/2025,01,"1,000.00","1,010.00",30.00,29.00,0.00,1.00,50.00,49.00,0.00,1.00,30,28
"""


@pytest.fixture
def csv_file(tmp_path):
    p = tmp_path / "isone.csv"
    p.write_text(FIXTURE)
    return p


def test_load_raw_strips_commas(csv_file):
    df = data_loader.load_raw(csv_file)
    # Comma-stripped float parsing.
    assert df.loc[0, "demand_mw"] == pytest.approx(2260.96)
    assert df.loc[1, "demand_mw"] == pytest.approx(3090.50)


def test_timestamp_hour_ending_to_start(csv_file):
    df = data_loader.load_raw(csv_file)
    # Hr_End 01 -> 00:00 of that day.
    assert df.loc[0, "timestamp"] == pd.Timestamp("2025-01-01 00:00:00")
    # Hr_End 24 -> 23:00 of the SAME day (final hour), no next-day rollover.
    assert df.loc[1, "timestamp"] == pd.Timestamp("2025-01-01 23:00:00")


def test_load_demand_filters_january(csv_file):
    df = data_loader.load_demand(csv_file, year=2025, month=1)
    # Only the two January rows remain (the Feb row is dropped).
    assert len(df) == 2
    assert (df["timestamp"].dt.month == 1).all()


def test_load_demand_no_month_returns_all(csv_file):
    df = data_loader.load_demand(csv_file, month=None)
    assert len(df) == 3


def test_missing_file_raises():
    with pytest.raises(data_loader.DataFileNotFoundError):
        data_loader.load_raw("does_not_exist_12345.csv")


def test_summarize(csv_file):
    df = data_loader.load_demand(csv_file, year=2025, month=1)
    s = data_loader.summarize(df)
    assert s["rows"] == 2
    assert s["max_mw"] == pytest.approx(3090.50)
    assert s["peak_timestamp"] == pd.Timestamp("2025-01-01 23:00:00")
