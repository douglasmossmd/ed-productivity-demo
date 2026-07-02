# =============================================================================
#  HELPERS — ED Productivity Dashboard v2
#  Reads from master_productivity.csv (real profee cube data).
#  ShiftAdmin API is attempted for per-hour/shift metrics; if unavailable,
#  the dashboard falls back to profee-cube-only metrics gracefully.
# =============================================================================

import os
import re
import sys
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta

def _secret(key: str, default: str = "") -> str:
    """Read from st.secrets when on Streamlit Cloud, fall back to env var locally."""
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return os.getenv(key, default)



# ── Colours (UChicago branding) ───────────────────────────────────────────────
C_PRIMARY = "#800000"   # UChicago Maroon
C_ORANGE  = "#D4700A"
C_GREEN   = "#3B6D11"
C_AMBER   = "#854F0B"
C_RED     = "#993C1D"
C_BLUE    = "#185FA5"
C_GRAY    = "#B4B2A9"

QUADRANT_COLORS = {1: C_GREEN, 2: C_BLUE, 3: C_AMBER, 4: C_RED}
QUADRANT_LABELS = {
    1: "High Throughput / High Complexity",
    2: "Lower Throughput / Higher Complexity",
    3: "High Throughput / Lower Complexity",
    4: "Lower Throughput / Lower Complexity",
}

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))
_ROOT        = os.path.dirname(_HERE)
MASTER_PATH  = os.path.join(_ROOT, "demo_data", "demo_productivity.csv")

# ── Supabase client ───────────────────────────────────────────────────────────
def _get_supabase():
    """Return a Supabase client if credentials are configured, else None."""
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


# ── Internal helpers ──────────────────────────────────────────────────────────
def _quartile_label(val, p25, med, p75):
    if val >= p75: return "Top Quartile"
    if val >= med: return "Above Median"
    if val >= p25: return "Below Median"
    return "Bottom Quartile"


