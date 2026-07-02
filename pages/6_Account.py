import os, sys
import streamlit as st
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if not st.session_state.get("authenticated"):
    st.error("Please log in from the home page."); st.stop()

is_admin = st.session_state.get("role") == "admin"
st.title("Account")

st.subheader("🔑 Change password")
st.info("**Demo mode** — Password changes are disabled. Sign in with **demo1234**.", icon="🔒")

st.markdown("---")
st.subheader("👤 User management")
st.caption("All accounts that can log in to the dashboard. Admins can add, edit, and delete accounts.")

from utils.auth import get_all_users
users = get_all_users()

with st.expander("➕ Add new user", expanded=False):
    with st.form("add_user_form"):
        c1, c2 = st.columns(2)
        c1.text_input("Display name", placeholder="Jane Smith")
        c2.text_input("Email", placeholder="jane@demo.com")
        st.selectbox("Role", ["viewer", "admin"])
        add_sub = st.form_submit_button("Create account", type="primary", use_container_width=True,
            disabled=not is_admin, help="Admin access required" if not is_admin else None)
    if add_sub and is_admin:
        st.info("**Demo mode** — User management is disabled.", icon="🔒")

st.markdown("---")
if not users:
    st.info("No users found.")
else:
    h1, h2, h3, h4, h5 = st.columns([3, 3, 2, 1, 1])
    for col, lbl in zip([h1,h2,h3,h4,h5], ["Name","Email","Role","Edit","Delete"]):
        col.markdown(f"**{lbl}**")
    st.divider()
    for u in users:
        c1, c2, c3, c4, c5 = st.columns([3, 3, 2, 1, 1])
        c1.write(u.get("display_name", ""))
        c2.write(u.get("ucm_username", ""))
        c3.write(u.get("role", "viewer"))
        c4.button("✏️", key=f"edit_{u['ucm_username']}", use_container_width=True,
            disabled=not is_admin, help="Admin access required" if not is_admin else None)
        c5.button("🗑",  key=f"del_{u['ucm_username']}",  use_container_width=True,
            disabled=not is_admin, help="Admin access required" if not is_admin else None)
