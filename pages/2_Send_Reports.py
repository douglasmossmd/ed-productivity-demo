import streamlit as st
import pandas as pd
import zipfile, io, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import (
    load_data, period_selector, inject_tooltip_css,
    QUADRANT_COLORS, QUADRANT_LABELS, C_PRIMARY,
)
from utils.pdf_generator import generate_pdf_bytes

# ── Auth guard ────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.warning("Please sign in from the Home page.")
    st.stop()

inject_tooltip_css()

# ── Session state defaults ────────────────────────────────────────────────────
if "generated_pdfs"   not in st.session_state: st.session_state.generated_pdfs   = {}
if "generated_period" not in st.session_state: st.session_state.generated_period = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    location = st.selectbox("**Location**", ["CCD", "NWI"], key="reports_location")
    st.divider()
    period_label, start_period, end_period = period_selector(location=location)
    st.divider()

    st.markdown("### Quick select")
    select_all = st.button("Select all providers", use_container_width=True)
    select_q   = {q: st.button(f"Select Q{q} only", use_container_width=True) for q in [1,2,3,4]}
    clear_btn  = st.button("Clear all",              use_container_width=True)



# ── Load data ─────────────────────────────────────────────────────────────────
df, has_shifts = load_data(start_period, end_period, location=location)
all_names = df["provider_name"].tolist()

# Emails are now loaded centrally in load_data() via ShiftAdmin + CSV fallback
HERE      = os.path.dirname(os.path.abspath(__file__))
APP_ROOT  = os.path.dirname(HERE)
DATA_ROOT = os.path.dirname(APP_ROOT)

# ── Quick-select button logic ─────────────────────────────────────────────────
if select_all:
    for name in all_names:
        st.session_state[f"chk_{name}"] = True
for q, pressed in select_q.items():
    if pressed:
        q_names = df[df["quadrant"] == q]["provider_name"].tolist()
        for name in all_names:
            st.session_state[f"chk_{name}"] = (name in q_names)
if clear_btn:
    for name in all_names:
        st.session_state[f"chk_{name}"] = False
    st.session_state.generated_pdfs = {}

# Invalidate PDF cache when period changes
if st.session_state.generated_period != period_label:
    st.session_state.generated_pdfs = {}

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:{C_PRIMARY};padding:16px 24px;border-radius:10px;margin-bottom:20px;">
  <span style="color:white;font-size:22px;font-weight:600;">Send Reports</span>
  <span style="color:rgba(255,255,255,0.7);font-size:14px;float:right;margin-top:4px;">
    {period_label}
  </span>