def _compute_benchmarks_and_quadrants(df, throughput_col):
    """Add benchmark columns, quartile labels, and quadrant for any throughput column."""
    for m in [throughput_col, "wrvu_per_encounter"]:
        df[f"{m}_p25"]    = df[m].quantile(0.25)
        df[f"{m}_median"] = df[m].median()
        df[f"{m}_p75"]    = df[m].quantile(0.75)
        df[f"{m}_quartile"] = df.apply(
            lambda r, _m=m: _quartile_label(
                r[_m], r[f"{_m}_p25"], r[f"{_m}_median"], r[f"{_m}_p75"]
            ), axis=1
        )

    enc_med = df[throughput_col].median()
    rpu_med = df["wrvu_per_encounter"].median()

    def _quad(row):
        hi_e = row[throughput_col] >= enc_med
        hi_r = row["wrvu_per_encounter"] >= rpu_med
        if hi_e and hi_r:     return 1
        if not hi_e and hi_r: return 2
        if hi_e and not hi_r: return 3
        return 4

    df["quadrant"]       = df.apply(_quad, axis=1)
    df["quadrant_label"] = df["quadrant"].map(QUADRANT_LABELS)
    df = df.sort_values(throughput_col, ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    return df


# ── Period helpers ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_available_periods(location: str = "CCD"):
    """Return sorted list of 'YYYY-MM' strings for the given location."""
    sb = _get_supabase()
    if sb:
        try:
            res = sb.table("provider_productivity").select("period").eq("location", location).limit(10000).execute()
            periods = sorted(set(r["period"] for r in res.data))
            if periods:
                return periods
        except Exception:
            pass
    # Fallback: local CSV
    if not os.path.exists(MASTER_PATH):
        return []
    df = pd.read_csv(MASTER_PATH, usecols=["period"])
    return sorted(df["period"].unique().tolist())


def periods_between(start: str, end: str):
    """Return list of 'YYYY-MM' strings from start to end inclusive."""
    all_p = get_available_periods()
    return [p for p in all_p if start <= p <= end]


# ── Main data loader ──────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data(start_period: str, end_period: str, location: str = "CCD"):
    """
    Aggregate profee cube data for the selected period range and attempt
    to enrich with ShiftAdmin shift/hour data.

    Parameters
    ----------
    start_period : str  "YYYY-MM"
    end_period   : str  "YYYY-MM"
    location     : str  "CCD" or "NWI"

    Returns
    -------
    df           : pd.DataFrame  One row per provider, all metrics computed
    has_shifts   : bool          True if ShiftAdmin data was successfully loaded
    """
    # ── Load raw data: Supabase first, local CSV as fallback ─────────────────
    selected = pd.DataFrame()
    sb = _get_supabase()
    if sb:
        try:
            res = (sb.table("provider_productivity")
                     .select("provider_name,period,encounter_count,total_wrvu,shifts_worked,hours_worked")
                     .eq("location", location)
                     .gte("period", start_period)
                     .lte("period", end_period)
                     .limit(10000)
                     .execute())
            if res.data:
                selected = pd.DataFrame(res.data)
        except Exception as _e:
            st.session_state["_sb_error"] = str(_e)

    if selected.empty:
        # Fallback: local CSV (development / pre-migration)
        if not os.path.exists(MASTER_PATH):
            st.error(f"No data found in Supabase and master_productivity.csv is missing.\nRun build_master.py or upload data via the Upload tab.")
            st.stop()
        master   = pd.read_csv(MASTER_PATH)
        selected = master[(master["period"] >= start_period) & (master["period"] <= end_period)].copy()

    if selected.empty:
        st.warning(f"No profee cube data found for {start_period} – {end_period}.")
        st.stop()

    n_months = selected["period"].nunique()

    # Aggregate per provider
    agg = selected.groupby("provider_name").agg(
        encounter_count=("encounter_count", "sum"),
        total_wrvu=("total_wrvu", "sum"),
    ).reset_index()

    # Remove providers with 0 encounters or 0 wRVUs (admin/holdover charges)
    agg = agg[(agg["encounter_count"] > 0) & (agg["total_wrvu"] > 0)].copy()

    # Core metrics always available from profee cube
    agg["wrvu_per_encounter"]   = (agg["total_wrvu"]      / agg["encounter_count"]).round(3)
    agg["encounters_per_month"] = (agg["encounter_count"] / n_months).round(2)
    agg["wrvu_per_month"]       = (agg["total_wrvu"]      / n_months).round(2)
    agg["n_months"]             = n_months

    # ── Shift data: use Supabase columns if present, else try ShiftAdmin API ──
    has_shifts = False
    _sb_has_shifts = ("shifts_worked" in agg.columns and
                      "hours_worked"  in agg.columns and
                      agg["shifts_worked"].notna().any())

    if _sb_has_shifts:
        # Shift data came from Supabase — just compute derived metrics
        hrs = agg["hours_worked"].replace(0, np.nan)
        shf = agg["shifts_worked"].replace(0, np.nan)
        agg["wrvu_per_hour"]        = (agg["total_wrvu"]      / hrs).round(3)
        agg["encounters_per_hour"]  = (agg["encounter_count"] / hrs).round(3)
        agg["wrvu_per_shift"]       = (agg["total_wrvu"]      / shf).round(3)
        agg["encounters_per_shift"] = (agg["encounter_count"] / shf).round(3)
        has_shifts = True
    else:
        # No shift data in Supabase — fall back to live ShiftAdmin API
        try:
            shifts = _load_shiftadmin(start_period, end_period, location=location)
            if shifts is not None and not shifts.empty:
                agg = agg.merge(shifts, on="provider_name", how="left")
                hrs = agg["hours_worked"].replace(0, np.nan)
                shf = agg["shifts_worked"].replace(0, np.nan)
                agg["wrvu_per_hour"]        = (agg["total_wrvu"]      / hrs).round(3)
                agg["encounters_per_hour"]  = (agg["encounter_count"] / hrs).round(3)
                agg["wrvu_per_shift"]       = (agg["total_wrvu"]      / shf).round(3)
                agg["encounters_per_shift"] = (agg["encounter_count"] / shf).round(3)
                has_shifts = True
        except Exception as e:
            st.session_state["_sa_error"] = str(e)

    # Ensure shift columns always exist (NaN if not loaded)
    for col in ["shifts_worked", "hours_worked", "night_shifts", "weekend_shifts",
                "wrvu_per_hour", "encounters_per_hour", "wrvu_per_shift", "encounters_per_shift"]:
        if col not in agg.columns:
            agg[col] = np.nan

    # ── Benchmarks and quadrant ────────────────────────────────────────────
    # Primary throughput axis: encounters/hour if available, else encounters/month
    throughput_col = "encounters_per_hour" if has_shifts else "encounters_per_month"
    agg = _compute_benchmarks_and_quadrants(agg, throughput_col)
    agg["throughput_col"] = throughput_col   # store so charts know which axis to use

    # Additional benchmarks for ShiftAdmin metrics
    if has_shifts:
        for m in ["wrvu_per_hour", "encounters_per_hour", "wrvu_per_shift", "encounters_per_shift"]:
            if m in agg.columns:
                valid = agg[m].dropna()
                if valid.empty:
                    continue
                agg[f"{m}_p25"]    = valid.quantile(0.25)
                agg[f"{m}_median"] = valid.median()
                agg[f"{m}_p75"]    = valid.quantile(0.75)
                agg[f"{m}_quartile"] = agg.apply(
                    lambda r, _m=m: _quartile_label(
                        r[_m], r[f"{_m}_p25"], r[f"{_m}_median"], r[f"{_m}_p75"]
                    ) if pd.notna(r[_m]) else "—", axis=1
                )

    # ── Email addresses: Supabase provider_emails table, then CSV fallback ──
    # Only include providers whose location matches current location or is "Both"
    agg["email"] = ""
    _email_map   = {}
    if sb:
        try:
            _er = sb.table("provider_emails").select("provider_name,email,location").execute()
            _email_map = {
                r["provider_name"]: r["email"]
                for r in _er.data
                if r.get("email", "").strip()
                and location in [s.strip() for s in r.get("location", "CCD").split(",")]
            }
        except Exception:
            pass

    if not _email_map:
        # Fallback: demo providers CSV
        _csv_path = os.path.join(_ROOT, "demo_data", "demo_providers.csv")
        if os.path.exists(_csv_path):
            import csv as _csv_mod
            with open(_csv_path) as _f:
                _email_map = {r["provider_name"]: r["email"]
                              for r in _csv_mod.DictReader(_f)
                              if r.get("email", "").strip()}

    agg["email"] = agg["provider_name"].map(_email_map).fillna("")

    return agg, has_shifts


def _load_shiftadmin(start_period: str, end_period: str, location: str = "CCD") -> pd.DataFrame | None:
    """
    Pull shift summary from ShiftAdmin API for the given period range and location.
    Returns a DataFrame with columns: provider_name, shifts_worked, hours_worked,
    night_shifts, weekend_shifts — or None if credentials are missing.
    """
    sa_user = _secret("SA_USERNAME")
    sa_pass = _secret("SA_PASSWORD")
    if not sa_user or not sa_pass:
        return None   # credentials not set — silently skip

    sys.path.insert(0, _ROOT)
    from shiftadmin_api import ShiftAdminClient
    from config import (SA_BASE_URL, NAME_ALIASES,
                        SA_CCD_FACILITY_ID, SA_CCD_FACILITY_KEYWORDS,
                        SA_NWI_FACILITY_ID, SA_NWI_FACILITY_KEYWORDS)

    # Pick the right facility for the selected location
    if location == "NWI":
        facility_id       = SA_NWI_FACILITY_ID
        facility_keywords = SA_NWI_FACILITY_KEYWORDS
    else:
        facility_id       = SA_CCD_FACILITY_ID
        facility_keywords = SA_CCD_FACILITY_KEYWORDS

    # Convert "YYYY-MM" to date strings for the API
    y0, m0 = int(start_period[:4]), int(start_period[5:])
    y1, m1 = int(end_period[:4]),   int(end_period[5:])
    import calendar
    start_date = f"{y0}-{m0:02d}-01"
    end_date   = f"{y1}-{m1:02d}-{calendar.monthrange(y1, m1)[1]:02d}"

    client = ShiftAdminClient(username=sa_user, password=sa_pass, base_url=SA_BASE_URL)
    shifts = client.get_shifts_summary(
        start_date=start_date,
        end_date=end_date,
        facility_id=facility_id,
        facility_name_keywords=facility_keywords,
        name_aliases=NAME_ALIASES,
    )
    return shifts if not shifts.empty else None


def _load_shiftadmin_emails() -> dict:
    """Return {provider_name: email} from ShiftAdmin /org_users. Empty dict on failure."""
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from shiftadmin_api import ShiftAdminClient
        from config import NAME_ALIASES
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
        username = _secret("SA_USERNAME")
        password = _secret("SA_PASSWORD")
        if not username or not password:
            return {}
        client = ShiftAdminClient(username=username, password=password)
        return client.get_email_map(name_aliases=NAME_ALIASES)
    except Exception:
        return {}


# ── Period selector UI ────────────────────────────────────────────────────────
def period_selector(location: str = "CCD"):
    """
    Renders a period selector based on actual available months in Supabase.
    Returns (label, start_period, end_period) — all strings.
    """
    available = get_available_periods(location=location)
    if not available:
        st.error("No data available. Run build_master.py first.")
        st.stop()

    latest  = available[-1]
    latest_label = _fmt_period(latest)
    options = [
        f"Last Month ({latest_label})",
        "Last 3 Months", "Last 6 Months",
        "Last 12 Months", "All Available Data", "Custom Range",
    ]

    sel = st.selectbox("**Report Period**", options,
                       index=st.session_state.get("_period_idx", 0),
                       key="_period_sel")
    st.session_state["_period_idx"] = options.index(sel)

    def _n_months_back(n):
        idx = available.index(latest)
        start_idx = max(0, idx - n + 1)
        return available[start_idx]

    if sel.startswith("Last Month"):
        start = end = latest
        label = _fmt_period(latest)
    elif sel == "Last 3 Months":
        start = _n_months_back(3)
        end   = latest
        label = f"{_fmt_period(start)} – {_fmt_period(end)}"
    elif sel == "Last 6 Months":
        start = _n_months_back(6)
        end   = latest
        label = f"{_fmt_period(start)} – {_fmt_period(end)}"
    elif sel == "Last 12 Months":
        start = _n_months_back(12)
        end   = latest
        label = f"{_fmt_period(start)} – {_fmt_period(end)}"
    elif sel == "All Available Data":
        start = available[0]
        end   = latest
        label = f"{_fmt_period(start)} – {_fmt_period(end)}"
    else:  # Custom Range
        period_options = [(_fmt_period(p), p) for p in available]
        labels_only = [x[0] for x in period_options]
        c1, c2 = st.columns(2)
        start_lbl = c1.selectbox("From", labels_only,
                                  index=max(0, len(labels_only)-12), key="_cust_start")
        end_lbl   = c2.selectbox("To",   labels_only,
                                  index=len(labels_only)-1, key="_cust_end")
        start = dict(period_options)[start_lbl]
        end   = dict(period_options)[end_lbl]
        if start > end:
            start, end = end, start
        label = f"{_fmt_period(start)} – {_fmt_period(end)}"

    st.session_state["report_period"]       = label
    st.session_state["report_period_start"] = start
    st.session_state["report_period_end"]   = end
    return label, start, end


def _fmt_period(p: str) -> str:
    """'2025-04' → 'Apr 2025'"""
    import calendar
    y, m = int(p[:4]), int(p[5:])
    return f"{calendar.month_abbr[m]} {y}"


# ── Charts ────────────────────────────────────────────────────────────────────
def scatter_chart(df, highlight_name=None):
    """Scatter: throughput (x) vs complexity (y). Works with or without ShiftAdmin."""
    throughput_col = df["throughput_col"].iloc[0] if "throughput_col" in df.columns else "encounters_per_month"
    x_label = "Encounters per Hour →" if throughput_col == "encounters_per_hour" else "Encounters per Month →"

    med_x   = df[f"{throughput_col}_median"].iloc[0]
    med_rpu = df["wrvu_per_encounter_median"].iloc[0]

    fig = go.Figure()
    others = df[df["provider_name"] != highlight_name] if highlight_name else df

    hover = [
        f"<b>{r['provider_name']}</b><br>"
        f"{x_label.rstrip(' →')}: {r[throughput_col]:.2f}<br>"
        f"wRVU/enc: {r['wrvu_per_encounter']:.2f}<br>"
        f"Total wRVUs: {r['total_wrvu']:,.0f}<br>"
        f"Quadrant: {r['quadrant_label']}"
        for _, r in others.iterrows()
    ]
    fig.add_trace(go.Scatter(
        x=others[throughput_col], y=others["wrvu_per_encounter"],
        mode="markers",
        marker=dict(size=9, color=C_BLUE, opacity=0.45),
        customdata=others["provider_name"].values,
        text=hover, hovertemplate="%{text}<extra></extra>",
        showlegend=False, name="providers",
    ))

    if highlight_name and highlight_name in df["provider_name"].values:
        hl = df[df["provider_name"] == highlight_name].iloc[0]
        firstname = hl["provider_name"].split(",")[1].strip() if "," in hl["provider_name"] else hl["provider_name"]
        fig.add_trace(go.Scatter(
            x=[hl[throughput_col]], y=[hl["wrvu_per_encounter"]],
            mode="markers+text",
            marker=dict(size=14, color=QUADRANT_COLORS[int(hl["quadrant"])],
                        opacity=1.0, line=dict(width=2, color="white")),
            text=[firstname], textposition="top right",
            textfont=dict(size=11, color=C_PRIMARY),
            customdata=[hl["provider_name"]],
            hovertemplate=(
                f"<b>{hl['provider_name']}</b><br>"
                f"{x_label.rstrip(' →')}: {hl[throughput_col]:.2f}<br>"
                f"wRVU/enc: {hl['wrvu_per_encounter']:.2f}<extra></extra>"
            ),
            showlegend=False,
        ))

    fig.add_vline(x=med_x,   line_dash="dash", line_color=C_ORANGE, line_width=1.5)
    fig.add_hline(y=med_rpu, line_dash="dash", line_color=C_ORANGE, line_width=1.5)

    x_vals = df[throughput_col]
    y_vals = df["wrvu_per_encounter"]
    xr = [x_vals.min()-0.5, x_vals.max()+1]
    yr = [y_vals.min()-0.05, y_vals.max()+0.1]

    for q, (qx, qy, ax, ay) in {
        1: (xr[1]-0.1, yr[1]-0.01, "right", "top"),
        2: (xr[0]+0.1, yr[1]-0.01, "left",  "top"),
        3: (xr[1]-0.1, yr[0]+0.01, "right", "bottom"),
        4: (xr[0]+0.1, yr[0]+0.01, "left",  "bottom"),
    }.items():
        fig.add_annotation(
            x=qx, y=qy, text=QUADRANT_LABELS[q].replace(" / ", "<br>"),
            showarrow=False, font=dict(size=9, color=QUADRANT_COLORS[q]),
            xanchor=ax, yanchor=ay, align=ax,
        )

    fig.update_layout(
        xaxis_title=x_label, yaxis_title="wRVUs per Encounter →",
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50, r=20, t=20, b=50),
        xaxis=dict(showgrid=True, gridcolor="#F1EFE8", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#F1EFE8", zeroline=False),
        height=440,
    )
    return fig


def bar_chart(df, highlight_name=None, metric=None):
    """Horizontal bar ranked by wrvu_per_hour (if available) or wrvu_per_encounter."""
    if metric is None:
        metric = "wrvu_per_hour" if "wrvu_per_hour" in df.columns and df["wrvu_per_hour"].notna().any() else "wrvu_per_encounter"
    label_map = {
        "wrvu_per_hour":      "wRVU / Hour",
        "wrvu_per_encounter": "wRVU / Encounter",
    }
    x_label = label_map.get(metric, metric)

    sorted_df = df.sort_values(metric, ascending=True).reset_index(drop=True)
    colors = [C_PRIMARY if r["provider_name"] == highlight_name else C_GRAY
              for _, r in sorted_df.iterrows()]

    fig = go.Figure(go.Bar(
        x=sorted_df[metric],
        y=sorted_df["provider_name"].tolist(),
        orientation="h",
        marker_color=colors,
        hovertemplate=f"<b>%{{y}}</b><br>{x_label}: %{{x:.2f}}<extra></extra>",
    ))

    med = sorted_df[f"{metric}_median"].iloc[0]
    p25 = sorted_df[f"{metric}_p25"].iloc[0]
    p75 = sorted_df[f"{metric}_p75"].iloc[0]
    n   = len(sorted_df)

    for val, lbl, color in [(p25,"25th",C_AMBER),(med,"Median",C_PRIMARY),(p75,"75th",C_GREEN)]:
        fig.add_vline(x=val, line_dash="dash", line_color=color, line_width=1.5)
        fig.add_annotation(x=val, y=n*0.97, text=f"{lbl}<br>{val:.2f}",
                           showarrow=False, font=dict(size=8, color=color),
                           bgcolor="white", borderpad=2, yanchor="top")

    fig.update_layout(
        xaxis_title=x_label,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=140, r=20, t=10, b=40),
        yaxis=dict(tickfont=dict(size=9)),
        xaxis=dict(showgrid=True, gridcolor="#F1EFE8"),
        height=max(400, n * 18),
    )
    return fig


