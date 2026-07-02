"""
In-memory PDF generator for the ED Productivity Dashboard (demo version).
Produces bytes (not a file) so it works on Streamlit Cloud.
"""
import io, random, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

# ── Colour palette ─────────────────────────────────────────────────────────────
C_BLUE        = "#185FA5"
C_BLUE_LIGHT  = "#E6F1FB"
C_BLUE_DOT    = "#378ADD"
C_ORANGE      = "#D4700A"
C_GREEN       = "#3B6D11";  C_GREEN_LIGHT  = "#EAF3DE"
C_AMBER       = "#854F0B";  C_AMBER_LIGHT  = "#FAEEDA"
C_RED         = "#993C1D";  C_RED_LIGHT    = "#FAECE7"
C_GRAY        = "#888780";  C_GRAY_LIGHT   = "#F1EFE8"
C_GRAY_DOT    = "#B4B2A9";  C_BORDER       = "#D3D1C7"
C_TEXT        = "#2C2C2A";  C_TEXT_MED     = "#5F5E5A"
C_TEXT_LIGHT  = "#B4B2A9"

QUADRANT_COLORS = {
    1: (C_GREEN, C_GREEN_LIGHT),
    2: (C_BLUE,  C_BLUE_LIGHT),
    3: (C_AMBER, C_AMBER_LIGHT),
    4: (C_RED,   C_RED_LIGHT),
}

_DEFAULT_QUADRANT_TITLES = {
    1: "Quadrant 1 — High Throughput / High Complexity",
    2: "Quadrant 2 — Lower Throughput / Higher Complexity",
    3: "Quadrant 3 — High Throughput / Lower Complexity",
    4: "Quadrant 4 — Lower Throughput / Lower Complexity",
}
_DEFAULT_QUADRANT_RECS = {
    1: (
        "Your metrics this period reflect strong performance across both patient volume and "
        "encounter complexity — you are above the group median on both dimensions, placing you "
        "among the highest overall wRVU generators in the department.",
        "Continue the workflows and documentation habits that are driving these results. "
        "Consider sharing throughput strategies with colleagues and monitor for sustainability "
        "as shift volume increases."
    ),
    2: (
        "Your documentation quality is a genuine strength — your wRVUs per encounter are above "
        "the group median, reflecting thorough capture of complexity, procedures, and acuity. "
        "The primary opportunity lies in patient throughput.",
        "Strategies worth exploring: parallel patient processing, earlier disposition planning, "
        "and reducing door-to-decision time. Even modest gains in encounters per hour will "
        "translate directly into higher total wRVU output given your documentation quality."
    ),
    3: (
        "You are seeing a high volume of patients — your encounters per hour are above the group "
        "median, which is a meaningful contribution to department capacity. The primary "
        "opportunity is in documentation and coding.",
        "Focus areas: capturing encounter complexity more fully, ensuring procedures are coded, "
        "and documenting critical care time when applicable. Small increases in average "
        "wRVUs per encounter have a large cumulative impact given the volume you already generate."
    ),
    4: (
        "Both patient throughput and encounter complexity metrics are below the group median "
        "this period. This combination represents the highest opportunity for growth in "
        "overall wRVU output.",
        "We would welcome a brief conversation to review your results in context — shift "
        "assignment, patient mix, and operational factors all matter and are worth discussing. "
        "Please reach out to schedule time with department leadership."
    ),
}

# Aliases kept for any legacy references
QUADRANT_RECS   = _DEFAULT_QUADRANT_RECS
QUADRANT_TITLES = _DEFAULT_QUADRANT_TITLES

# ── DEFAULTS dict — exported for 5_Templates.py ───────────────────────────────
DEFAULTS = {
    "q1_title": _DEFAULT_QUADRANT_TITLES[1],
    "q1_para1": _DEFAULT_QUADRANT_RECS[1][0],
    "q1_para2": _DEFAULT_QUADRANT_RECS[1][1],
    "q2_title": _DEFAULT_QUADRANT_TITLES[2],
    "q2_para1": _DEFAULT_QUADRANT_RECS[2][0],
    "q2_para2": _DEFAULT_QUADRANT_RECS[2][1],
    "q3_title": _DEFAULT_QUADRANT_TITLES[3],
    "q3_para1": _DEFAULT_QUADRANT_RECS[3][0],
    "q3_para2": _DEFAULT_QUADRANT_RECS[3][1],
    "q4_title": _DEFAULT_QUADRANT_TITLES[4],
    "q4_para1": _DEFAULT_QUADRANT_RECS[4][0],
    "q4_para2": _DEFAULT_QUADRANT_RECS[4][1],
    "email_subject":  "Your ED Productivity Report — {period}",
    "email_greeting": "Dear {firstname},",
    "email_body":     ("Please find attached your personalized ED productivity report for {period}. "
                       "Your report includes your individual metrics compared to the de-identified group."),
    "email_closing":  "Best regards,\nEmergency Medicine Analytics",
}


