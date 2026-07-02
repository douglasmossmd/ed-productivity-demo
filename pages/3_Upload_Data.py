import streamlit as st, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if not st.session_state.get("authenticated"):
    st.error("Please log in."); st.stop()
from utils.helpers import C_PRIMARY
st.markdown(f"""<div style="background:{C_PRIMARY};padding:16px 24px;border-radius:10px;margin-bottom:20px;">
  <span style="color:white;font-size:22px;font-weight:600;">Upload Data</span></div>""", unsafe_allow_html=True)
st.info(
    "**Demo mode** — Upload is disabled. The dashboard is pre-loaded with anonymized "
    "productivity data spanning 2023–2026.\n\n"
    "In the live dashboard, admins upload monthly profee cube exports here, which are "
    "parsed and pushed directly to the database.",
    icon="🔒",
)
