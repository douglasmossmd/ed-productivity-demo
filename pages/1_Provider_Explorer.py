import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.helpers import (
    load_data, scatter_chart, bar_chart,
    QUADRANT_COLORS, QUADRANT_LABELS,
    C_PRIMARY, C_GRAY, C_BLUE, C_AMBER,
    period_selector, tooltip_icon, METRIC_TOOLTIPS,
    inject_tooltip_css,
    generate_shift_breakdown,
)

if not st.session_state.get("authenticated"):
    st.warning("Please sign in from the Home page.")
    st.stop()

inject_tooltip_css()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.divider()
    location = st.selectbox("**Location**", ["CCD", "NWI"], key="explorer_location")
    st.divider()
    period_label, start_period, end_period = period_selector(location=location)
    st.divider()
    st.markdown("**Filters**")
    q_options = ["All quadrants"] + [f"Q{q} — {QUADRANT_LABELS[q]}" for q in [1,2,3,4]]
    q_sel       = st.selectbox("Quadrant", q_options)
    rvu_range   = st.slider("wRVU / Hour range",  0.0, 10.0, (0.0, 10.0), step=0.1)
    shift_range = st.slider("Shifts worked",       0,   120,  (0, 120))


# ── Load data ─────────────────────────────────────────────────────────────────
df, has_shifts = load_data(start_period, end_period, location=location)

# ── Resolve provider navigation ───────────────────────────────────────────────
jump_name = st.session_state.pop("jump_to_provider", None)
if jump_name and jump_name in df["provider_name"].values:
    st.session_state["selected_provider_name"] = jump_name

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = df.copy()
if q_sel != "All quadrants":
    filtered = filtered[filtered["quadrant"] == int(q_sel[1])]

if has_shifts and "wrvu_per_hour" in filtered.columns:
    filtered = filtered[
        (filtered["wrvu_per_hour"].fillna(0)  >= rvu_range[0])  &
        (filtered["wrvu_per_hour"].fillna(0)  <= rvu_range[1])  &
        (filtered["shifts_worked"].fillna(0)  >= shift_range[0])&
        (filtered["shifts_worked"].fillna(0)  <= shift_range[1])
    ]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:{C_PRIMARY};padding:16px 24px;border-radius:10px;margin-bottom:20px;">
  <span style="color:white;font-size:22px;font-weight:600;">Provider Explorer</span>
  <span style="color:rgba(255,255,255,0.7);font-size:14px;float:right;margin-top:4px;">
    {period_label} &nbsp;·&nbsp; Showing {len(filtered)} of {len(df)} providers
  </span>
</div>
""", unsafe_allow_html=True)

# ── Resolve selected provider ─────────────────────────────────────────────────
stored_name = st.session_state.get("selected_provider_name", None)
if stored_name not in df["provider_name"].values:
    stored_name = None

# ── Always-visible charts — click to select / switch provider ─────────────────
st.caption("Click a dot or bar to view that provider's profile below. Click another to switch.")
c1, c2 = st.columns([1.2, 1])
with c1:
    bar_event = st.plotly_chart(
        bar_chart(filtered, highlight_name=stored_name),
        use_container_width=True,
        key="filt_bar", on_select="rerun", selection_mode="points",
    )
    bar_pts = getattr(getattr(bar_event, "selection", None), "points", [])
    if bar_pts:
        clicked = bar_pts[0].get("y", None)
        if clicked and clicked in df["provider_name"].values and clicked != stored_name:
            st.session_state["selected_provider_name"] = clicked
            st.rerun()
with c2:
    scatter_event = st.plotly_chart(
        scatter_chart(filtered, highlight_name=stored_name),
        use_container_width=True,
        key="filt_scat", on_select="rerun", selection_mode="points",
    )
    scat_pts = getattr(getattr(scatter_event, "selection", None), "points", [])
    if scat_pts:
        clicked = scat_pts[0].get("customdata", None)
        if clicked and clicked in df["provider_name"].values and clicked != stored_name:
            st.session_state["selected_provider_name"] = clicked
            st.rerun()

# ── Provider table (collapsed by default once a provider is selected) ──────────
with st.expander("Browse all providers" if stored_name else "Browse all providers",
                 expanded=(stored_name is None)):
    if has_shifts and "wrvu_per_hour" in filtered.columns and filtered["wrvu_per_hour"].notna().any():
        wanted = [
            ("provider_name",              "Provider"),
            ("quadrant_label",             "Quadrant"),
            ("wrvu_per_hour",              "wRVU/hr"),
            ("wrvu_per_hour_quartile",     "wRVU Tier"),
            ("encounters_per_hour",        "Enc/hr"),
            ("wrvu_per_encounter",         "wRVU/enc"),
            ("shifts_worked",              "Shifts"),
            ("encounter_count",            "Encounters"),
            ("total_wrvu",                 "Total wRVU"),
        ]
    else:
        wanted = [
            ("provider_name",              "Provider"),
            ("quadrant_label",             "Quadrant"),
            ("wrvu_per_encounter",         "wRVU/enc"),
            ("encounters_per_month",       "Enc/Month"),
            ("encounter_count",            "Encounters"),
            ("total_wrvu",                 "Total wRVU"),
        ]
    present = [(c, lbl) for c, lbl in wanted if c in filtered.columns]
    cols_sel, col_labels = zip(*present)
    display = filtered[list(cols_sel)].copy()
    display.columns = list(col_labels)
    for col in ["wRVU/hr","Enc/hr","wRVU/enc","Enc/Month"]:
        if col in display.columns:
            display[col] = display[col].round(2)
    display["Total wRVU"] = display["Total wRVU"].round(0).astype(int)
    sel = st.dataframe(
        display, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", height=250,
    )
    selected_rows = sel.selection.rows if hasattr(sel, "selection") else []
    if selected_rows:
        picked = filtered.iloc[selected_rows[0]]["provider_name"]
        if picked != stored_name:
            st.session_state["selected_provider_name"] = picked
            st.rerun()

# ── No selection yet ──────────────────────────────────────────────────────────
if not stored_name:
    st.info("Click a provider in the charts above to view their full profile here.")
    st.stop()

# ── Provider profile ──────────────────────────────────────────────────────────
prov_row  = df[df["provider_name"] == stored_name].iloc[0]
name      = prov_row["provider_name"]
q         = int(prov_row["quadrant"])
color     = QUADRANT_COLORS[q]
firstname = name.split(",")[1].strip() if "," in name else name

st.divider()

badge_bg = {1:"#EAF3DE", 2:"#E6F1FB", 3:"#FAEEDA", 4:"#FAECE7"}
st.markdown(f"""
<div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
  <span style="font-size:22px;font-weight:700;color:#2C2C2A;">{name}</span>
  <span style="background:{badge_bg[q]};color:{color};font-size:11px;font-weight:700;
               padding:4px 12px;border-radius:14px;border:1px solid {color};">
    Q{q} — {QUADRANT_LABELS[q]}
  </span>