def load_templates_from_supabase() -> dict:
    """
    Fetch report_templates from Supabase. Returns an empty dict on any failure
    so callers always fall back to built-in defaults.
    """
    try:
        import os as _os
        from supabase import create_client
        url = _os.getenv("SUPABASE_URL", "")
        key = _os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            return {}
        sb  = create_client(url, key)
        res = sb.table("report_templates").select("key,value").execute()
        return {r["key"]: r["value"] for r in res.data} if res.data else {}
    except Exception:
        return {}


def _quartile_tag(val, p25, median, p75):
    if val >= p75:    return "Above 75th percentile",  C_GREEN,  C_GREEN_LIGHT
    if val >= median: return "Above median",            C_BLUE,   C_BLUE_LIGHT
    if val >= p25:    return "Below median",            C_AMBER,  C_AMBER_LIGHT
    return                   "Below 25th percentile",  C_RED,    C_RED_LIGHT


def _metric_card(ax, label, value, p25, median, p75):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_axis_off()
    tag_text, tag_fg, tag_bg = _quartile_tag(value, p25, median, p75)
    card = FancyBboxPatch((0.0, 0.0), 1.0, 1.0,
                          boxstyle="round,pad=0.02",
                          facecolor=C_GRAY_LIGHT, edgecolor=C_BORDER, linewidth=0.8,
                          transform=ax.transAxes, clip_on=False)
    ax.add_patch(card)
    ax.text(0.5, 0.82, label,           ha="center", va="center", fontsize=8,  color=C_TEXT_MED,
            transform=ax.transAxes)
    ax.text(0.5, 0.56, f"{value:.2f}",  ha="center", va="center", fontsize=19, color=C_TEXT,
            fontweight="bold", transform=ax.transAxes)
    ax.text(0.5, 0.37, f"Median {median:.2f}  ·  75th {p75:.2f}",
            ha="center", va="center", fontsize=7, color=C_TEXT_LIGHT, transform=ax.transAxes)
    pill = FancyBboxPatch((0.10, 0.08), 0.80, 0.20,
                          boxstyle="round,pad=0.02", facecolor=tag_bg, edgecolor="none",
                          transform=ax.transAxes, clip_on=False)
    ax.add_patch(pill)
    ax.text(0.5, 0.18, tag_text, ha="center", va="center",
            fontsize=7, color=tag_fg, fontweight="bold", transform=ax.transAxes)


