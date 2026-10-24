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
bounded by power, capacity, and efficiency. Candidate clean/dirty hours are
chosen by percentile, but each discharge is only committed when it is
carbon-POSITIVE after round-trip losses: stored energy carries a carbon
"cost basis" and is released only into hours dirty enough that delivering it
avoids more CO2 than it cost to store. On flat days with too small a clean/dirty
swing the battery simply stays idle, so the net CO2 avoided is never negative
(cycling at a loss is never worthwhile).
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
    eff = max(min(efficiency, 1.0), 1e-9)
    n = len(intensity)

    charge = [0.0] * n       # grid MWh drawn to charge each hour
    discharge = [0.0] * n    # MWh delivered each hour
    # Per-hour remaining power headroom (an hour can only do one or the other).
    charge_room = [power_mw] * n
    discharge_room = [power_mw] * n

    # Rank-based greedy matching: repeatedly take the DIRTIEST hour that can
    # still discharge and pair it with the CLEANEST earlier hour that can still
    # charge, as long as the pairing is carbon-POSITIVE after round-trip losses
    # (dirty_ci * eff >= clean_ci) and capacity is never exceeded in between.
    # This prioritizes saving stored energy for the dirtiest hours instead of
    # dumping it into the first above-threshold hour (the old greedy flaw).
    dirty_order = sorted(range(n), key=lambda i: intensity[i], reverse=True)

    def soc_after(ch: list[float], di: list[float]) -> list[float]:
        s, trace = 0.0, []
        for i in range(n):
            s += ch[i] * f - di[i] / f
            s = min(max(s, 0.0), capacity_mwh)
            trace.append(s)
        return trace

    def free_capacity_between(ch, di, a, b) -> float:
        """Min spare capacity over hours [a, b] (so adding a charge->discharge
        pair won't overflow the tank at any point in between)."""
        s, spare = 0.0, capacity_mwh
        for i in range(n):
            s += ch[i] * f - di[i] / f
            s = min(max(s, 0.0), capacity_mwh)
            if a <= i < b:
                spare = min(spare, capacity_mwh - s)
        return max(spare, 0.0)

    for d_idx in dirty_order:
        d_ci = intensity[d_idx]
        # Cleanest earlier hours first.
        charge_candidates = sorted(
            (i for i in range(d_idx) if intensity[i] * 1.0 < d_ci * eff - 1e-9),
            key=lambda i: intensity[i],
        )
        for c_idx in charge_candidates:
            if discharge_room[d_idx] <= 1e-9:
                break
            if charge_room[c_idx] <= 1e-9:
                continue
            # Profitability: delivering `out` avoids out*d_ci; the stored energy
            # it uses cost (out / f) * c_ci / f  ... in grid terms, charging
            # `g` grid MWh stores g*f, delivering that gives g*f*f = g*eff MWh.
            # So charging g at c_ci and discharging yields net d_ci*g*eff - c_ci*g.
            if d_ci * eff <= intensity[c_idx] + 1e-9:
                continue
            # How much grid-charge can we add at c_idx and deliver at d_idx?
            spare = free_capacity_between(charge, discharge, c_idx, d_idx)  # stored MWh room
            # grid charge limited by: charge power, discharge power/eff, capacity room.
            max_by_charge = charge_room[c_idx]
            max_by_discharge = discharge_room[d_idx] / eff
            max_by_cap = spare / f if f > 0 else 0.0
            g = min(max_by_charge, max_by_discharge, max_by_cap)
            if g <= 1e-9:
                continue
            charge[c_idx] += g
            discharge[d_idx] += g * eff
            charge_room[c_idx] -= g
            discharge_room[d_idx] -= g * eff

    # Tally carbon: each delivered MWh at hour i avoids intensity[i]; each grid
    # MWh charged at hour j cost intensity[j].
    co2_displaced = sum(discharge[i] * intensity[i] for i in range(n))
    co2_charged = sum(charge[i] * intensity[i] for i in range(n))
    soc_trace = soc_after(charge, discharge)

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


def binding_constraint(
    intensity: list[float],
    power_mw: float,
    capacity_mwh: float,
    efficiency: float,
    probe: float = 1.25,
    tol: float = 0.02,
) -> dict:
    """Diagnose what limits the battery: power, energy (capacity), both, or none.

    We re-run the dispatch with ~25% more power (capacity fixed) and with ~25%
    more capacity (power fixed), and compare the net CO2 avoided to the baseline.
    Whichever unlocks a meaningful gain is "binding"; if neither helps, the day
    is simply too flat.

    Returns a dict: ``label`` in {"power", "energy", "both", "none"},
    plus ``power_gain`` / ``energy_gain`` (fractional improvements).
    """
    base = simulate_carbon(intensity, power_mw, capacity_mwh, efficiency)
    base_net = base.net_co2_avoided_lbs

    more_power = simulate_carbon(intensity, power_mw * probe, capacity_mwh, efficiency)
    more_cap = simulate_carbon(intensity, power_mw, capacity_mwh * probe, efficiency)

    def gain(r) -> float:
        if base_net <= 1e-9:
            return (r.net_co2_avoided_lbs - base_net)  # absolute if base ~0
        return (r.net_co2_avoided_lbs - base_net) / base_net

    pg = gain(more_power)
    eg = gain(more_cap)

    power_helps = pg > tol
    energy_helps = eg > tol

    if base_net <= 1e-9 and not power_helps and not energy_helps:
        label = "none"
    elif power_helps and energy_helps:
        label = "both"
    elif power_helps:
        label = "power"
    elif energy_helps:
        label = "energy"
    else:
        label = "none"

    return {"label": label, "power_gain": pg, "energy_gain": eg}
