"""Clean Shift — a carbon-aware load & storage optimizer for the MA grid.

The grid is cleanest when solar is abundant (midday) and dirtiest during the
evening gas-peaker ramp. Clean Shift shows that swing using real ISO-NE data and
gives two levers to exploit it:

  1. Load-shift advisor — when to run a flexible load (e.g. EV charging) to cut CO2.
  2. Carbon battery — charge on clean/solar hours, discharge during dirty hours.

Run locally with:
    streamlit run app.py

This starts a local web server (default http://localhost:8501). Nothing is
deployed to the cloud.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src import (
    carbon,
    carbon_battery as cb,
    data_loader,
    forecast,
    loadshift,
    presets,
    timeline,
)

# Full-year hourly data exceeds Altair's default 5,000-row cap once melted;
# lift it (we also downsample long windows for legibility).
alt.data_transformers.disable_max_rows()
MAX_HOURLY_CHART_POINTS = 24 * 10  # ~10 days

ROUND_TRIP_EFFICIENCY = 0.90

# Plain-English tooltips shown as a hoverable "?" next to each control/metric.
HELP = {
    "carbon_intensity": (
        "How much CO2 the grid emits per unit of electricity right now "
        "(pounds of CO2 per megawatt-hour). It drops when clean sources like "
        "solar and wind are generating, and rises when gas or oil 'peaker' "
        "plants ramp up. Lower is cleaner."
    ),
    "emission_factors": (
        "We estimate each hour's CO2 from the grid's fuel mix, weighting each "
        "fuel by a standard emission factor: coal ~2,100, oil ~1,700, natural "
        "gas ~900 lbs CO2/MWh; nuclear, hydro, solar and wind ~0. It's an "
        "average-mix estimate, not a plant-by-plant measurement."
    ),
    "energy_kwh": (
        "How much energy the flexible load needs in total. A typical EV charge "
        "is 30-60 kWh; a dishwasher ~1.5 kWh."
    ),
    "duration": "How many hours the load runs once it starts.",
    "baseline": (
        "The hour you'd normally start the load out of habit (e.g. 7pm after "
        "work). We compare the cleanest window against this to show what timing "
        "alone saves."
    ),
    "power": (
        "How fast the battery charges/discharges (MW) — the 'tap' size. Here it "
        "decides how much clean energy it can soak up or release each hour."
    ),
    "capacity": (
        "How much energy the battery stores (MWh) — the 'tank' size. More "
        "capacity lets it carry more clean midday energy into the dirty evening."
    ),
    "co2_avoided_shift": "CO2 you'd avoid by running the load in the cleanest window instead of at your usual time.",
    "co2_avoided_batt": (
        "Net CO2 avoided over the period: dirty generation displaced when the "
        "battery discharges, minus the CO2 of the (cleaner) energy it charged "
        "with, after round-trip losses."
    ),
    "cycles": "How many full charge/discharge cycles the battery ran over the period.",
    "clean_share": "Share of grid electricity coming from clean sources (nuclear, hydro, solar, wind) this hour.",
    "forecast": (
        "Today and Tomorrow use a live forecast of carbon intensity built with "
        "grid dispatch logic: we start from ISO-NE's demand forecast, subtract "
        "its official solar and wind forecasts (plus typical nuclear and hydro), "
        "and assume the leftover demand is met by gas and other fossil plants — "
        "then apply standard emission factors. It's an estimate, not an official "
        "projection, and the forecast only reaches ~48 hours ahead (today + "
        "tomorrow), limited by ISO-NE's demand forecast."
    ),
}

INTRO_MD = """
**The idea in one line:** electricity is *cleaner at some hours than others*, so
*when* you use or store energy changes how much CO2 you cause.

Around midday, solar and wind are plentiful and the grid is relatively clean,
sometimes there's more clean power than the grid can use. In the evening the sun
sets, demand climbs, and the grid fires up its dirtiest gas and oil plants to
keep up. The **same** kilowatt-hour is greener at 1pm than at 7pm.

**Two ways to use that**
- **Shift a flexible load** (like EV charging) into the clean hours — free, no hardware.
- **Store it in a battery:** charge on clean midday/solar energy, discharge during the dirty evening.

