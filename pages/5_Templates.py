# =============================================================================
#  TEMPLATES PAGE — DEMO (session-state storage, no Supabase)
# =============================================================================
import os, sys
import streamlit as st
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if not st.session_state.get("authenticated"):
    st.error("Please log in from the home page."); st.stop()

from utils.pdf_generator import DEFAULTS

LABELS = {
    "q1_title":"Section Title", "q1_para1":"Opening paragraph", "q1_para2":"Recommendations paragraph",
    "q2_title":"Section Title", "q2_para1":"Opening paragraph", "q2_para2":"Recommendations paragraph",
    "q3_title":"Section Title", "q3_para1":"Opening paragraph", "q3_para2":"Recommendations paragraph",
    "q4_title":"Section Title", "q4_para1":"Opening paragraph", "q4_para2":"Recommendations paragraph",
    "email_subject":"Subject line", "email_greeting":"Greeting line",
    "email_body":"Body paragraphs",  "email_closing":"Closing / sign-off",
}
QUADRANT_COLORS = {
    1: ("#3B6D11", "#EAF3DE"), 2: ("#185FA5", "#E6F1FB"),
    3: ("#854F0B", "#FAEEDA"), 4: ("#993C1D", "#FAECE7"),
}
SESSION_PREFIX = "tpl_"

def _get(key): return st.session_state.get(SESSION_PREFIX + key, DEFAULTS.get(key, ""))
def _save(key, value): st.session_state[SESSION_PREFIX + key] = value

def _field_form(key, label, val, default, height):
    ck = f"_confirm_{key}"; vk = f"_ver_{key}"
    if vk not in st.session_state: st.session_state[vk] = 0
    if ck in st.session_state: st.success(st.session_state.pop(ck))
    with st.form(f"form_{key}_v{st.session_state[vk]}"):
        nv = st.text_area(label, value=val, height=height)
        c1, c2, _ = st.columns([1, 1, 3])
        save_btn  = c1.form_submit_button("Save",             type="primary", use_container_width=True)
        reset_btn = c2.form_submit_button("Reset to default", use_container_width=True)
    if save_btn:
        _save(key, nv.strip())
        st.session_state[ck] = f"✓  Saved — {label}"; st.rerun()
    if reset_btn:
        _save(key, default); st.session_state[vk] += 1
        st.session_state[ck] = f"↩️  Reset {label} to default"; st.rerun()

def _q_preview(q):
    fg, bg = QUADRANT_COLORS[q]
    st.markdown(
        f'<div style="border:1.5px solid {fg};border-radius:8px;padding:14px 18px;'
        f'background:{bg};margin:12px 0 20px 0;position:relative;">'
        f'<div style="position:absolute;left:0;top:0;bottom:0;width:5px;background:{fg};border-radius:8px 0 0 8px;"></div>'
        f'<div style="margin-left:10px;">'
        f'<p style="font-size:12px;font-weight:700;color:{fg};margin:0 0 8px 0;">{_get(f"q{q}_title")}</p>'
        f'<p style="font-size:11px;color:#2C2C2A;margin:0 0 8px 0;line-height:1.5;">{_get(f"q{q}_para1")}</p>'
        f'<p style="font-size:11px;color:#2C2C2A;margin:0;line-height:1.5;">{_get(f"q{q}_para2")}</p>'
        f'</div></div>', unsafe_allow_html=True)

st.title("Templates")
st.markdown("<style>textarea { caret-color: #2C2C2A !important; }</style>", unsafe_allow_html=True)
st.caption("Edit the verbiage used in PDF reports and the standard email. "
           "Changes carry over to Send Reports immediately. "
           "(Demo mode: edits are saved for this session only.)")

tab_report, tab_email = st.tabs(["PDF Report Text", "Email Template"])

with tab_report:
    st.markdown("These text blocks appear in the **Quadrant Recommendation** box of each provider's PDF report.")
    for q in [1, 2, 3, 4]:
        fg, bg = QUADRANT_COLORS[q]
        st.markdown(f'<div style="border-left:4px solid {fg};background:{bg};border-radius:0 8px 8px 0;'
                    f'padding:10px 16px;margin:16px 0 8px 0;"><b style="color:{fg};">Q{q}</b></div>',
                    unsafe_allow_html=True)
        for field in ["title", "para1", "para2"]:
            k = f"q{q}_{field}"
            _field_form(k, LABELS[k], _get(k), DEFAULTS[k], 68 if field == "title" else 120)
        with st.expander(f"Preview Q{q} report box", expanded=False):
            _q_preview(q)
    st.divider()
    if st.button("Reset ALL PDF report text to defaults", type="secondary"):
        for q2 in [1,2,3,4]:
            for f2 in ["title","para1","para2"]:
                k = f"q{q2}_{f2}"; _save(k, DEFAULTS[k])
                st.session_state[f"_ver_{k}"] = st.session_state.get(f"_ver_{k}", 0) + 1
        st.session_state["_confirm_all_pdf"] = "↩️  All PDF report text reset to defaults"; st.rerun()
    if "_confirm_all_pdf" in st.session_state: st.success(st.session_state.pop("_confirm_all_pdf"))

with tab_email:
    st.markdown("Use `{period}` and `{firstname}` as placeholders — filled in automatically for each provider.")
    HINTS = {"email_subject": "Placeholder: `{period}`", "email_greeting": "Placeholder: `{firstname}`",
             "email_body": "Placeholders: `{period}` and `{firstname}`", "email_closing": None}
    for key in ["email_subject", "email_greeting", "email_body", "email_closing"]:
        hint = HINTS.get(key)
        if hint: st.caption(hint)
        _field_form(key, LABELS[key], _get(key), DEFAULTS[key],
                    68 if key in {"email_subject","email_greeting","email_closing"} else 200)
    st.divider(); st.subheader("Preview")
    def _fill(t): return t.replace("{period}", "Jan – Mar 2025").replace("{firstname}", "Alex")
    subj = _fill(_get("email_subject")); greet = _fill(_get("email_greeting"))
    body = _fill(_get("email_body")).replace("\n\n","<br><br>").replace("\n","<br>")
    closing = _fill(_get("email_closing")).replace("\n","<br>")
    st.markdown(f"""<div style="border:1px solid #D3D1C7;border-radius:10px;padding:18px;
        font-size:13px;background:white;line-height:1.7;">
      <div style="color:#888;font-size:11px;margin-bottom:12px;"><b>Subject:</b> {subj}</div>
      <div style="border-top:1px solid #eee;padding-top:12px;">
        {greet}<br><br>{body}<br><br>{closing}
      </div></div>""", unsafe_allow_html=True)
    st.divider()
    if st.button("Reset ALL email fields to defaults", type="secondary"):
        for k in ["email_subject","email_greeting","email_body","email_closing"]:
            _save(k, DEFAULTS[k]); st.session_state[f"_ver_{k}"] = st.session_state.get(f"_ver_{k}",0)+1
        st.session_state["_confirm_all_email"] = "↩️  Email template reset to defaults"; st.rerun()
    if "_confirm_all_email" in st.session_state: st.success(st.session_state.pop("_confirm_all_email"))
