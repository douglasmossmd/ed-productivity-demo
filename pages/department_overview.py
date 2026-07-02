import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.helpers import (
    load_data, scatter_chart, bar_chart,
    QUADRANT_COLORS, QUADRANT_LABELS,
    C_PRIMARY, C_ORANGE, period_selector,
    METRIC_TOOLTIPS, tooltip_icon, inject_tooltip_css,
)


inject_tooltip_css()

# ── Auth gate ─────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.error("Please log in from the home page.")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    location = st.selectbox("**Location**", ["CCD", "NWI"], key="dept_location")
    st.divider()
    period_label, start_period, end_period = period_selector(location=location)

# ── Load data ─────────────────────────────────────────────────────────────────
df, has_shifts = load_data(start_period, end_period, location=location)
throughput_col  = df["throughput_col"].iloc[0]

# ── ShiftAdmin status banner ──────────────────────────────────────────────────
if not has_shifts:
    err = st.session_state.get("_sa_error", "")
    tip = f" ({err[:120]})" if err else " Add SA_USERNAME and SA_PASSWORD to .env to enable per-hour metrics."
    st.info(
        f"**ShiftAdmin not connected** — showing profee cube metrics only (wRVU/encounter, encounters/month).{tip}",
        icon="ℹ️"
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:{C_PRIMARY};padding:18px 24px;border-radius:10px;margin-bottom:24px;">
  <span style="color:white;font-size:22px;font-weight:600;">Department Overview</span>
  <span style="color:rgba(255,255,255,0.7);font-size:14px;float:right;margin-top:4px;">
    {period_label} &nbsp;·&nbsp; Center for Care and Discovery
  </span>
</div>
""", unsafe_allow_html=True)

# ── Summary stat cards ────────────────────────────────────────────────────────
if has_shifts:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    cols_data = [
        (c1, "Total Encounters",        f"{int(df['encounter_count'].sum()):,}"),
        (c2, "Total wRVUs",             f"{df['total_wrvu'].sum():,.0f}"),
        (c3, "Total Hours",             f"{df['hours_worked'].sum():,.0f}"),
        (c4, "Median wRVU / Hour",      f"{df['wrvu_per_hour_median'].iloc[0]:.2f}"),
        (c5, "Median Encounters / Hour",f"{df['encounters_per_hour_median'].iloc[0]:.2f}"),
        (c6, "Median wRVU / Encounter", f"{df['wrvu_per_encounter_median'].iloc[0]:.2f}"),
    ]
else:
    c1, c2, c3, c4 = st.columns(4)
    cols_data = [
        (c1, "Total Encounters",          f"{int(df['encounter_count'].sum()):,}"),
        (c2, "Total wRVUs",               f"{df['total_wrvu'].sum():,.0f}"),
        (c3, "Median Encounters / Month", f"{df['encounters_per_month_median'].iloc[0]:.1f}"),
        (c4, "Median wRVU / Encounter",   f"{df['wrvu_per_encounter_median'].iloc[0]:.2f}"),
    ]

for col, label, value in cols_data:
    tip = METRIC_TOOLTIPS.get(label, "")
    col.metric(label, value, help=tip)

st.divider()

# ── Quadrant summary ──────────────────────────────────────────────────────────
st.subheader("Quadrant Distribution")
x_axis_name = "Encounters/Hour" if has_shifts else "Encounters/Month"
st.caption(
    f"Providers split by {x_axis_name} (throughput) vs wRVU/Encounter (complexity). "
    "Dividing lines = group medians."
)
q_counts = df["quadrant"].value_counts().sort_index()
qcols = st.columns(4)
for q, col in zip([1,2,3,4], qcols):
    count = int(q_counts.get(q, 0))
    pct   = round(count / len(df) * 100)
    color = QUADRANT_COLORS[q]
    col.markdown(f"""
    <div style="border-left:4px solid {color};padding:10px 14px;
                background:#fafaf9;border-radius:0 8px 8px 0;margin-bottom:4px;">
      <div style="font-size:11px;color:#888;font-weight:500;text-transform:uppercase;
                  letter-spacing:.05em;">Q{q}</div>
      <div style="font-size:24px;font-weight:700;color:{color};">{count}</div>
      <div style="font-size:11px;color:#666;">{QUADRANT_LABELS[q]}</div>
      <div style="font-size:11px;color:#aaa;">{pct}% of providers</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
left, right = st.columns([1.2, 1])
with left:
    st.subheader("Provider Throughput vs. Encounter Complexity")
    st.caption("Dashed lines = group medians. Click a dot to jump to that provider's profile.")
    scatter_event = st.plotly_chart(
        scatter_chart(df), use_container_width=True,
        key="home_scatter", on_select="rerun", selection_mode="points"
    )
    points = getattr(getattr(scatter_event, "selection", None), "points", [])
    if points:
        clicked = points[0].get("customdata", None)
        if clicked and clicked in df["provider_name"].values:
            st.session_state["jump_to_provider"] = clicked
            st.switch_page("pages/1_Provider_Explorer.py")

with right:
    st.subheader("wRVU / Encounter — All Providers")
    st.caption("Ranked lowest to highest. Click a bar to jump to that provider's profile.")
    bar_event = st.plotly_chart(
        bar_chart(df), use_container_width=True,
        key="home_bar", on_select="rerun", selection_mode="points"
    )
    bar_points = getattr(getattr(bar_event, "selection", None), "points", [])
    if bar_points:
        clicked_bar = bar_points[0].get("y", None)
        if clicked_bar and clicked_bar in df["provider_name"].values:
            st.session_state["jump_to_provider"] = clicked_bar
            st.switch_page("pages/1_Provider_Explorer.py")
