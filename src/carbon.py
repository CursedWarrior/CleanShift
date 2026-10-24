"""Carbon-intensity estimation from the ISO-NE generation fuel mix.

We estimate how "dirty" each hour of grid electricity is by weighting each fuel
type's generation (MW) by a standard CO2 emission factor (lbs CO2 per MWh) and
dividing by total generation. The result is an average carbon intensity in
lbs CO2/MWh for each hour.

Emission factors
----------------
Standard, well-established values (EPA / EIA order of magnitude). Zero-carbon
fuels (nuclear, hydro, solar, wind) emit no CO2 at generation. These are
documented, rounded figures for a demo, not plant-specific measurements.

    Coal            ~2100 lbs/MWh
    Oil             ~1700 lbs/MWh
    Natural Gas     ~900  lbs/MWh
    Refuse (MSW)    ~1000 lbs/MWh
    Landfill Gas    ~500  lbs/MWh (biogenic; counted modestly)
    Wood (biomass)  ~0    lbs/MWh at stack (biogenic; treated as ~carbon-neutral)
    Other           ~1200 lbs/MWh (unknown mix; conservative mid value)
    Nuclear/Hydro/Solar/Wind  0

Caveat: this is an AVERAGE-mix intensity, not a marginal signal (what the next
kWh would cause). It is a defensible, transparent estimate; a true marginal
rate is not freely available at hourly resolution for ISO-NE.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_FUELMIX_FILE = "isone_fuelmix.csv"

# lbs CO2 per MWh. Documented, rounded standard values.
EMISSION_FACTORS: dict[str, float] = {
    "Coal": 2100.0,
    "Oil": 1700.0,
    "Natural Gas": 900.0,
    "Refuse": 1000.0,
    "Landfill Gas": 500.0,
    "Wood": 0.0,
    "Other": 1200.0,
    "Nuclear": 0.0,
    "Hydro": 0.0,
    "Solar": 0.0,
    "Wind": 0.0,
}

# Fuels considered clean/renewable for the "clean share" metric.
CLEAN_FUELS = ["Nuclear", "Hydro", "Solar", "Wind"]


class FuelMixNotFoundError(FileNotFoundError):
    """Raised when the cached fuel-mix CSV is missing."""


def default_fuelmix_path() -> Path:
    return DEFAULT_DATA_DIR / DEFAULT_FUELMIX_FILE


def load_fuelmix(path: str | Path | None = None) -> pd.DataFrame:
    """Load the cached hourly fuel-mix CSV (produced by ``fetch_fuelmix.py``)."""
    path = Path(path) if path is not None else default_fuelmix_path()
    if not path.exists():
        raise FuelMixNotFoundError(
            f"Expected cached fuel-mix file at '{path}'. "
            "Run `python fetch_fuelmix.py` to create it."
        )
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)


def _fuel_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in EMISSION_FACTORS if c in df.columns]


def carbon_intensity(df: pd.DataFrame) -> pd.Series:
    """Return hourly carbon intensity (lbs CO2/MWh) for a fuel-mix DataFrame.

    intensity = sum(fuel_MW * factor) / sum(fuel_MW)
    """
    fuels = _fuel_columns(df)
    generation = df[fuels].clip(lower=0.0)
    total = generation.sum(axis=1)
    weighted = sum(generation[f] * EMISSION_FACTORS[f] for f in fuels)
    intensity = weighted / total.replace(0.0, pd.NA)
    return intensity.astype(float)


def clean_share(df: pd.DataFrame) -> pd.Series:
    """Fraction (0..1) of generation from clean fuels each hour."""
    fuels = _fuel_columns(df)
    clean = [f for f in CLEAN_FUELS if f in df.columns]
    generation = df[fuels].clip(lower=0.0)
    total = generation.sum(axis=1)
    clean_gen = generation[clean].sum(axis=1)
    return (clean_gen / total.replace(0.0, pd.NA)).astype(float)


def with_intensity(df: pd.DataFrame) -> pd.DataFrame:
    """Return the fuel-mix frame with added ``carbon_lbs_per_mwh``,
    ``solar_mw`` and ``clean_share`` columns."""
    out = df.copy()
    out["carbon_lbs_per_mwh"] = carbon_intensity(df)
    out["solar_mw"] = df["Solar"] if "Solar" in df.columns else 0.0
    out["clean_share"] = clean_share(df)
    return out


def load_carbon(path: str | Path | None = None) -> pd.DataFrame:
    """Convenience: load the fuel mix and return it with intensity columns.

    Returns columns: ``timestamp``, all fuels, ``carbon_lbs_per_mwh``,
    ``solar_mw``, ``clean_share``.
    """
    return with_intensity(load_fuelmix(path))