</div>
""", unsafe_allow_html=True)

if not has_shifts:
    st.info(
        "ShiftAdmin not connected — PDFs will use profee cube metrics only (wRVU/encounter, volume). "
        "Connect ShiftAdmin to include per-hour metrics in reports.",
        icon="ℹ️"
    )

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Provider selection
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("1 — Select providers")
left_col, right_col = st.columns([1, 1])

with left_col:
    bg_map = {1:"#EAF3DE", 2:"#E6F1FB", 3:"#FAEEDA", 4:"#FAECE7"}
    for q in [1, 2, 3, 4]:
        color   = QUADRANT_COLORS[q]
        q_provs = df[df["quadrant"] == q]["provider_name"].tolist()
        st.markdown(f"""
        <div style="border-left:4px solid {color};background:{bg_map[q]};
                    border-radius:0 8px 8px 0;padding:8px 14px;margin-bottom:6px;">
          <span style="font-size:12px;font-weight:600;color:{color};">
            Q{q} — {QUADRANT_LABELS[q]} ({len(q_provs)} providers)
          </span>
        </div>""", unsafe_allow_html=True)
        for name in sorted(q_provs):
            email = df.loc[df["provider_name"] == name, "email"].values[0] if name in df["provider_name"].values else ""
            if email:
                label = f"{name}  —  {email}"
                st.checkbox(label, key=f"chk_{name}")
            else:
                col_chk, col_warn = st.columns([3, 1])
                col_chk.checkbox(name, key=f"chk_{name}")
                col_warn.markdown(
                    '<span style="color:#993C1D;font-weight:700;font-size:11px;'
                    'line-height:2.2;">no email on file</span>',
                    unsafe_allow_html=True
                )

active = [n for n in all_names if st.session_state.get(f"chk_{n}", False)]
n_sel  = len(active)

# Drop PDFs for deselected providers
for name in list(st.session_state.generated_pdfs.keys()):
    if name not in active:
        del st.session_state.generated_pdfs[name]

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Generate reports
# ══════════════════════════════════════════════════════════════════════════════
with right_col:
    st.subheader("2 — Generate reports")

    if n_sel == 0:
        st.info("Select providers on the left, then generate their reports here.")
    else:
        st.markdown(f"**{n_sel} provider{'s' if n_sel != 1 else ''} selected**")

        if st.button(f"Generate {n_sel} report{'s' if n_sel != 1 else ''}",
                     type="primary", use_container_width=True):
            progress = st.progress(0, text="Starting…")
            for i, name in enumerate(active):
                progress.progress(i / n_sel, text=f"Building report for {name}…")
                if name not in st.session_state.generated_pdfs:
                    row = df[df["provider_name"] == name].iloc[0]
                    try:
                        st.session_state.generated_pdfs[name] = generate_pdf_bytes(
                            row, df,
                            report_period   = period_label,
                            department_name = "Emergency Medicine",
                            institution     = "University of Chicago Medicine",
                        )
                    except Exception as e:
                        st.warning(f"Could not generate PDF for {name}: {e}")
            st.session_state.generated_period = period_label
            progress.progress(1.0, text="Done!")
            st.rerun()

        all_ready = (bool(st.session_state.generated_pdfs) and
                     set(active) == set(st.session_state.generated_pdfs.keys()))

        if all_ready:
            st.success(f"✅ {len(st.session_state.generated_pdfs)} reports ready for {period_label}")
            period_short = f"{start_period.replace('-','')}_{end_period.replace('-','')}"
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, pdf_bytes in st.session_state.generated_pdfs.items():
                    safe = name.replace(", ", "_").replace(" ", "_")
                    zf.writestr(f"{safe}_{period_short}.pdf", pdf_bytes)
            zip_buf.seek(0)
            st.download_button(
                label="⬇️  Download all as ZIP",
                data=zip_buf.getvalue(),
                file_name=f"ED_Reports_{period_short}.zip",
                mime="application/zip",
                use_container_width=True,
            )

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Preview email + PDF
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("3 — Preview email")

if not active:
    st.info("Select at least one provider above to preview their email.")
else:
    preview_name = st.selectbox("Preview email for:", sorted(active))
    prov_row  = df[df["provider_name"] == preview_name].iloc[0]
    q         = int(prov_row["quadrant"])
    color     = QUADRANT_COLORS[q]
    firstname = preview_name.split(",")[1].strip() if "," in preview_name else preview_name

    # Pull metric lines — gracefully handle missing columns
    def _metric_line(label, col_val, col_quartile):
        v = prov_row.get(col_val, None)
        t = prov_row.get(col_quartile, "")
        if v is None or (hasattr(v, '__class__') and str(v) == 'nan'):
            return ""
        return f"&bull; {label}: <b>{float(v):.2f}</b> ({t})<br>"

    metric_lines = (
        _metric_line("wRVU / Hour",        "wrvu_per_hour",        "wrvu_per_hour_quartile") +
        _metric_line("Encounters / Hour",  "encounters_per_hour",  "encounters_per_hour_quartile") +
        _metric_line("wRVU / Encounter",   "wrvu_per_encounter",   "wrvu_per_encounter_quartile")
    )

    provider_email = prov_row.get("email", "") or "(no email on file)"

    st.markdown(f"""
    <div style="border:1px solid #D3D1C7;border-radius:10px;padding:18px;
                font-size:13px;background:white;line-height:1.7;">
      <div style="color:#888;font-size:11px;margin-bottom:12px;">
        <b>To:</b> {provider_email}<br>
        <b>From:</b> ccd.ed.productivity@gmail.com<br>
        <b>Subject:</b> Your ED Productivity Report — {period_label}
      </div>
      <div style="border-top:1px solid #eee;padding-top:12px;">
        Dear {firstname},<br><br>
        Please find attached your personalized ED productivity report for the period
        <b>{period_label}</b>. Your report includes your individual metrics compared to
        the de-identified group, a visual summary of your position relative to department
        benchmarks, and tailored recommendations based on your results.<br><br>
        <b>Your summary:</b><br>
        {metric_lines}
        <br>
        All other provider data in your report has been fully de-identified.
        If you have questions or would like to discuss your results, please reach out to
        <a href="mailto:EDPhysicianLeadership@uchicagomedicine.org">
        EDPhysicianLeadership@uchicagomedicine.org</a>, or simply reply to this email.<br><br>
        Best regards,<br>
        <b>Emergency Medicine — {location} Analytics</b>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if preview_name in st.session_state.generated_pdfs:
        period_short = f"{start_period.replace('-','')}_{end_period.replace('-','')}"
        safe = preview_name.replace(", ", "_").replace(" ", "_")
        pdf_bytes = st.session_state.generated_pdfs[preview_name]

        # Try to show inline PDF viewer; fall back to download button
        try:
            from streamlit_pdf_viewer import pdf_viewer
            st.markdown("**PDF Preview:**")
            pdf_viewer(input=pdf_bytes, width=700, key=f"pdf_{preview_name}")
        except ImportError:
            st.info(
                "Install `streamlit-pdf-viewer` to see inline PDF preview:\n"
                "```\npip3 install streamlit-pdf-viewer --break-system-packages\n```",
            )

        st.download_button(
            label=f"⬇️  Download {preview_name}'s PDF",
            data=pdf_bytes,
            file_name=f"{safe}_{period_short}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.caption("Generate reports (Step 2) to preview and download the PDF here.")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Send
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("4 — Send")
st.info(
    "**Demo mode** — Email sending is disabled. In the live dashboard, this button sends "
    "personalized PDF reports directly to each provider's UCM email.",
    icon="🔒",
)
st.button("Send reports (disabled in demo)", type="primary", disabled=True)