def generate_pdf_bytes(provider_row, all_providers_df, report_period,
                       department_name="Emergency Department",
                       institution="University of Chicago Medicine",
                       templates: dict | None = None):
    """
    Build one provider PDF entirely in memory and return raw bytes.
    No file is written to disk — safe for Streamlit Cloud.
    templates: optional dict of verbiage overrides (keys: q1_title, q1_para1, etc.)
    """
    import math as _math

    # Resolve text from templates with fallback to built-in defaults
    _t = templates or {}
    def _tmpl(key, default):
        return _t.get(key, default)

    q_titles = {
        q: _tmpl(f"q{q}_title", _DEFAULT_QUADRANT_TITLES[q]) for q in [1, 2, 3, 4]
    }
    q_recs = {
        q: (_tmpl(f"q{q}_para1", _DEFAULT_QUADRANT_RECS[q][0]),
            _tmpl(f"q{q}_para2", _DEFAULT_QUADRANT_RECS[q][1]))
        for q in [1, 2, 3, 4]
    }

    prov      = provider_row
    df        = all_providers_df
    firstname = prov["provider_name"].split(",")[1].strip() \
                if "," in prov["provider_name"] else prov["provider_name"]

    # ── Figure ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(8.5, 11), facecolor="white")

    # ── Layout constants ──────────────────────────────────────────────────────
    _L  = 0.07
    _W  = 0.86
    _cg = 0.018
    _cw = (_W - 2 * _cg) / 3

    _hdr_b  = 0.805;  _hdr_h  = 0.128
    _card_b = 0.692;  _card_h = 0.100
    _rec_b  = 0.543;  _rec_h  = 0.137
    _ch_h   = 0.422
    _ch_b   = 0.075

    _bar_l  = 0.15
    _bar_w  = 0.370
    _sc_gap = 0.020
    _sc_l   = _bar_l + _bar_w + _sc_gap
    _sc_w   = (_L + _W) - _sc_l

    # ── Create axes ───────────────────────────────────────────────────────────
    ax_hdr = fig.add_axes([_L,              _hdr_b,  _W,     _hdr_h])
    ax_c   = [
        fig.add_axes([_L + i * (_cw + _cg), _card_b, _cw,    _card_h])
        for i in range(3)
    ]
    ax_rec = fig.add_axes([_L,              _rec_b,  _W,     _rec_h])
    ax_bar = fig.add_axes([_bar_l,          _ch_b,   _bar_w, _ch_h])
    ax_sc  = fig.add_axes([_sc_l,           _ch_b,   _sc_w,  _ch_h])

    # ── Header ────────────────────────────────────────────────────────────────
    ax_hdr.set_xlim(0, 1); ax_hdr.set_ylim(0, 1); ax_hdr.set_axis_off()
    ax_hdr.add_patch(FancyBboxPatch((0, 0.76), 1.0, 0.24,
                     boxstyle="square,pad=0", facecolor=C_BLUE, edgecolor="none",
                     transform=ax_hdr.transAxes))
    ax_hdr.text(0.02, 0.87, "ED PRODUCTIVITY REPORT",
                color="white", fontsize=8.5, fontweight="bold", va="center",
                transform=ax_hdr.transAxes)
    ax_hdr.text(0.98, 0.87, report_period,
                color="white", fontsize=8, va="center", ha="right",
                transform=ax_hdr.transAxes)
    ax_hdr.text(0.02, 0.53, prov["provider_name"],
                color=C_TEXT, fontsize=17, fontweight="bold", va="center",
                transform=ax_hdr.transAxes)
    ax_hdr.text(0.02, 0.30, f"{department_name}  ·  {institution}",
                color=C_TEXT_MED, fontsize=8, va="center",
                transform=ax_hdr.transAxes)

    _s = prov.get("shifts_worked", float("nan"))
    _h = prov.get("hours_worked",  float("nan"))
    try:
        _shift_part = f"{int(_s)} shifts  ·  {float(_h):.0f} hrs  ·  " \
                      if not _math.isnan(float(_s)) else ""
    except Exception:
        _shift_part = ""

    ax_hdr.text(0.02, 0.10,
                f"{_shift_part}{int(prov['encounter_count']):,} encounters"
                f"  ·  {prov['total_wrvu']:,.0f} total wRVUs",
                color=C_TEXT_LIGHT, fontsize=7.5, va="center",
                transform=ax_hdr.transAxes)
    ax_hdr.axhline(0.0, color=C_BORDER, linewidth=0.8)

    # ── Metric cards ──────────────────────────────────────────────────────────
    _has_shifts = (
        "wrvu_per_hour" in prov.index
        and not _math.isnan(float(prov.get("wrvu_per_hour", float("nan"))))
    )
    _metric_list = (
        [("wRVUs per Hour",       "wrvu_per_hour"),
         ("Encounters per Hour",  "encounters_per_hour"),
         ("wRVUs per Encounter",  "wrvu_per_encounter")]
        if _has_shifts else
        [("wRVUs per Encounter",  "wrvu_per_encounter"),
         ("Encounters / Month",   "encounters_per_month"),
         ("Total wRVUs",          "total_wrvu")]
    )
    for i, (lbl, metric) in enumerate(_metric_list):
        p25_v = prov.get(f"{metric}_p25",    prov[metric])
        med_v = prov.get(f"{metric}_median", prov[metric])
        p75_v = prov.get(f"{metric}_p75",    prov[metric])
        _metric_card(ax_c[i], lbl, float(prov[metric]),
                     float(p25_v), float(med_v), float(p75_v))

    # ── Quadrant recommendation ───────────────────────────────────────────────
    ax_rec.set_xlim(0, 1); ax_rec.set_ylim(0, 1); ax_rec.set_axis_off()
    q = int(prov["quadrant"])
    fg, bg = QUADRANT_COLORS[q]
    p1, p2 = q_recs[q]
    ax_rec.add_patch(FancyBboxPatch((0, 0), 1.0, 1.0,
                     boxstyle="round,pad=0.015", facecolor=bg, edgecolor=fg, linewidth=0.8,
                     transform=ax_rec.transAxes))
    ax_rec.add_patch(FancyBboxPatch((0, 0), 0.007, 1.0,
                     boxstyle="square,pad=0", facecolor=fg, edgecolor="none",
                     transform=ax_rec.transAxes))
    ax_rec.text(0.018, 0.84, q_titles[q],
                color=fg, fontsize=8, fontweight="bold", va="center",
                transform=ax_rec.transAxes)
    ax_rec.text(0.018, 0.57, textwrap.fill(p1, width=118),
                color=C_TEXT, fontsize=6.8, va="center", linespacing=1.4,
                transform=ax_rec.transAxes)
    ax_rec.text(0.018, 0.22, textwrap.fill(p2, width=118),
                color=C_TEXT, fontsize=6.8, va="center", linespacing=1.4,
                transform=ax_rec.transAxes)

    # ── Bar chart ─────────────────────────────────────────────────────────────
    _bc_col = "wrvu_per_hour" if _has_shifts else "wrvu_per_encounter"
    _bc_lbl = "wRVUs per Hour" if _has_shifts else "wRVUs per Encounter"
    sorted_df = df.sort_values(_bc_col, ascending=True).reset_index(drop=True)
    n_others  = len(sorted_df) - 1
    anon      = [f"Provider {i+1:02d}" for i in range(n_others)]
    random.seed(hash(prov["provider_name"]) % (2**31))
    random.shuffle(anon)
    labels, colors, edges, anon_idx = [], [], [], 0
    for _, row in sorted_df.iterrows():
        if row["provider_name"] == prov["provider_name"]:
            labels.append(f"► {firstname}"); colors.append(C_BLUE); edges.append(C_BLUE)
        else:
            labels.append(anon[anon_idx]); colors.append(C_GRAY_LIGHT); edges.append(C_BORDER)
            anon_idx += 1
    vals = sorted_df[_bc_col].values
    ax_bar.barh(range(len(labels)), vals, color=colors, edgecolor=edges,
                linewidth=0.5, height=0.72)
    n = len(labels)
    for val, lbl, color, y_frac in [
        (prov[f"{_bc_col}_p25"],    "25th\n{:.2f}",   C_AMBER, 0.96),
        (prov[f"{_bc_col}_median"], "Median\n{:.2f}", C_BLUE,  0.84),
        (prov[f"{_bc_col}_p75"],    "75th\n{:.2f}",   C_GREEN, 0.72),
    ]:
        ax_bar.axvline(val, color=color, linewidth=1.3, linestyle="--", alpha=0.85, zorder=3)
        ax_bar.text(val + 0.05, n * y_frac, lbl.format(val),
                    color=color, fontsize=6, va="top", fontweight="bold", linespacing=1.2,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=1.5))
    ax_bar.set_yticks(range(len(labels)))
    ax_bar.set_yticklabels(labels, fontsize=6.2)
    for tick, lbl in zip(ax_bar.get_yticklabels(), labels):
        if lbl.startswith("►"):
            tick.set_color(C_BLUE); tick.set_fontweight("bold")
    ax_bar.set_xlabel(_bc_lbl, fontsize=8, color=C_TEXT_MED, labelpad=6)
    ax_bar.set_title(f"{_bc_lbl} — Group Comparison\n(all other providers de-identified)",
                     fontsize=8.5, color=C_TEXT, loc="left", fontweight="bold", pad=6)
    ax_bar.set_xlim(0, max(vals) * 1.16)
    ax_bar.tick_params(axis="x", labelsize=7, colors=C_TEXT_MED, pad=4)
    ax_bar.tick_params(axis="y", pad=3)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.spines[["left", "bottom"]].set_edgecolor(C_BORDER)
    ax_bar.grid(axis="x", color=C_BORDER, linewidth=0.5, alpha=0.7)

    # ── Scatter plot ──────────────────────────────────────────────────────────
    others   = df[df["provider_name"] != prov["provider_name"]]
    _sc_xcol = "encounters_per_hour" if _has_shifts else "encounters_per_month"
    _sc_xlbl = "Encounters per Hour" if _has_shifts else "Encounters / Month"
    enc_all  = df[_sc_xcol].dropna().values
    rpu_all  = df["wrvu_per_encounter"].dropna().values
    x_pad = (enc_all.max() - enc_all.min()) * 0.12
    y_pad = (rpu_all.max() - rpu_all.min()) * 0.12
    x_min = max(0, enc_all.min() - x_pad)
    x_max = enc_all.max() + x_pad
    y_min = max(0, rpu_all.min() - y_pad)
    y_max = rpu_all.max() + y_pad
    x_min = min(x_min, float(prov[_sc_xcol]) - x_pad)
    x_max = max(x_max, float(prov[_sc_xcol]) + x_pad)
    y_min = min(y_min, float(prov["wrvu_per_encounter"]) - y_pad)
    y_max = max(y_max, float(prov["wrvu_per_encounter"]) + y_pad)
    ax_sc.scatter(others[_sc_xcol], others["wrvu_per_encounter"],
                  color=C_BLUE_DOT, alpha=0.45, s=30, zorder=2)
    enc_med = prov[f"{_sc_xcol}_median"]
    rpu_med = prov["wrvu_per_encounter_median"]
    ax_sc.axvline(enc_med, color=C_ORANGE, linewidth=1.4, linestyle="--", alpha=0.9, zorder=3)
    ax_sc.axhline(rpu_med, color=C_ORANGE, linewidth=1.4, linestyle="--", alpha=0.9, zorder=3)
    prov_q_color = QUADRANT_COLORS[q][0]
    ax_sc.scatter(prov[_sc_xcol], prov["wrvu_per_encounter"],
                  color=prov_q_color, edgecolors="white", s=100, linewidth=2, zorder=5)
    ax_sc.annotate(firstname,
                   (prov[_sc_xcol], prov["wrvu_per_encounter"]),
                   textcoords="offset points", xytext=(8, 5),
                   fontsize=8, color=prov_q_color, fontweight="bold")
    ax_sc.set_xlim(x_min, x_max); ax_sc.set_ylim(y_min, y_max)
    corner_labels = {
        1: ("High Throughput\nHigh Complexity",    x_max, y_max, "right", "top"),
        2: ("Lower Throughput\nHigher Complexity",  x_min, y_max, "left",  "top"),
        3: ("High Throughput\nLower Complexity",    x_max, y_min, "right", "bottom"),
        4: ("Lower Throughput\nLower Complexity",   x_min, y_min, "left",  "bottom"),
    }
    for q_num, (label, cx, cy, ha, va) in corner_labels.items():
        is_active = (q_num == q)
        ax_sc.text(cx, cy, label, fontsize=6, ha=ha, va=va, linespacing=1.3,
                   color=QUADRANT_COLORS[q_num][0] if is_active else C_TEXT_LIGHT,
                   fontweight="bold" if is_active else "normal", style="italic",
                   transform=ax_sc.transData)
    ax_sc.set_xlabel(f"{_sc_xlbl} →", fontsize=7.5, color=C_TEXT_MED, labelpad=6)
    ax_sc.set_ylabel("wRVUs per Encounter →", fontsize=7.5, color=C_TEXT_MED, labelpad=4)
    ax_sc.set_title("Provider Throughput vs.\nEncounter Complexity",
                    fontsize=8.5, color=C_TEXT, loc="left", fontweight="bold", pad=6)
    ax_sc.tick_params(labelsize=7, colors=C_TEXT_MED, pad=3)
    ax_sc.spines[["top", "right"]].set_visible(False)
    ax_sc.spines[["left", "bottom"]].set_edgecolor(C_BORDER)
    ax_sc.grid(color=C_BORDER, linewidth=0.4, alpha=0.6)

    # ── Footer ────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.028,
             f"Confidential — intended solely for {prov['provider_name']}  ·  "
             f"All other provider data has been de-identified  ·  "
             f"Questions? Contact your department administrator.",
             fontsize=6, color=C_TEXT_LIGHT, va="bottom", ha="center")

    # ── Render to bytes ───────────────────────────────────────────────────────
    buf = io.BytesIO()
    plt.savefig(buf, format="pdf", dpi=150, facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