Everything here uses **real ISO-NE data** (Boston-area demand + the grid's
hour-by-hour fuel mix, from Jan 2025 to the latest available day). The load-shift
advisor can also use a **live 48-hour forecast** so its advice is about a time
you can still act on. Hover any **?** for a plain-English definition.
"""


st.set_page_config(page_title="Clean Shift", page_icon="🌱", layout="wide")


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _load_timeline() -> pd.DataFrame:
    """Historical rows with both demand and carbon (battery & duck-curve tabs)."""
    return timeline.build_timeline()


@st.cache_data(show_spinner=False)
def _load_carbon_history() -> pd.DataFrame:
    """Full historical carbon timeline (2025 -> latest cached)."""
    return timeline.load_carbon_history()


@st.cache_data(show_spinner="Fetching the latest 48-hour grid forecast...", ttl=3600)
def _load_forecast(history_max_ts: str) -> pd.DataFrame:
    """Live 48h forecast. Cached for an hour; keyed on the history extent so it
    refreshes if the cache is rebuilt. Returns empty DataFrame on failure."""
    try:
        hist = _load_carbon_history()
        return forecast.build_forecast_timeline(hist)
    except Exception:
        return pd.DataFrame()


def _init_state():
    st.session_state.setdefault("batt_power_mw", 50)
    st.session_state.setdefault("batt_capacity_mwh", 200)


def _apply_preset(name: str):
    p = presets.get_preset(name)
    st.session_state["batt_power_mw"] = int(p.power_mw)
    st.session_state["batt_capacity_mwh"] = int(p.capacity_mwh)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def _maybe_downsample(plot_df: pd.DataFrame, value_cols: list[str]) -> tuple[pd.DataFrame, bool]:
    """Aggregate to daily means for long windows so charts stay legible."""
    if len(plot_df) <= MAX_HOURLY_CHART_POINTS:
        return plot_df, False
    daily = (
        plot_df.set_index("timestamp")[value_cols]
        .resample("D")
        .mean()
        .reset_index()
        .dropna()
    )
    return daily, True


def carbon_chart(window: pd.DataFrame) -> alt.Chart:
    plot_df = pd.DataFrame(
        {
            "timestamp": list(pd.to_datetime(window["timestamp"])),
            "Carbon intensity": [float(x) for x in window["carbon_lbs_per_mwh"]],
        }
    )
    plot_df, aggregated = _maybe_downsample(plot_df, ["Carbon intensity"])
    x_title = "Day (daily average)" if aggregated else "Hour"
    return (
        alt.Chart(plot_df)
        .mark_area(opacity=0.7, color="#16a34a", line={"color": "#15803d"})
        .encode(
            x=alt.X("timestamp:T", title=x_title),
            y=alt.Y("Carbon intensity:Q", title="lbs CO2 / MWh",
                    scale=alt.Scale(zero=False)),
            tooltip=["timestamp:T", "Carbon intensity:Q"],
        )
        .properties(height=300)
    )


def solar_carbon_chart(day: pd.DataFrame) -> alt.Chart:
    """Single-day dual view: solar MW vs carbon intensity, to show the duck curve."""
    base = pd.DataFrame(
        {
            "timestamp": list(pd.to_datetime(day["timestamp"])),
            "Solar (MW)": [float(x) for x in day["solar_mw"]],
            "Carbon (lbs/MWh)": [float(x) for x in day["carbon_lbs_per_mwh"]],
        }
    )
    solar = (
        alt.Chart(base)
        .mark_area(opacity=0.35, color="#f59e0b")
        .encode(
            x=alt.X("timestamp:T", title="Hour"),
            y=alt.Y("Solar (MW):Q", title="Solar generation (MW)"),
        )
    )
    carbon_line = (
        alt.Chart(base)
        .mark_line(color="#15803d", strokeWidth=3)
        .encode(
            x="timestamp:T",
            y=alt.Y("Carbon (lbs/MWh):Q", title="Carbon intensity (lbs/MWh)",
                    scale=alt.Scale(zero=False)),
        )
    )
    return alt.layer(solar, carbon_line).resolve_scale(y="independent").properties(height=320)


def battery_dispatch_chart(window: pd.DataFrame, res) -> alt.Chart:
    """Show the battery working: carbon curve + charge/discharge bars + SOC.

    This visibly responds to battery power/capacity changes (unlike the raw
    carbon curve), because the bars and the SOC line are outputs of the
    dispatch.
    """
    ts = list(pd.to_datetime(window["timestamp"]))
    base = pd.DataFrame(
        {
            "timestamp": ts,
            "Carbon": [float(x) for x in window["carbon_lbs_per_mwh"]],
            "SOC": [float(x) for x in res.soc],
            # Discharge shown as positive, charge as negative, so the bars read
            # as "pulling from" vs "pushing to" the grid.
            "Power": [float(d) - float(c) for c, d in zip(res.charge, res.discharge)],
        }
    )
    base["Action"] = base["Power"].apply(
        lambda p: "Discharge (clean out)" if p > 1e-9
        else ("Charge (store)" if p < -1e-9 else "Idle")
    )

    carbon_line = (
        alt.Chart(base)
        .mark_line(color="#15803d", strokeWidth=2)
        .encode(
            x=alt.X("timestamp:T", title="Hour"),
            y=alt.Y("Carbon:Q", title="Carbon intensity (lbs/MWh)",
                    scale=alt.Scale(zero=False)),
            tooltip=["timestamp:T", "Carbon:Q"],
        )
    )
    bars = (
        alt.Chart(base)
        .mark_bar(opacity=0.6)
        .encode(
            x="timestamp:T",
            y=alt.Y("Power:Q", title="Battery power (MW)  —  charge ↓ / discharge ↑"),
            color=alt.Color(
                "Action:N", title="",
                scale=alt.Scale(
                    domain=["Charge (store)", "Discharge (clean out)", "Idle"],
                    range=["#16a34a", "#f59e0b", "#d1d5db"],
                ),
            ),
            tooltip=["timestamp:T", "Power:Q", "Action:N"],
        )
    )
    return alt.layer(bars, carbon_line).resolve_scale(y="independent").properties(height=360)


def shift_window_chart(day: pd.DataFrame, res: loadshift.ShiftResult) -> alt.Chart:
    base = pd.DataFrame(
        {
            "timestamp": list(pd.to_datetime(day["timestamp"])),
            "Carbon": [float(x) for x in day["carbon_lbs_per_mwh"]],
        }
    )
    line = (
        alt.Chart(base)
        .mark_line(color="#15803d")
        .encode(
            x=alt.X("timestamp:T", title="Hour"),
            y=alt.Y("Carbon:Q", title="lbs CO2 / MWh", scale=alt.Scale(zero=False)),
        )
        .properties(height=300)
    )
    best = pd.DataFrame({"start": [res.best_start], "end": [res.best_end_exclusive]})
    best_band = (
        alt.Chart(best)
        .mark_rect(opacity=0.25, color="#16a34a")
        .encode(x="start:T", x2="end:T")
    )
    base_pt = pd.DataFrame({"t": [res.baseline_start]})
    base_rule = (
        alt.Chart(base_pt)
        .mark_rule(color="#dc2626", strokeDash=[5, 4], strokeWidth=2)
        .encode(x="t:T")
    )
    return best_band + line + base_rule


# ---------------------------------------------------------------------------
# UI sections
# ---------------------------------------------------------------------------
def render_loadshift_tab(history: pd.DataFrame, fc: pd.DataFrame):
    st.subheader("When should I run a flexible load?")
    st.caption(
        "Tell us a load and we find the cleanest window to run it, and how much "
        "CO2 you'd avoid versus running it at your usual time."
    )

    forecast_available = fc is not None and not fc.empty

    # --- Mode: actionable forecast (Today / Tomorrow) vs. explore past ---
    if forecast_available:
        mode = st.radio(
            "Which day?",
            ["Today", "Tomorrow", "Explore a past day"],
            horizontal=True,
            help=HELP["forecast"],
        )
    else:
        st.warning(
            "Live forecast is unavailable right now (no network or the forecast "
            "feed is down). Showing historical days instead."
        )
        mode = "Explore a past day"

    c1, c2, c3 = st.columns(3)
    with c1:
        energy = st.number_input(
            "Energy needed (kWh)", min_value=1.0, max_value=200.0, value=50.0,
            step=1.0, help=HELP["energy_kwh"], key="shift_energy_kwh",
        )
    with c2:
        duration = st.number_input(
            "Run time (hours)", min_value=1, max_value=12, value=4,
            help=HELP["duration"], key="shift_duration_h",
        )
    with c3:
        baseline = st.slider(
            "Your usual start hour", min_value=0, max_value=23, value=19,
            help=HELP["baseline"], key="shift_baseline_hour",
        )

    if mode in ("Today", "Tomorrow"):
        fc_sorted = fc.sort_values("timestamp").reset_index(drop=True)
        today = pd.Timestamp(fc["timestamp"].min()).normalize()
        target = today if mode == "Today" else today + pd.Timedelta(days=1)
        day = _day_slice(fc_sorted, target)

        if mode == "Today":
            # Only hours from the current hour onward are actionable.
            now_hour = pd.Timestamp.now().floor("h")
            upcoming = day[day["timestamp"] >= now_hour]
            if len(upcoming) >= duration:
                day = upcoming.reset_index(drop=True)
                st.caption(
                    f"🔮 Live forecast for the rest of today "
                    f"(from {now_hour.strftime('%H:%M')}). Advice you can act on now."
                )
            else:
                # Too little of today left to fit the run — nudge to Tomorrow.
                st.info(
                    "Not enough of today left to fit this run. Showing the full "
                    "day's forecast; switch to **Tomorrow** for a full window."
                )
        else:
            st.caption("🔮 Live forecast for tomorrow. Plan ahead for the cleanest window.")

        if day.empty:
            st.warning("Forecast data for that day isn't available.")
            return
    else:
        day_choice = pick_day(history, "Day", key="shift_day")
        day = _day_slice(history, day_choice)

    if len(day) < duration:
        st.warning("Not enough hours in that window for this run time.")
        return

    res = loadshift.optimize_window(day, energy, int(duration), baseline)

    # Single calendar day now, so plain HH:MM labels are unambiguous.
    time_fmt = "%H:%M"
    win_start = res.best_start.strftime(time_fmt)
    win_end = res.best_end_exclusive.strftime(time_fmt)
    base_label = res.baseline_start.strftime(time_fmt)

    m1, m2, m3 = st.columns(3)
    m1.metric("Cleanest window", f"{win_start}–{win_end}")
    m2.metric("CO2 if shifted", f"{res.best_kg:.2f} kg")
    m3.metric(
        "CO2 avoided", f"{res.kg_avoided:.2f} kg",
        delta=f"-{res.pct_avoided:.0f}%", delta_color="inverse",
        help=HELP["co2_avoided_shift"],
    )

    if res.kg_avoided > 0.01:
        st.success(
            f"**Run it {win_start}–{win_end}** instead of {base_label} to avoid "
            f"**{res.kg_avoided:.2f} kg CO2** ({res.pct_avoided:.0f}% less) — "
            f"same energy, cleaner timing."
        )
    else:
        st.info(
            "The grid is fairly flat across this window, so timing barely changes "
            "emissions here. Try a different day (sunny spring/summer days swing most)."
        )

    st.markdown("**Green band = cleanest window • red dashed line = your usual start**")
    st.altair_chart(shift_window_chart(day, res), width="stretch")


def render_battery_tab(df: pd.DataFrame):
    st.subheader("Store clean energy, release it when the grid is dirty")
    st.caption(
        "A battery that charges during the cleanest hours (soaking up solar) and "
        "discharges during the dirtiest ones, displacing gas and oil generation."
    )

    st.write("**Battery presets**")
    pcols = st.columns(len(presets.PRESETS))
    for col, p in zip(pcols, presets.PRESETS):
        col.button(p.name, width="stretch", on_click=_apply_preset, args=(p.name,))

    s1, s2 = st.columns(2)
    with s1:
        st.slider("Power (MW)", 1, 1000, key="batt_power_mw", help=HELP["power"])
    with s2:
        st.slider("Capacity (MWh)", 1, 5000, key="batt_capacity_mwh", help=HELP["capacity"])

    power = float(st.session_state["batt_power_mw"])
    capacity = float(st.session_state["batt_capacity_mwh"])

    # --- Headline metrics: impact over all cached history ---------------
    hist_ci = df["carbon_lbs_per_mwh"].tolist()
    hist_res = cb.simulate_carbon(hist_ci, power, capacity, ROUND_TRIP_EFFICIENCY)
    tonnes = hist_res.net_co2_avoided_kg / 1000.0

    # Normalize to a per-year figure for an intuitive car-equivalent.
    span_days = max(
        (df["timestamp"].max() - df["timestamp"].min()).total_seconds() / 86400.0,
        1.0,
    )
    tonnes_per_year = tonnes * 365.0 / span_days

    m1, m2, m3 = st.columns(3)
    m1.metric("Net CO2 avoided (per year)", f"{tonnes_per_year:,.1f} tonnes", help=HELP["co2_avoided_batt"])
    m2.metric("Full cycles (per year)", f"{hist_res.cycles * 365.0 / span_days:,.0f}", help=HELP["cycles"])
    m3.metric("Round-trip efficiency", f"{ROUND_TRIP_EFFICIENCY*100:.0f}%")

    cars = tonnes_per_year * 1000 / 4600.0  # ~4.6 t CO2 per US car per year
    st.success(
        f"A **{power:,.0f} MW / {capacity:,.0f} MWh** carbon battery would avoid "
        f"about **{tonnes_per_year:,.1f} tonnes of CO2 per year** — roughly the "
        f"annual emissions of **{cars:,.0f} cars** — just by shifting *when* it "
        f"draws and delivers energy. (Based on {span_days/365.0:.1f} years of "
        f"ISO-NE data.)"
    )

    # --- Chart: show the battery actually working on a chosen day -------
    st.markdown("##### See it work — a single day")
    st.caption(
        "Green bars = charging (storing clean energy), orange bars = discharging "
        "(displacing dirty energy), green line = carbon intensity. "
        "Resize the battery above and watch the bars change."
    )
    day_choice = pick_day(df, "Day", key="batt_day")
    day = _day_slice(df, day_choice)
    if day.empty:
        st.warning("No data for that day.")
        return
    day_res = cb.simulate_carbon(
        day["carbon_lbs_per_mwh"].tolist(), power, capacity, ROUND_TRIP_EFFICIENCY
    )
    st.altair_chart(battery_dispatch_chart(day, day_res), width="stretch")


def _sunniest_day(df: pd.DataFrame) -> pd.Timestamp:
    """The highest-solar day — a nice default for demos."""
    by_day = df.assign(d=df["timestamp"].dt.normalize()).groupby("d")["solar_mw"].max()
    if by_day.empty:
        return pd.Timestamp(df["timestamp"].iloc[0]).normalize()
    return pd.Timestamp(by_day.idxmax()).normalize()


def pick_day(df: pd.DataFrame, label: str, key: str,
             default: pd.Timestamp | None = None,
             min_d: pd.Timestamp | None = None,
             max_d: pd.Timestamp | None = None,
             help_text: str | None = None) -> pd.Timestamp:
    """Calendar day picker constrained to a date range.

    Defaults the bounds to the dataset's own min/max; callers can widen the
    range (e.g. to include the forecast days). Dates outside [min_d, max_d] are
    greyed out by the calendar widget.
    """
    data_min = pd.Timestamp(df["timestamp"].min()).normalize()
    data_max = pd.Timestamp(df["timestamp"].max()).normalize()
    min_d = (min_d or data_min).normalize()
    max_d = (max_d or data_max).normalize()
    if default is None:
        default = _sunniest_day(df)
    default = min(max(default, min_d), max_d)
    chosen = st.date_input(
        label,
        value=default.date(),
        min_value=min_d.date(),
        max_value=max_d.date(),
        key=key,
        help=help_text or "Historical data covers 2025 through the latest cached day.",
    )
    return pd.Timestamp(chosen).normalize()


def _day_slice(df: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    day = pd.Timestamp(day).normalize()
    out = df[df["timestamp"].dt.normalize() == day]
    return out.sort_values("timestamp").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    _init_state()
    st.title("🌱 Clean Shift")
    st.caption(
        "Cut CO2 by shifting *when* energy is used or stored — using real "
        "ISO-NE data for the Boston area."
    )

    with st.expander("New here? Start with a 30-second tour", expanded=False):
        st.markdown(INTRO_MD)

    # --- Load data, fail gracefully -------------------------------------
    try:
        carbon_hist = _load_carbon_history()
    except (data_loader.DataFileNotFoundError, carbon.FuelMixNotFoundError) as e:
        st.error(str(e))
        st.info(
            "This app needs two data files in `data/`:\n"
            f"- Demand: `{data_loader.default_data_path().name}` (ISO-NE SMD hourly, NEMA sheet)\n"
            f"- Fuel mix: `{carbon.default_fuelmix_path().name}` "
            "(run `python fetch_fuelmix.py` to create it)"
        )
        st.stop()

    if carbon_hist.empty:
        st.warning("No carbon data found.")
        st.stop()

    # Live 48h forecast (cached ~1h; keyed on cache extent so it refreshes on rebuild).
    fc = _load_forecast(str(carbon_hist["timestamp"].max()))

    # Headline "why this matters": cleanest vs dirtiest hour of day.
    by_hour = carbon_hist.assign(h=carbon_hist["timestamp"].dt.hour).groupby("h")["carbon_lbs_per_mwh"].mean()
    cleanest_h, dirtiest_h = int(by_hour.idxmin()), int(by_hour.idxmax())
    gap = by_hour.max() - by_hour.min()
    st.info(
        f"**The grid's daily rhythm (historical average):** cleanest around "
        f"**{cleanest_h:02d}:00** ({by_hour.min():.0f} lbs CO2/MWh), dirtiest around "
        f"**{dirtiest_h:02d}:00** ({by_hour.max():.0f}). That {gap:.0f}-point swing "
        f"is the opportunity this tool helps you capture."
    )

    tab1, tab2, tab3 = st.tabs([
        "⚡ Load-shift advisor",
        "🔋 Carbon battery",
        "📈 The clean/dirty day",
    ])
    with tab1:
        render_loadshift_tab(carbon_hist, fc)
    with tab2:
        render_battery_tab(carbon_hist)
    with tab3:
        render_duckcurve_tab(carbon_hist)

    with st.expander("Assumptions & methodology"):
        st.markdown(
            f"""
