"""Carbon-aware battery dispatch: store clean energy, release it when dirty.

This is the second lever alongside load-shifting. Standard battery mechanics
(power, capacity, round-trip efficiency, hourly state of charge) but the
dispatch decision is driven by CARBON INTENSITY instead of demand:

  * Charge during the cleanest hours (low lbs CO2/MWh) — ideally soaking up
    midday solar that would otherwise be surplus.
  * Discharge during the dirtiest hours (high intensity) — displacing gas/oil
    generation that would otherwise serve that load.

Net CO2 effect per hour:
    discharging D MWh at intensity I_dis  -> avoids  D * I_dis   (clean energy
                                                                  serves load)
    charging    C MWh at intensity I_chg  -> causes  C * I_chg   (that charge
                                                                  was generated)
Because charging happens in clean hours (low I_chg) and discharging in dirty
hours (high I_dis), and efficiency losses are modeled, the net is a CO2 saving
when the clean/dirty gap beats the round-trip loss.

Strategy
--------
A simple, explainable threshold rule: rank the hours by intensity. Charge when
intensity is in the cleanest band, discharge when it is in the dirtiest band,
bounded by power, capacity, and efficiency. The bands are chosen by percentile
so the battery cycles roughly once per day's clean/dirty swing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

LB_TO_KG = 0.453592


@dataclass
class CarbonDispatchResult:
    charge: list[float]        # MW drawn to charge each hour
    discharge: list[float]     # MW delivered each hour
    soc: list[float]           # state of charge at end of each hour (MWh)
    intensity: list[float]     # carbon intensity per hour (lbs/MWh)
    co2_charged_lbs: float     # CO2 attributable to charging energy
    co2_displaced_lbs: float   # CO2 avoided by discharging clean energy
    power_mw: float
    capacity_mwh: float
    efficiency: float

    @property
    def net_co2_avoided_lbs(self) -> float:
        return self.co2_displaced_lbs - self.co2_charged_lbs

    @property
    def net_co2_avoided_kg(self) -> float:
        return self.net_co2_avoided_lbs * LB_TO_KG

    @property
    def cycles(self) -> float:
        if self.capacity_mwh <= 0:
            return 0.0
        return sum(self.discharge) / self.capacity_mwh


def _charge_factor(efficiency: float) -> float:
    return math.sqrt(max(min(efficiency, 1.0), 1e-9))


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(int(q * (len(sorted_vals) - 1)), len(sorted_vals) - 1)
    return sorted_vals[idx]


def simulate_carbon(
    intensity: list[float],
    power_mw: float,
    capacity_mwh: float,
    efficiency: float,
    charge_pct: float = 0.33,
    discharge_pct: float = 0.67,
    initial_soc: float = 0.0,
) -> CarbonDispatchResult:
    """Dispatch a battery to charge clean and discharge dirty.

    Parameters
    ----------
    intensity:
        Hourly carbon intensity (lbs CO2/MWh).
    power_mw, capacity_mwh, efficiency:
        Battery parameters. Efficiency loss is split sqrt-wise across charge
        and discharge.
    charge_pct, discharge_pct:
        Percentile thresholds. Charge when an hour's intensity is at/below the
        ``charge_pct`` percentile; discharge when at/above ``discharge_pct``.
    """
    intensity = [float(x) for x in intensity]
    f = _charge_factor(efficiency)

    ordered = sorted(intensity)
    low_thr = _percentile(ordered, charge_pct)
    high_thr = _percentile(ordered, discharge_pct)

    soc = float(initial_soc)
    charge: list[float] = []
    discharge: list[float] = []
    soc_trace: list[float] = []
    co2_charged = 0.0
    co2_displaced = 0.0

    for ci in intensity:
        hour_charge = 0.0
        hour_discharge = 0.0

        if ci <= low_thr:
            # Clean hour: charge using available room.
            room = capacity_mwh - soc
            max_grid_for_room = room / f if f > 0 else 0.0
            hour_charge = max(min(power_mw, max_grid_for_room), 0.0)
            soc += hour_charge * f
            if soc > capacity_mwh:
                soc = capacity_mwh
            co2_charged += hour_charge * ci
        elif ci >= high_thr:
            # Dirty hour: discharge stored energy.
            deliverable = soc * f
            hour_discharge = max(min(power_mw, deliverable), 0.0)
            soc -= hour_discharge / f
            if soc < 0:
                soc = 0.0
            co2_displaced += hour_discharge * ci

        charge.append(hour_charge)
        discharge.append(hour_discharge)
        soc_trace.append(soc)

    return CarbonDispatchResult(
        charge=charge,
        discharge=discharge,
        soc=soc_trace,
        intensity=intensity,
        co2_charged_lbs=co2_charged,
        co2_displaced_lbs=co2_displaced,
        power_mw=power_mw,
        capacity_mwh=capacity_mwh,
        efficiency=efficiency,
    )