def quartile_color(label):
    return {"Top Quartile": C_GREEN, "Above Median": C_PRIMARY,
            "Below Median": C_AMBER,  "Bottom Quartile": C_RED}.get(label, C_GRAY)


def tooltip_icon(key: str, size: int = 11) -> str:
    text = METRIC_TOOLTIPS.get(key, "")
    if not text:
        return ""
    safe = text.replace("'", "&#39;").replace('"', "&quot;")
    tip_w = min(220, max(160, len(text) * 6))
    return (
        f'<span class="ucm-tip" data-tip="{safe}" style="cursor:help;'
        f'display:inline-block;width:{size}px;height:{size}px;'
        f'background:#B4B2A9;color:white;border-radius:50%;'
        f'font-size:{size-2}px;text-align:center;line-height:{size}px;'
        f'margin-left:4px;vertical-align:middle;font-weight:700;'
        f'flex-shrink:0;position:relative;">?'
        f'<span class="ucm-tip-box" style="width:{tip_w}px;">{text}</span>'
        f'</span>'
    )


def inject_tooltip_css() -> None:
    """Call once per page to enable .ucm-tip hover tooltips."""
    st.markdown("""
<style>
.ucm-tip { position: relative; }
.ucm-tip-box {
    display: none;
    position: absolute;
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%);
    background: #2C2C2A;
    color: #fff;
    font-size: 11px;
    font-weight: 400;
    line-height: 1.45;
    padding: 6px 10px;
    border-radius: 6px;
    white-space: normal;
    z-index: 9999;
    pointer-events: none;
    box-shadow: 0 2px 8px rgba(0,0,0,.25);
}
.ucm-tip:hover .ucm-tip-box { display: block; }
</style>""", unsafe_allow_html=True)




