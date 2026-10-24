"""Data loading and cleaning for ISO-NE Massachusetts demand data.

Source: the ISO-NE "SMD hourly" report, an Excel workbook (``.xlsx``) with one
sheet per load zone. We read the **NEMA** sheet (Northeast Massachusetts /
Boston). Its columns are:

    Date, Hr_End, DA_Demand, RT_Demand, DA_LMP, DA_EC, DA_CC, DA_MLC,
    RT_LMP, RT_EC, RT_CC, RT_MLC, Dry_Bulb, Dew_Point

Notes handled here:
  * ``Date`` may arrive as a real datetime (Excel) or an ``M/D/YYYY`` string
    (CSV); both are handled.
  * ``Hr_End`` is the *hour ending* (01..24). The start-of-hour timestamp is
    ``date + (Hr_End - 1) hours``. Hour 24 therefore maps to 23:00 of the same
    calendar day (i.e. the final hour of that day), which keeps every reading on
    its own day and avoids an awkward next-day rollover.
  * Numeric fields may use thousands commas (e.g. ``2,268.70`` in CSV exports);
    these are stripped defensively before parsing.

The loader accepts both ``.xlsx``/``.xls`` (read via a sheet) and ``.csv``, so
test fixtures and future exports both work.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Default location/name of the bundled data file. The user drops their download
# here. We keep the name fixed but fail gracefully if it is missing.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_FILENAME = "2025_smd_hourly.xlsx"
DEFAULT_SHEET = "NEMA"  # Northeast Massachusetts / Boston

# Numeric columns that may contain thousands commas (in CSV exports).
_NUMERIC_COLUMNS = [
    "DA_Demand",
    "RT_Demand",
    "DA_LMP",
    "DA_EC",
    "DA_CC",
    "DA_MLC",
    "RT_LMP",
    "RT_EC",
    "RT_CC",
    "RT_MLC",
    "Dry_Bulb",
    "Dew_Point",
]


class DataFileNotFoundError(FileNotFoundError):
    """Raised when the expected ISO-NE data file is not present."""


def default_data_path() -> Path:
    """Return the default expected path of the data file."""
    return DEFAULT_DATA_DIR / DEFAULT_FILENAME


def _strip_commas(series: pd.Series) -> pd.Series:
    """Remove thousands commas and coerce to float (no-op for real numbers)."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def _build_timestamp(date_col: pd.Series, hr_end_col: pd.Series) -> pd.Series:
    """Build a start-of-hour timestamp from Date + Hr_End (hour ending 1..24).

    ``Date`` may be a real datetime (Excel) or an ``M/D/YYYY`` string (CSV);
    ``pd.to_datetime`` handles both.

    ``Hr_End`` is normally ``01``..``24``, but on the November daylight-saving
    "fall back" day ISO-NE tags the repeated 2 a.m. hour as ``02X``. We extract
    the leading digits so ``02X`` -> hour 2. Rows whose hour can't be parsed
    yield NaT and are dropped downstream.
    """
    base_date = pd.to_datetime(date_col).dt.normalize()
    # Keep only leading digits (handles the DST "02X" marker).
    hr_digits = hr_end_col.astype(str).str.extract(r"(\d+)", expand=False)
    hour_num = pd.to_numeric(hr_digits, errors="coerce")
    hour_start = hour_num - 1
    offset = pd.to_timedelta(hour_start, unit="h")
    return base_date + offset


def _read_file(path: Path, sheet: str) -> pd.DataFrame:
    """Read the raw table from either an Excel sheet or a CSV."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path, sheet_name=sheet, dtype=str)
    return pd.read_csv(path, dtype=str)


def load_raw(
    path: str | Path | None = None,
    sheet: str = DEFAULT_SHEET,
) -> pd.DataFrame:
    """Load and clean the full data file into a tidy DataFrame.

    Returns a DataFrame with columns ``timestamp``, ``demand_mw`` (from
    ``RT_Demand``), ``da_demand_mw`` (from ``DA_Demand``), plus the LMP price
    columns preserved for later use. Sorted by timestamp.

    Parameters
    ----------
    path:
        Path to the data file. Defaults to ``data/2025_smd_hourly.xlsx``.
        ``.xlsx``/``.xls`` are read from ``sheet``; ``.csv`` is read directly.
    sheet:
        Worksheet name for Excel files (default ``"NEMA"``). Ignored for CSV.

    Raises :class:`DataFileNotFoundError` if the file is missing.
    """
    path = Path(path) if path is not None else default_data_path()
    if not path.exists():
        raise DataFileNotFoundError(
            f"Expected ISO-NE data file at '{path}'. "
            "Download the ISO-NE SMD hourly workbook and place it there."
        )

    df = _read_file(path, sheet)
    df.columns = [str(c).strip() for c in df.columns]

    for col in _NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = _strip_commas(df[col])

    timestamp = _build_timestamp(df["Date"], df["Hr_End"])

    tidy = pd.DataFrame(
        {
            "timestamp": timestamp,
            "demand_mw": df["RT_Demand"],
            "da_demand_mw": df.get("DA_Demand"),
            "rt_lmp": df.get("RT_LMP"),
            "da_lmp": df.get("DA_LMP"),
        }
    )

    tidy = tidy.dropna(subset=["timestamp", "demand_mw"])
    tidy = tidy.sort_values("timestamp").reset_index(drop=True)
    return tidy


def filter_month(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Return rows within the given calendar month."""
    mask = (df["timestamp"].dt.year == year) & (df["timestamp"].dt.month == month)
    return df.loc[mask].reset_index(drop=True)


def load_demand(
    path: str | Path | None = None,
    year: int = 2025,
    month: int | None = 1,
    sheet: str = DEFAULT_SHEET,
) -> pd.DataFrame:
    """Load demand data, optionally filtered to a single month.

    Parameters
    ----------
    path:
        Path to the data file. Defaults to ``data/2025_smd_hourly.xlsx``.
    year:
        Calendar year to filter to (used only when ``month`` is given).
    month:
        Month (1-12) to filter to. Pass ``None`` to return the whole file.
    sheet:
        Worksheet name for Excel files (default ``"NEMA"``).

    Returns
    -------
    DataFrame with ``timestamp`` and ``demand_mw`` (and price columns),
    sorted and ready for simulation.
    """
    tidy = load_raw(path, sheet=sheet)
    if month is None:
        return tidy
    return filter_month(tidy, year, month)


def summarize(df: pd.DataFrame) -> dict:
    """Return quick summary stats for a demand DataFrame."""
    if df.empty:
        return {"rows": 0}
    peak_idx = df["demand_mw"].idxmax()
    return {
        "rows": int(len(df)),
        "min_mw": float(df["demand_mw"].min()),
        "max_mw": float(df["demand_mw"].max()),
        "mean_mw": float(df["demand_mw"].mean()),
        "peak_timestamp": df.loc[peak_idx, "timestamp"],
    }