</div>
<div style="font-size:12px;color:#888;margin-bottom:16px;">{period_label}</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Summary stat cards
# ══════════════════════════════════════════════════════════════════════════════
def mini_stat(col, label, value, tip_key=None):
    tip = tooltip_icon(tip_key or label)
    col.markdown(f"""
    <div style="background:#F1EFE8;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#888;margin-bottom:2px;">{label}{tip}</div>
      <div style="font-size:18px;font-weight:700;color:#2C2C2A;">{value}</div>
    </div>""", unsafe_allow_html=True)

s1, s2, s3, s4, s5 = st.columns(5)
mini_stat(s1, "Shifts Worked",   int(prov_row.get("shifts_worked", 0)),   "Shifts Worked")
mini_stat(s2, "Hours Worked",    f"{prov_row.get('hours_worked', 0):.0f}", "Hours Worked")
mini_stat(s3, "Encounters",      f"{int(prov_row['encounter_count']):,}",  "Encounters")
mini_stat(s4, "Total wRVUs",     f"{prov_row['total_wrvu']:,.0f}",         "Total wRVUs (provider)")
hrs_per_shift = prov_row.get("hours_worked", 0) / max(prov_row.get("shifts_worked", 1), 1)
mini_stat(s5, "Avg hrs / Shift", f"{hrs_per_shift:.1f}",                   "Avg hrs / Shift")

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Performance metric cards
# ══════════════════════════════════════════════════════════════════════════════
def metric_card(col, title, value, p25, med, p75, tip_key=None):
    tag, tcolor = (
        ("Above 75th",  "#3B6D11") if value >= p75 else
        ("Above median","#800000") if value >= med else
        ("Below median","#854F0B") if value >= p25 else
        ("Below 25th",  "#993C1D")
    )
    bg = ("#EAF3DE" if tcolor=="#3B6D11" else "#FFF0F0" if tcolor=="#800000"
          else "#FAEEDA" if tcolor=="#854F0B" else "#FAECE7")
    tip = tooltip_icon(tip_key or title, size=12)
    col.markdown(f"""
    <div style="background:#F1EFE8;border-radius:10px;padding:16px;text-align:center;">
      <div style="font-size:11px;color:#888;margin-bottom:4px;">{title}{tip}</div>
      <div style="font-size:28px;font-weight:700;color:#2C2C2A;">{value:.2f}</div>
      <div style="font-size:10px;color:#B4B2A9;margin:6px 0;">
        P25: {p25:.2f} &nbsp;·&nbsp; Median: {med:.2f} &nbsp;·&nbsp; P75: {p75:.2f}
      </div>
      <span style="background:{bg};color:{tcolor};font-size:10px;font-weight:600;
                   padding:3px 10px;border-radius:12px;">{tag}</span>
    </div>""", unsafe_allow_html=True)

m1, m2, m3 = st.columns(3)
metric_card(m1, "wRVUs per Hour",
            prov_row.get("wrvu_per_hour", 0),
            prov_row.get("wrvu_per_hour_p25", 0), prov_row.get("wrvu_per_hour_median", 0), prov_row.get("wrvu_per_hour_p75", 0),
            "wRVUs per Hour")