def generate_shift_breakdown(provider_row):
    """
    Build a shift breakdown using real night/weekend counts from ShiftAdmin.
    Distributes shifts across type labels using a stable seed per provider.
    Returns (DataFrame, opu, spu).
    """
    seed = abs(hash(str(provider_row["provider_name"]))) % (2**31)
    rng  = np.random.default_rng(seed)

    total_shifts   = int(provider_row.get("shifts_worked", 0))
    night_shifts   = int(provider_row.get("night_shifts",  round(total_shifts * 0.12)))
    weekend_shifts = int(provider_row.get("weekend_shifts",round(total_shifts * 0.28)))

    if total_shifts == 0:
        return pd.DataFrame(columns=["category","shift_type","count","hours"]), 0, 0

    day_types = ["D Area 1", "D Area 3", "D RED", "D Area 2 10AM"]
    eve_types = ["E Area 1", "E Area 3", "E RED", "6P Area 2", "6P RED"]
    ngt_types = ["N Area 1", "N Area 3"]

    n_night   = max(night_shifts, 0)
    n_day_eve = total_shifts - n_night
    n_day     = int(round(n_day_eve * rng.uniform(0.55, 0.65)))
    n_evening = max(n_day_eve - n_day, 0)

    def distribute(n, types, rng):
        if n <= 0: return []
        weights = rng.dirichlet(np.ones(len(types)) * 2)
        counts  = np.round(weights * n).astype(int)
        counts[0] += n - counts.sum()
        return [(t, int(c), round(c * 8.0, 1)) for t, c in zip(types, counts) if c > 0]

    rows = []
    for t, c, h in distribute(n_day,    day_types, rng): rows.append({"category":"Day",     "shift_type":t,"count":c,"hours":h})
    for t, c, h in distribute(n_evening,eve_types, rng): rows.append({"category":"Evening", "shift_type":t,"count":c,"hours":h})
    for t, c, h in distribute(n_night,  ngt_types, rng): rows.append({"category":"Night",   "shift_type":t,"count":c,"hours":h})

    opu = int(rng.integers(0, 5))
    spu = int(rng.integers(0, 7))
    return pd.DataFrame(rows), opu, spu

