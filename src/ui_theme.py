"""Risograph eco-poster theme for Clean Shift.

A handcrafted, screen-printed look: warm recycled-paper canvas, a few flat spot
colours (forest green = clean, clay = dirty, marigold accent), bold condensed
display type, thick ink rules, and subtle print texture / offset. The opposite
of the generic dark-glass dashboard aesthetic.

All presentation lives here so app.py stays focused on logic.
"""

from __future__ import annotations

import altair as alt
import streamlit as st

# ---- Risograph spot-colour palette -------------------------------------
PAPER = "#f4ead6"       # warm recycled paper
PAPER_2 = "#efe2c9"     # slightly darker panel paper
INK = "#2b2a26"         # near-black ink
GREEN = "#2f6b4f"       # forest green (clean)
GREEN_BRIGHT = "#3f9b6e"
CLAY = "#d2603a"        # terracotta / clay (dirty)
MARIGOLD = "#e9b949"    # accent pop (sun)
MUTED = "#7a7360"       # muted ink for secondary text


_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

/* ---------- Paper canvas with print grain ---------- */
.stApp {
  background-color: #f4ead6;
  background-image:
    radial-gradient(#00000008 1px, transparent 1px),
    radial-gradient(#00000005 1px, transparent 1px);
  background-size: 7px 7px, 13px 13px;
  background-position: 0 0, 3px 4px;
  color: #2b2a26;
}
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1080px; }

/* Body + headings type */
html, body, [class*="css"], p, li, label, .stMarkdown { font-family:'Space Grotesk', sans-serif; color:#2b2a26; }
h1, h2, h3, h4 { font-family:'Fraunces', serif; color:#23402f; letter-spacing:-0.01em; }

/* ---------- Poster hero ---------- */
.cs-poster {
  position: relative;
  border: 3px solid #2b2a26;
  border-radius: 4px;
  background: #2f6b4f;
  color: #f4ead6;
  padding: 26px 30px 22px 30px;
  margin: 2px 0 20px 0;
  box-shadow: 10px 10px 0 #2b2a26;      /* hard offset = screen-print block */
  overflow: hidden;
}
/* faint printed sun rays in the corner */
.cs-poster::before {
  content:""; position:absolute; top:-70px; right:-70px; width:220px; height:220px;
  border-radius:50%;
  background: repeating-conic-gradient(#e9b949 0deg 9deg, transparent 9deg 18deg);
  opacity:0.28;
  animation: cs-spin 60s linear infinite;
}
@keyframes cs-spin { to { transform: rotate(360deg); } }

.cs-kicker {
  font-family:'Space Grotesk'; font-weight:700; font-size:.72rem; letter-spacing:.28em;
  text-transform:uppercase; color:#e9b949; margin-bottom:6px;
}
.cs-poster h1 {
  font-family:'Archivo Black', sans-serif; color:#f4ead6;
  font-size: 3.1rem; line-height:0.96; margin:0; letter-spacing:-0.02em; text-transform:uppercase;
}
.cs-poster h1 .sun { color:#e9b949; }
.cs-poster .cs-sub { font-family:'Fraunces',serif; font-size:1.18rem; font-style:italic;
  margin-top:14px; max-width:660px; color:#eadfc8; line-height:1.4; }
.cs-tags { margin-top:16px; display:flex; gap:0; flex-wrap:wrap; }
.cs-tag {
  font-family:'Space Grotesk'; font-weight:600; font-size:.74rem; letter-spacing:.04em;
  padding:4px 11px; border:2px solid #f4ead6; color:#f4ead6;
  margin:0 -2px -2px 0;
}
.cs-tag.on { background:#e9b949; color:#2b2a26; border-color:#2b2a26; }

/* ---------- Rhythm "stamp" cards ---------- */
.cs-stamp {
  border:3px solid #2b2a26; border-radius:4px; padding:14px 16px;
  box-shadow:5px 5px 0 #2b2a26; background:#efe2c9;
}
.cs-stamp.clean { background:#e4efe4; }
.cs-stamp.dirty { background:#f6e3d8; }
.cs-stamp .lbl { font-family:'Space Grotesk'; font-weight:700; font-size:.72rem;
  letter-spacing:.14em; text-transform:uppercase; }
.cs-stamp.clean .lbl { color:#2f6b4f; }
.cs-stamp.dirty .lbl { color:#c04f2b; }
.cs-stamp .big { font-family:'Archivo Black',sans-serif; font-size:2.1rem; color:#23402f; line-height:1; margin-top:4px; }
.cs-stamp .unit { font-family:'Fraunces',serif; font-style:italic; color:#7a7360; font-size:.92rem; }
.cs-swing { font-family:'Fraunces',serif; font-style:italic; color:#7a7360; margin:8px 2px 14px; }
.cs-swing b { font-family:'Archivo Black'; font-style:normal; color:#d2603a; }

/* little circled "?" help badge in a stamp's bottom-right corner */
.cs-help {
  position:absolute; right:9px; bottom:9px;
  width:19px; height:19px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-family:'Space Grotesk'; font-weight:700; font-size:.72rem;
  color:#2b2a26; background:transparent;
  border:2px solid #2b2a26; cursor:help; user-select:none;
  opacity:0.45; transition:opacity .12s ease, transform .12s ease;
}
.cs-help:hover { opacity:1; transform:scale(1.12); }

/* on-theme (risograph) tooltip bubble that matches the rest of the app */
.cs-help .cs-tip {
  position:absolute; bottom:135%; right:-6px; width:240px;
  background:#f4ead6; color:#2b2a26;
  border:2.5px solid #2b2a26; border-radius:4px;
  box-shadow:4px 4px 0 #2b2a26;
  padding:10px 12px; font-family:'Space Grotesk',sans-serif; font-weight:500;
  font-size:.78rem; line-height:1.35; text-align:left;
  opacity:0; visibility:hidden; transform:translateY(4px);
  transition:opacity .14s ease, transform .14s ease, visibility .14s;
  z-index:50; pointer-events:none;
}
/* little pointer notch */
.cs-help .cs-tip::after {
  content:""; position:absolute; top:100%; right:10px;
  border:7px solid transparent; border-top-color:#2b2a26;
}
.cs-help:hover .cs-tip { opacity:1; visibility:visible; transform:translateY(0); }

/* ---------- Metric chips ---------- */
/* Make every metric card in a row the same height (match the tallest). */
[data-testid="stHorizontalBlock"] { align-items:stretch; }
[data-testid="stHorizontalBlock"] [data-testid="stColumn"] { display:flex; }
[data-testid="stHorizontalBlock"] [data-testid="stColumn"] > div,
[data-testid="stColumn"] [data-testid="stVerticalBlock"] { width:100%; }
[data-testid="stHorizontalBlock"] [data-testid="stColumn"] [data-testid="stMetric"] {
  flex:1 1 auto;
}

[data-testid="stMetric"] {
  background:#efe2c9; border:2.5px solid #2b2a26; border-radius:4px;
  padding:12px 14px 10px; box-shadow:4px 4px 0 #2b2a26;
  transition: transform .12s ease, box-shadow .12s ease;
  overflow:visible;
  display:flex; flex-direction:column; justify-content:flex-start;
  min-height:118px;
}
[data-testid="stMetric"]:hover { transform:translate(-2px,-2px); box-shadow:6px 6px 0 #2b2a26; }
[data-testid="stMetricValue"] {
  font-family:'Archivo Black',sans-serif !important; color:#23402f;
  font-size:1.5rem !important; line-height:1.15 !important;
  white-space:normal !important; overflow:visible !important;
  text-overflow:clip !important;
}
/* let the value container grow instead of truncating with "..." */
[data-testid="stMetricValue"] > div { overflow:visible !important; white-space:normal !important; }
[data-testid="stMetricLabel"] { color:#7a7360; font-weight:600; text-transform:uppercase; letter-spacing:.04em; font-size:.72rem; }
[data-testid="stMetricLabel"] * { white-space:normal !important; }

/* ---------- Tabs: printed index tabs ---------- */
.stTabs [data-baseweb="tab-list"] { gap:10px; border-bottom:3px solid #2b2a26; }
.stTabs [data-baseweb="tab"] {
  background:#efe2c9; border:2.5px solid #2b2a26; border-bottom:none;
  border-radius:8px 8px 0 0;
  padding:10px 34px !important; color:#2b2a26; font-weight:600;
  margin-bottom:-3px; font-family:'Space Grotesk'; white-space:nowrap;
}
/* Streamlit nests the label in an inner flex box that carries its own padding;
   force horizontal breathing room there too so the highlight doesn't hug text. */
.stTabs [data-baseweb="tab"] > * { padding-left:6px !important; padding-right:6px !important; }
.stTabs [data-baseweb="tab"] [data-testid="stMarkdownContainer"],
.stTabs [data-baseweb="tab"] p { margin:0; }
.stTabs [data-baseweb="tab"] * { color:#2b2a26 !important; }
.stTabs [aria-selected="true"] { background:#2f6b4f !important; }
/* cream text (not black) on the green active tab */
.stTabs [aria-selected="true"], .stTabs [aria-selected="true"] * { color:#f4ead6 !important; }

/* ---------- Buttons: stamped ---------- */
.stButton > button {
  font-family:'Space Grotesk'; font-weight:700;
  background:#e9b949; color:#2b2a26; border:2.5px solid #2b2a26; border-radius:4px;
  box-shadow:3px 3px 0 #2b2a26; transition: all .1s ease;
  white-space:normal; line-height:1.15; min-height:40px; padding:6px 8px;
}
.stButton > button p { white-space:normal; overflow-wrap:anywhere; }
.stButton > button:hover { transform:translate(-1px,-1px); box-shadow:4px 4px 0 #2b2a26; background:#f0c863; }
.stButton > button:active { transform:translate(2px,2px); box-shadow:0 0 0 #2b2a26; }
/* Selected preset = primary button: keep the EXACT same marigold fill as the
   others; the ONLY change is a thicker, darker (double) border. Streamlit marks
   primary buttons differently across versions (kind="primary" on the <button>
   and/or data-testid="stBaseButton-primary"), and colours them via its own
   theme primaryColor. We override ALL of those variants + states with
   !important so the green can't bleed through. */
.stButton button[kind="primary"],
.stButton button[kind="primary"]:hover,
.stButton button[kind="primary"]:focus,
.stButton button[kind="primary"]:focus:not(:active),
.stButton button[kind="primary"]:active,
.stButton [data-testid="stBaseButton-primary"],
.stButton [data-testid="stBaseButton-primary"]:hover,
.stButton [data-testid="stBaseButton-primary"]:focus,
.stButton [data-testid="stBaseButton-primary"]:active {
  background-color:#e9b949 !important;
  background:#e9b949 !important;
  color:#2b2a26 !important;
  border:4px double #2b2a26 !important;
  box-shadow:inset 2px 2px 0 rgba(43,42,38,0.18), 3px 3px 0 #2b2a26 !important;
}
.stButton button[kind="primary"] *,
.stButton [data-testid="stBaseButton-primary"] * { color:#2b2a26 !important; }

/* ---------- Alerts: hand-ruled notes ---------- */
[data-testid="stAlert"] {
  border:2.5px solid #2b2a26; border-radius:4px; box-shadow:4px 4px 0 rgba(43,42,38,0.5);
  background:#efe2c9;
}

/* Inputs / sliders */
.stSlider [data-baseweb="slider"] div[role="slider"] { border:2px solid #2b2a26; }

/* Text / number / date inputs: distinct paper panel + ink border so they don't
   blend into cards or the expander background. Target the testid wrappers and
   force every nested container to the panel colour (DaseWeb class names vary by
   Streamlit version, so we hit all descendants). */
[data-testid="stDateInput"] > div,
[data-testid="stDateInput"] > div > div,
[data-testid="stNumberInput"] > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stTextInput"] > div,
[data-testid="stTextInput"] > div > div,
[data-testid="stSelectbox"] > div,
[data-testid="stSelectbox"] > div > div {
  background:#fbf6ea !important;
  border-color:#2b2a26 !important;
}
[data-testid="stDateInput"] > div > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stTextInput"] > div > div,
[data-testid="stSelectbox"] > div > div {
  border:2px solid #2b2a26 !important;
  border-radius:4px !important;
  box-shadow:2px 2px 0 rgba(43,42,38,0.4);
}
[data-testid="stDateInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input {
  background:#fbf6ea !important; color:#2b2a26 !important;
}
[data-testid="stExpander"] { border:2.5px solid #2b2a26; border-radius:4px; background:#efe2c9; box-shadow:4px 4px 0 rgba(43,42,38,0.35); }

/* section headings get a little underline rule */
.main h3 { border-bottom:3px solid #2b2a26; display:inline-block; padding-bottom:2px; }

/* entrance */
.main .block-container > div { animation: cs-rise .45s cubic-bezier(.2,.7,.3,1) both; }
@keyframes cs-rise { from{opacity:0; transform:translateY(10px)} to{opacity:1; transform:none} }
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def hero():
    st.markdown(
        """
        <div class="cs-poster">
          <div class="cs-kicker">Boston · ISO-NE grid · carbon-aware</div>
          <h1>CLEAN<span class="sun">·</span>SHIFT</h1>
          <div class="cs-sub">
            The grid is cleanest when the sun is up and dirtiest when the peaker
            plants roar to life. Shift <em>when</em> you use or store power — and
            watch the carbon fall.
          </div>
          <div class="cs-tags">
            <span class="cs-tag on">Real data</span>
            <span class="cs-tag">Load-shift advisor</span>
            <span class="cs-tag">Carbon battery</span>
            <span class="cs-tag">48-hr forecast</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def rhythm_banner(cleanest_h: int, cleanest_v: float, dirtiest_h: int,
                  dirtiest_v: float, gap: float, data_start_year: int = 2025):
    tip = (
        f"Average across every hour in the data (hourly ISO-NE fuel mix, "
        f"{data_start_year} to today). We bucket all days by hour-of-day and "
        f"take the mean carbon intensity — so this is a typical day, not right now."
    )
    st.markdown(
        f"""
        <div style="display:flex; gap:16px; flex-wrap:wrap; align-items:stretch; margin:4px 0 2px;">
          <div class="cs-stamp clean" style="flex:1; min-width:210px; position:relative;">
            <div class="lbl">☀ Cleanest hour</div>
            <div class="big">{cleanest_h:02d}:00</div>
            <div class="unit">{cleanest_v:.0f} kg CO₂ / MWh</div>
            <span class="cs-help">?<span class="cs-tip">{tip}</span></span>
          </div>
          <div class="cs-stamp dirty" style="flex:1; min-width:210px; position:relative;">
            <div class="lbl">⚑ Dirtiest hour</div>
            <div class="big">{dirtiest_h:02d}:00</div>
            <div class="unit">{dirtiest_v:.0f} kg CO₂ / MWh</div>
            <span class="cs-help">?<span class="cs-tip">{tip}</span></span>
          </div>
        </div>
        <div class="cs-swing">A <b>{gap:.0f}-point</b> daily swing between clean and dirty —
        that gap is the opportunity Clean Shift helps you capture.
        <span style="font-style:normal; color:#9a917c;">(average day, {data_start_year}–today)</span></div>
        """,
        unsafe_allow_html=True,
    )


def source_caption(text: str):
    """Tiny, muted data-attribution line to sit directly under a chart."""
    st.markdown(
        f"<div style='font-family:\"Space Grotesk\",sans-serif; font-size:0.7rem; "
        f"color:#9a917c; letter-spacing:.01em; margin:-4px 2px 10px;'>"
        f"{text}</div>",
        unsafe_allow_html=True,
    )


def note(icon: str, html_msg: str):
    """A compact on-theme inline note (paper strip with an ink left-rule)."""
    st.markdown(
        f"""
        <div style="display:flex; gap:10px; align-items:flex-start;
             background:#efe2c9; border:2px solid #2b2a26; border-left:6px solid #d2603a;
             border-radius:4px; box-shadow:3px 3px 0 rgba(43,42,38,0.4);
             padding:10px 14px; margin:4px 0 14px;">
          <div style="font-size:1.1rem; line-height:1.4;">{icon}</div>
          <div style="font-family:'Space Grotesk'; font-size:.9rem; line-height:1.45; color:#2b2a26;">
            {_md_bold(html_msg)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _md_bold(text: str) -> str:
    """Tiny markdown-bold -> <b> converter for note()."""
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def dispatch_summary_card(day_label: str, charge_windows: str,
                          discharge_windows: str, source_phrase: str,
                          net_str: str):
    """A paper card summarizing the day's dispatch, with Charge in green and
    Discharge in clay to match the chart's shaded bands."""
    st.markdown(
        f"""
        <div style="border:2.5px solid #2b2a26; border-radius:4px; background:#efe2c9;
             box-shadow:4px 4px 0 rgba(43,42,38,0.45); padding:16px 18px; margin:6px 0 10px;">
          <div style="font-family:'Fraunces',serif; font-weight:600; font-size:1.05rem; margin-bottom:8px;">
            On {day_label}, this battery would:
          </div>
          <div style="margin:6px 0; line-height:1.5;">
            🔋 <b style="color:#2f6b4f;">Charge</b>
            <span style="color:#5c5647;">(store clean energy)</span> during
            <b>{charge_windows}</b> — the cleanest hours.{source_phrase}
          </div>
          <div style="margin:6px 0; line-height:1.5;">
            ⚡ <b style="color:#c04f2b;">Discharge</b>
            <span style="color:#5c5647;">(push stored energy to the grid)</span> during
            <b>{discharge_windows}</b> — the dirtiest hours, displacing gas and oil.
          </div>
          <div style="margin-top:12px; padding-top:10px; border-top:2px dashed rgba(43,42,38,0.3);
               font-family:'Space Grotesk';">
            Net effect that day:
            <b style="font-family:'Archivo Black'; color:#23402f;">{net_str} of CO₂ avoided.</b>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- Altair: ink-on-paper figure style ---------------------------
def _altair_theme():
    axis = {
        "labelColor": "#2b2a26",
        "titleColor": "#23402f",
        "gridColor": "rgba(43,42,38,0.12)",
        "domainColor": "#2b2a26",
        "domainWidth": 1.5,
        "tickColor": "#2b2a26",
        "labelFont": "Space Grotesk",
        "titleFont": "Fraunces",
        "titleFontSize": 13,
        "titleFontWeight": 600,
    }
    return {
        "config": {
            "background": "transparent",
            "view": {"stroke": "transparent"},
            "axis": axis,
            "axisX": {**axis, "grid": False},
            "legend": {
                "labelColor": "#2b2a26", "titleColor": "#23402f",
                "labelFont": "Space Grotesk", "titleFont": "Fraunces",
            },
            "title": {"color": "#23402f", "font": "Fraunces", "fontSize": 15},
        }
    }


def register_altair_theme():
    try:
        alt.theme.register("cleanshift", _altair_theme)
        alt.theme.enable("cleanshift")
    except Exception:
        try:
            alt.themes.register("cleanshift", _altair_theme)
            alt.themes.enable("cleanshift")
        except Exception:
            pass