metric_card(m2, "Encounters per Hour",
            prov_row.get("encounters_per_hour", 0),
            prov_row.get("encounters_per_hour_p25", 0), prov_row.get("encounters_per_hour_median", 0), prov_row.get("encounters_per_hour_p75", 0),
            "Encounters per Hour")
metric_card(m3, "wRVUs per Encounter",
            prov_row["wrvu_per_encounter"],
            prov_row["wrvu_per_encounter_p25"], prov_row["wrvu_per_encounter_median"], prov_row["wrvu_per_encounter_p75"],
            "wRVUs per Encounter")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Shift activity breakdown
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("#### Shift Activity")

shift_df, opu, spu = generate_shift_breakdown(prov_row)

total_s   = int(prov_row.get("shifts_worked",  0))
night_s   = int(prov_row.get("night_shifts",   0))
weekend_s = int(prov_row.get("weekend_shifts", 0))
hours_w   = float(prov_row.get("hours_worked", 0))
avg_hrs   = hours_w / max(total_s, 1)

def act_card(col, label, value, sub=None, color="#2C2C2A", tip_key=None):
    sub_html = f'<div style="font-size:10px;color:#888;margin-top:2px;">{sub}</div>' if sub else ""
    tip = tooltip_icon(tip_key or label)
    col.markdown(f"""
    <div style="background:#F1EFE8;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:#888;margin-bottom:2px;">{label}{tip}</div>
      <div style="font-size:20px;font-weight:700;color:{color};">{value}</div>
      {sub_html}
    </div>""", unsafe_allow_html=True)

a1, a2, a3, a4, a5, a6 = st.columns(6)
act_card(a1, "Total Shifts",    total_s,           tip_key="Total Shifts")
act_card(a2, "Total Hours",     f"{hours_w:.0f}",  tip_key="Total Hours (shift)")
act_card(a3, "Avg hrs / Shift", f"{avg_hrs:.1f}",  tip_key="Avg hrs / Shift")
act_card(a4, "Night Shifts",    night_s,
         sub=f"{night_s/max(total_s,1)*100:.0f}% of shifts", color="#185FA5", tip_key="Night Shifts")
act_card(a5, "Weekend Shifts",  weekend_s,
         sub=f"{weekend_s/max(total_s,1)*100:.0f}% of shifts", color="#854F0B", tip_key="Weekend Shifts")
act_card(a6, "Extra Pickups",   opu + spu,
         sub=f"{opu} open · {spu} staff-posted", color="#3B6D11", tip_key="Extra Pickups")

st.markdown("<br>", unsafe_allow_html=True)

left_c, right_c = st.columns([1.6, 1])

cat_colors = {"Day": "#185FA5", "Evening": "#854F0B", "Night": "#2C2C2A"}

with left_c:
    st.markdown("**Shifts by Type**")
    fig_shift = go.Figure()
    for cat in ["Night", "Evening", "Day"]:
        sub = shift_df[shift_df["category"] == cat]
        if sub.empty:
            continue
        fig_shift.add_trace(go.Bar(
            y=sub["shift_type"], x=sub["count"], name=cat,
            orientation="h", marker_color=cat_colors[cat],
            text=sub["count"], textposition="outside",
            hovertemplate=f"<b>%{{y}}</b><br>{cat}: %{{x}} shifts<extra></extra>",
        ))
    fig_shift.update_layout(
        barmode="group", xaxis_title="Number of Shifts",
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=120, r=40, t=10, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(showgrid=True, gridcolor="#F1EFE8"),
        yaxis=dict(tickfont=dict(size=10)),
        height=max(300, len(shift_df) * 28 + 60),
    )
    st.plotly_chart(fig_shift, use_container_width=True, key="shift_bar")

with right_c:
    st.markdown("**Shift Category Summary**")
    cat_totals = shift_df.groupby("category")[["count","hours"]].sum().reset_index()
    for _, row in cat_totals.sort_values("count", ascending=False).iterrows():
        clr = cat_colors.get(row["category"], C_GRAY)
        pct = round(row["count"] / max(shift_df["count"].sum(), 1) * 100)
        st.markdown(f"""
        <div style="border-left:4px solid {clr};padding:10px 14px;
                    background:#F1EFE8;border-radius:0 8px 8px 0;margin-bottom:8px;">
          <div style="font-size:12px;font-weight:600;color:{clr};">{row['category']} Shifts</div>
          <div style="font-size:18px;font-weight:700;color:#2C2C2A;">{int(row['count'])} shifts</div>
          <div style="font-size:11px;color:#888;">{pct}% of total &nbsp;·&nbsp; {row['hours']:.0f} hrs</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Shift Pickups**")
    st.markdown(f"""
    <div style="background:#EAF3DE;border-radius:8px;padding:12px 16px;">
      <div style="font-size:12px;color:#3B6D11;font-weight:600;margin-bottom:6px;">
        Extra Shift Pickups — {opu+spu} total
      </div>
      <div style="font-size:12px;color:#555;">
        {opu} open shift pickup{"s" if opu != 1 else ""} (OPU)<br>
        {spu} staff-posted pickup{"s" if spu != 1 else ""} (SPU)
      </div>
    </div>""", unsafe_allow_html=True)