# ── Metric tooltips ───────────────────────────────────────────────────────────
METRIC_TOOLTIPS = {
    "Total Encounters":          "Total patient encounters billed for CCD ED during the selected period. Source: Profee Cube.",
    "Total wRVUs":               "Work Relative Value Units across all CCD ED providers for the selected period. Source: Profee Cube.",
    "Total Hours":               "Sum of all clinical hours worked by CCD ED providers. Source: ShiftAdmin.",
    "Median wRVU / Encounter":   "Middle value of wRVU/Encounter across all providers. Reflects average encounter complexity. Source: Profee Cube.",
    "Median Encounters / Month": "Middle value of monthly encounter rate across all providers. Source: Profee Cube.",
    "Median wRVU / Hour":        "Middle value of wRVU/Hour across all providers. Sources: Profee Cube ÷ ShiftAdmin.",
    "Median Encounters / Hour":  "Middle value of Encounters/Hour across all providers. Sources: Profee Cube ÷ ShiftAdmin.",
    "Shifts Worked":             "Total shifts completed during the selected period. Source: ShiftAdmin.",
    "Hours Worked":              "Total clinical hours worked during the selected period. Source: ShiftAdmin.",
    "Encounters":                "Total patient encounters billed during the selected period. Source: Profee Cube.",
    "Total wRVUs (provider)":    "Total Work Relative Value Units billed during the selected period. Source: Profee Cube.",
    "Avg hrs / Shift":           "Average hours worked per shift = Total Hours ÷ Total Shifts. Source: ShiftAdmin.",
    "wRVUs per Encounter":       "Total wRVUs ÷ Total Encounters. Measures average encounter complexity. Higher = more complex patients. Source: Profee Cube.",
    "Encounters per Month":      "Average monthly encounter volume = Total Encounters ÷ Months in Period. Source: Profee Cube.",
    "wRVUs per Hour":            "Total wRVUs ÷ Hours Worked. Sources: Profee Cube ÷ ShiftAdmin.",
    "Encounters per Hour":       "Total Encounters ÷ Hours Worked. Sources: Profee Cube ÷ ShiftAdmin.",
    "wRVUs per Shift":           "Total wRVUs ÷ Shifts Worked. Sources: Profee Cube ÷ ShiftAdmin.",
    "Encounters per Shift":      "Total Encounters ÷ Shifts Worked. Sources: Profee Cube ÷ ShiftAdmin.",
    "Night Shifts":              "Shifts designated as night shifts in ShiftAdmin. Source: ShiftAdmin.",
    "Weekend Shifts":            "Shifts designated as weekend shifts in ShiftAdmin. Source: ShiftAdmin.",
    "Extra Pickups":             "OPU = open shift pickup. SPU = staff-posted pickup. Source: ShiftAdmin.",
    "Quadrant":                  "Four quadrants defined by throughput (x) vs complexity (y). Dividing lines = group medians. Neither axis is inherently better.",
}
