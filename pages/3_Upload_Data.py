# =============================================================================
#  UPLOAD DATA PAGE — DEMO version
#  Matches production UI; upload + delete controls are disabled.
#  History is read from the pre-loaded demo CSV.
# =============================================================================
import os, sys, io
import streamlit as st
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if not st.session_state.get("authenticated"):
    st.error("Please log in from the home page.")
    st.stop()

from utils.helpers import C_PRIMARY, MASTER_PATH, inject_tooltip_css

inject_tooltip_css()

is_admin = st.session_state.get("role") == "admin"

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:{C_PRIMARY};padding:16px 24px;border-radius:10px;margin-bottom:20px;">
  <span style="color:white;font-size:22px;font-weight:600;">Upload Data</span>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — UPLOAD (disabled in demo)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("⬆️ Upload profee cube export")
st.caption(
    "Upload a profee cube xlsx export. Accepts: "
    "(1) combined CCD + NWI multi-month file, or "
    "(2) a single-month CCD or NWI file — location is auto-detected from the file header. "
    "Existing records are overwritten; new months are added."
)

st.info(
    "**Demo mode** — File upload is disabled. The dashboard is pre-loaded with "
    "anonymized productivity data from 2023–2026.",
    icon="🔒",
)
st.file_uploader(
    "Drop profee cube xlsx here", type=["xlsx"],
    disabled=True,
    help="Upload disabled in demo mode.",
)

col_cb, col_btn = st.columns([2, 1])
with col_cb:
    st.checkbox("Fetch shift data from ShiftAdmin", value=True, disabled=True)
with col_btn:
    st.button(
        "⬆️ Upload to Supabase", type="primary",
        use_container_width=True, disabled=True,
        help="Upload disabled in demo mode.",
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — HISTORY (built from demo CSV)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📋 Upload history")


@st.cache_data(show_spinner=False)
def _load_history():
    df = pd.read_csv(MASTER_PATH)
    # Simulate an uploaded_at date: first day of the following month
    def _uploaded(period):
        try:
            y, m = int(period[:4]), int(period[5:])
            m2 = m + 1 if m < 12 else 1
            y2 = y if m < 12 else y + 1
            return f"{y2}-{m2:02d}-01"
        except Exception:
            return "—"
    df["uploaded_at"] = df["period"].map(_uploaded)
    return df


hist_df = _load_history()

if hist_df.empty:
    st.info("No data available.")
else:
    for loc in ["CCD", "NWI"]:
        loc_df = hist_df[hist_df["location"] == loc]
        if loc_df.empty:
            continue

        st.markdown(f"**{loc}**")
        summary = (
            loc_df.groupby("period")
            .agg(
                providers   = ("provider_name",   "nunique"),
                encounters  = ("encounter_count", "sum"),
                total_wrvus = ("total_wrvu",      "sum"),
                uploaded_at = ("uploaded_at",     "max"),
            )
            .reset_index()
            .sort_values("period", ascending=False)
        )

        h_cols = st.columns([2, 1, 1, 1, 1, 1, 1])
        for col, label in zip(h_cols,
                              ["Month", "Providers", "Encounters",
                               "Total wRVUs", "Uploaded", "Download", "Delete"]):
            col.markdown(f"**{label}**")
        st.divider()

        for _, row in summary.iterrows():
            period = row["period"]
            try:
                period_disp = datetime.strptime(period, "%Y-%m").strftime("%B %Y")
            except Exception:
                period_disp = period

            try:
                up_disp = datetime.strptime(row["uploaded_at"], "%Y-%m-%d").strftime("%b %d %Y")
            except Exception:
                up_disp = "—"

            c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1, 1, 1, 1, 1, 1])
            c1.write(period_disp)
            c2.write(str(int(row["providers"])))
            c3.write(f"{row['encounters']:,.0f}")
            c4.write(f"{row['total_wrvus']:,.1f}")
            c5.write(up_disp)
            c6.button(
                "⬇ CSV", key=f"dl_{loc}_{period}",
                disabled=True, use_container_width=True,
                help="Download disabled in demo mode.",
            )
            c7.button(
                "🗑 Delete", key=f"del_{loc}_{period}",
                disabled=True, use_container_width=True,
                help="Delete disabled in demo mode.",
            )

        st.markdown("")