- **Demand:** ISO-NE SMD hourly, **NEMA** zone (Boston / Northeast MA), 2025.
- **Fuel mix (historical):** ISO-NE generation by fuel type, fetched via the
  `gridstatus` library and cached hourly from Jan 2025 to the latest day.
- **Carbon intensity:** estimated from the fuel mix using standard emission
  factors (coal ~2,100, oil ~1,700, natural gas ~900 lbs CO2/MWh; nuclear,
  hydro, solar, wind ~0). This is an **average-mix** estimate, not a marginal
  rate (a true hourly marginal signal isn't freely available for ISO-NE).
- **48-hour forecast:** built from ISO-NE's live demand, solar and wind
  forecasts via grid-dispatch logic (demand minus forecast clean supply is met
  by fossil plants). An estimate, not an official projection; limited to 48h by
  the demand-forecast horizon. There may be a 1-2 day gap between the last
  historical day and the forecast window — those dates are greyed out.
- **Load-shift advisor:** finds the contiguous window of the chosen length with
  the lowest average carbon intensity, and compares it to your usual start time.
  Defaults to the live forecast (actionable); can also explore past days.
- **Carbon battery:** charges during the cleanest ~third of hours and discharges
  during the dirtiest ~third, bounded by power, capacity and a
  {ROUND_TRIP_EFFICIENCY*100:.0f}% round-trip efficiency. "Net CO2 avoided" is
  dirty generation displaced minus the CO2 of the energy charged.
- **Car-equivalent:** ~4.6 tonnes CO2 per US passenger car per year (rough EPA
  figure), for intuition only.
            """
        )


def render_duckcurve_tab(df: pd.DataFrame):
    st.subheader("Why timing matters: solar vs. carbon on one day")
    st.caption(
        "When solar rises (orange), carbon intensity (green) falls. When the sun "
        "sets and gas plants ramp up for the evening, carbon climbs."
    )
    day_choice = pick_day(df, "Day", key="duck_day")
    day = _day_slice(df, day_choice)
    st.altair_chart(solar_carbon_chart(day), width="stretch")
    st.caption("Orange area = solar generation • green line = grid carbon intensity. "
               "This inverse relationship is the whole premise of Clean Shift.")


if __name__ == "__main__":
    main()
