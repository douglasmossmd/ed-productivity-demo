# =============================================================================
#  PROVIDERS PAGE
#  Admins: add / edit / delete providers and their email addresses
#  Viewers: read-only
#  Location stored as comma-separated site codes, e.g. "CCD", "NWI", "CCD,NWI"
# =============================================================================
import os, sys
import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Auth gate ─────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.error("Please log in from the home page.")
    st.stop()

is_admin = st.session_state.get("role") == "admin"

# ── Site config — add new entries here when a third site opens ────────────────
ALL_SITES   = ["CCD", "NWI"]
SITE_COLORS = {"CCD": "#185FA5", "NWI": "#3B6D11"}
DEFAULT_COLOR = "#666"

def _badges(location_str: str) -> str:
    """Render one colored pill per site from a comma-separated location string."""
    sites = [s.strip() for s in (location_str or "CCD").split(",") if s.strip()]
    parts = []
    for site in sites:
        color = SITE_COLORS.get(site, DEFAULT_COLOR)
        parts.append(
            f'<span style="background:{color}22;color:{color};font-size:12px;'
            f'font-weight:600;padding:2px 9px;border-radius:10px;'
            f'margin-right:4px;">{site}</span>'
        )
    return "".join(parts)

def _loc_to_list(location_str: str) -> list[str]:
    return [s.strip() for s in (location_str or "CCD").split(",") if s.strip()]

def _list_to_loc(sites: list[str]) -> str:
    # Keep consistent ordering (CCD first, then alphabetical)
    ordered = [s for s in ALL_SITES if s in sites] + \
              sorted([s for s in sites if s not in ALL_SITES])
    return ",".join(ordered) if ordered else "CCD"

@st.cache_data(show_spinner=False)
def _fetch_providers():
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(_root, "demo_data", "demo_providers.csv")
    if not os.path.exists(csv_path):
        return pd.DataFrame(columns=["provider_name","email","location"])
    df = pd.read_csv(csv_path)
    if "location" not in df.columns: df["location"] = "CCD"
    return df.sort_values("provider_name").reset_index(drop=True)

# ══════════════════════════════════════════════════════════════════════════════
st.title("Providers")

df = _fetch_providers()

# ── Add new provider (admin only) ─────────────────────────────────────────────
if is_admin:
    with st.expander("➕ Add new provider", expanded=False):
        with st.form("add_provider_form"):
            c1, c2, c3 = st.columns([3, 4, 2])
            new_name   = c1.text_input("Provider name", placeholder="Last, First")
            new_email  = c2.text_input("UCM email",     placeholder="First.Last@bsd.uchicago.edu")
            new_sites  = c3.multiselect("Sites", ALL_SITES, default=["CCD"])
            submitted  = st.form_submit_button("Add provider", type="primary", use_container_width=True)
        if submitted:
            if not new_name.strip() or not new_email.strip():
                st.error("Both name and email are required.")
            elif not new_sites:
                st.error("Select at least one site.")
            elif new_name.strip() in df["provider_name"].values:
                st.error(f"'{new_name.strip()}' already exists. Edit them below.")
            else:
                st.info("**Demo mode** — Provider management is disabled in this demo.", icon="🔒")

st.markdown("---")

# ── Filter bar ────────────────────────────────────────────────────────────────
loc_filter = st.segmented_control(
    "Show", ["All"] + ALL_SITES, default="All", key="prov_loc_filter"
)
if loc_filter == "All":
    view_df = df
else:
    # Match any row whose location string contains the selected site
    view_df = df[df["location"].str.contains(loc_filter, na=False)]

st.caption(f"Showing {len(view_df)} of {len(df)} providers")

# ── Provider list ─────────────────────────────────────────────────────────────
if view_df.empty:
    st.info("No providers found.")
else:
    if is_admin:
        h1, h2, h3, h4, h5 = st.columns([3, 4, 2, 1, 1])
    else:
        h1, h2, h3 = st.columns([3, 4, 2])
    h1.markdown("**Provider**")
    h2.markdown("**Email**")
    h3.markdown("**Sites**")
    if is_admin:
        h4.markdown("**Edit**")
        h5.markdown("**Delete**")
    st.divider()

    for _, row in view_df.iterrows():
        name        = row["provider_name"]
        email       = row.get("email", "")
        location    = row.get("location", "CCD")
        edit_key    = f"editing_{name}"
        confirm_key = f"confirm_del_{name}"

        if is_admin and st.session_state.get(edit_key):
            # ── Inline edit form ──────────────────────────────────────────────
            with st.form(f"edit_form_{name}"):
                ec1, ec2, ec3 = st.columns([3, 4, 2])
                new_name_val  = ec1.text_input("Name",  value=name)
                new_email_val = ec2.text_input("Email", value=email)
                new_sites_val = ec3.multiselect(
                    "Sites", ALL_SITES,
                    default=_loc_to_list(location),
                )
                sc1, sc2 = st.columns(2)
                save   = sc1.form_submit_button("💾 Save",   use_container_width=True, type="primary")
                cancel = sc2.form_submit_button("✕ Cancel", use_container_width=True)
            if save:
                st.session_state.pop(edit_key, None)
                st.info("**Demo mode** — Provider management is disabled.", icon="🔒")
            if cancel:
                st.session_state.pop(edit_key, None)
                st.rerun()

        elif is_admin and st.session_state.get(confirm_key):
            # ── Delete confirmation ───────────────────────────────────────────
            if is_admin:
                c1, c2, c3, c4, c5 = st.columns([3, 4, 2, 1, 1])
            else:
                c1, c2, c3 = st.columns([3, 4, 2])
            c1.write(name)
            c2.write(email)
            c3.markdown(_badges(location), unsafe_allow_html=True)
            if is_admin:
                if c4.button("✓ Confirm", key=f"do_del_{name}", type="primary", use_container_width=True):
                    st.session_state.pop(confirm_key, None)
                    st.info("**Demo mode** — Provider management is disabled.", icon="🔒")
                if c5.button("✕ Cancel", key=f"cancel_del_{name}", use_container_width=True):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()

        else:
            # ── Normal row ────────────────────────────────────────────────────
            if is_admin:
                c1, c2, c3, c4, c5 = st.columns([3, 4, 2, 1, 1])
            else:
                c1, c2, c3 = st.columns([3, 4, 2])
            c1.write(name)
            c2.write(email if email else "—")
            c3.markdown(_badges(location), unsafe_allow_html=True)
            if is_admin:
                c4.button(
                    "✏️", key=f"edit_btn_{name}",
                    use_container_width=True,
                    on_click=lambda k=edit_key: st.session_state.update({k: True}),
                )
                c5.button(
                    "🗑", key=f"del_btn_{name}",
                    use_container_width=True,
                    on_click=lambda k=confirm_key: st.session_state.update({k: True}),
                )
