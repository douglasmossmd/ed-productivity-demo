# =============================================================================
#  Home.py — DEMO version
# =============================================================================
import streamlit as st
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(page_title="ED Productivity", page_icon="🏥", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("""<style>[data-testid="stSidebar"]{display:none}</style>""", unsafe_allow_html=True)
    st.info(
        "**Portfolio Demo** — This is a sanitized demo built for UChicago Medicine CCD ED. "
        "Provider names and user accounts are fictitious. Data reflects real statistical "
        "patterns with all identifying information removed.\n\n"
        "**Login:** demo@demo.com  |  **Password:** demo1234",
        icon="ℹ️",
    )
    st.markdown(
        "<h2 style='text-align:center;margin-top:2rem'>🏥 ED Productivity Dashboard</h2>"
        "<p style='text-align:center;color:gray'>Emergency Medicine — CCD Analytics</p>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        with st.form("login_form", clear_on_submit=False):
            email    = st.text_input("Email", placeholder="demo@demo.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")
        if submitted:
            from utils.auth import get_user, verify_password
            user = get_user(email)
            if user and verify_password(password, user["password_hash"]):
                st.session_state.update({
                    "authenticated":        True,
                    "username":             user["ucm_username"],
                    "display_name":         user.get("display_name", email),
                    "role":                 user["role"],
                    "must_change_password": False,
                })
                st.rerun()
            else:
                st.error("Invalid email or password.")
    st.stop()

is_admin = st.session_state.get("role") == "admin"

pages = [
    st.Page("pages/department_overview.py", title="Department Overview", icon="🏥"),
    st.Page("pages/1_Provider_Explorer.py", title="Provider Explorer",   icon="🔍"),
    st.Page("pages/2_Send_Reports.py",      title="Send Reports",        icon="📧"),
    st.Page("pages/5_Templates.py",        title="Templates",           icon="✏️"),
    st.Page("pages/3_Upload_Data.py",      title="Upload Data",         icon="📤"),
    st.Page("pages/4_Providers.py",        title="Providers",           icon="👥"),
    st.Page("pages/6_Account.py",          title="Account",             icon="⚙️"),
]
pg = st.navigation(pages)

with st.sidebar:
    st.markdown("## ED Productivity")
pg.run()
with st.sidebar:
    st.divider()
    st.markdown(
        f"**{st.session_state.get('display_name', '')}**  \n"
        f"<span style='color:gray;font-size:0.85em'>{'Admin' if is_admin else 'Viewer'}</span>",
        unsafe_allow_html=True,
    )
    if st.button("Sign out", use_container_width=True):
        for k in ["authenticated","username","display_name","role","must_change_password"]:
            st.session_state.pop(k, None)
        st.rerun()
