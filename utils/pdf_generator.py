# =============================================================================
#  utils/pdf_generator.py — DEMO version
#  Generates a provider productivity report PDF using reportlab + matplotlib.
# =============================================================================
import io, math
import numpy as np
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, Image as RLImage)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Brand colours ─────────────────────────────────────────────────────────────
MAROON  = HexColor("#800000")
BLUE    = HexColor("#185FA5")
GREEN   = HexColor("#3B6D11")
AMBER   = HexColor("#854F0B")
RED     = HexColor("#993C1D")
ORANGE  = HexColor("#D4700A")
LGRAY   = HexColor("#F5F3EE")
MGRAY   = HexColor("#B4B2A9")
DGRAY   = HexColor("#2C2C2A")

QCOLORS = {1: HexColor("#3B6D11"), 2: HexColor("#185FA5"),
           3: HexColor("#854F0B"), 4: HexColor("#993C1D")}
QBGS    = {1: HexColor("#EAF3DE"), 2: HexColor("#E6F1FB"),
           3: HexColor("#FAEEDA"), 4: HexColor("#FAECE7")}

QHEX    = {1: "#3B6D11", 2: "#185FA5", 3: "#854F0B", 4: "#993C1D"}
QBGHEX  = {1: "#EAF3DE", 2: "#E6F1FB", 3: "#FAEEDA", 4: "#FAECE7"}

DEFAULTS = {
    "q1_title": "Quadrant 1 — High Throughput / High Complexity",
    "q1_para1": ("Your metrics this period reflect strong performance across both patient volume and "
                 "encounter complexity — you are above the group median on both dimensions."),
    "q1_para2": ("Continue the workflows and documentation habits driving these results. "
                 "Consider sharing throughput strategies with colleagues and monitor for sustainability."),
    "q2_title": "Quadrant 2 — Lower Throughput / Higher Complexity",
    "q2_para1": ("Your documentation quality is a genuine strength — your wRVUs per encounter are "
                 "above the group median, reflecting thorough capture of complexity and acuity."),
    "q2_para2": ("Strategies worth exploring: parallel patient processing, earlier disposition "
                 "planning, and reducing door-to-decision time."),
    "q3_title": "Quadrant 3 — High Throughput / Lower Complexity",
    "q3_para1": ("You are seeing a high volume of patients — your encounter rate is above the group "
                 "median, a meaningful contribution to department capacity."),
    "q3_para2": ("Focus areas: capturing encounter complexity more fully, ensuring procedures are "
                 "coded, and documenting critical care time when applicable."),
    "q4_title": "Quadrant 4 — Lower Throughput / Lower Complexity",
    "q4_para1": ("Both patient throughput and encounter complexity metrics are below the group "
                 "median this period — the highest opportunity for growth in overall wRVU output."),
    "q4_para2": ("We would welcome a brief conversation to review your results in context — shift "
                 "assignment, patient mix, and operational factors all matter."),
    "email_subject":  "Your ED Productivity Report — {period}",
    "email_greeting": "Dear {firstname},",
    "email_body":     ("Please find attached your personalized ED productivity report for {period}. "
                       "Your report includes your individual metrics compared to the de-identified group."),
    "email_closing":  "Best regards,\nEmergency Medicine Analytics",
}


def _pct_rank(value, series):
    """Return percentile rank 0–100 of value within series."""
    valid = series.dropna()
    if valid.empty:
        return 50
    return round(100 * (valid < value).sum() / len(valid))


def _make_charts_png(row, df, fig_w=7.2, fig_h=2.8):
    """
    Build a 2-panel matplotlib figure (scatter + bar) and return PNG bytes.
    Returns None on failure (charts become optional).
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        throughput_col = (df["throughput_col"].iloc[0]
                          if "throughput_col" in df.columns
                          else "encounters_per_month")
        has_hour  = (throughput_col == "encounters_per_hour")
        x_label   = "Encounters / Hour" if has_hour else "Encounters / Month"
        quadrant  = int(row.get("quadrant", 4))
        qhex      = QHEX[quadrant]
        qbghex    = QBGHEX[quadrant]

        fig, (ax1, ax2) = plt.subplots(
            1, 2, figsize=(fig_w, fig_h),
            gridspec_kw={"width_ratios": [1.1, 0.9]},
        )
        fig.patch.set_facecolor("white")

        # ── Left: scatter ─────────────────────────────────────────────────────
        x_all  = df[throughput_col]
        y_all  = df["wrvu_per_encounter"]
        med_x  = x_all.median()
        med_y  = y_all.median()

        ax1.scatter(x_all, y_all, color="#B4B2A9", s=22, alpha=0.55, zorder=2)
        ax1.scatter(
            [row[throughput_col]], [row["wrvu_per_encounter"]],
            color=qhex, s=90, zorder=5,
            edgecolors="white", linewidths=1.2,
        )
        ax1.axvline(med_x, color="#D4700A", linestyle="--", linewidth=0.9, alpha=0.75)
        ax1.axhline(med_y, color="#D4700A", linestyle="--", linewidth=0.9, alpha=0.75)

        # Quadrant corner labels
        xpad = (x_all.max() - x_all.min()) * 0.04
        ypad = (y_all.max() - y_all.min()) * 0.04
        ax1.set_xlim(x_all.min() - xpad, x_all.max() + xpad)
        ax1.set_ylim(y_all.min() - ypad, y_all.max() + ypad)
        xl, xr = ax1.get_xlim()
        yb, yt = ax1.get_ylim()
        q_labels = {1: ("right","top","#3B6D11"), 2: ("left","top","#185FA5"),
                    3: ("right","bottom","#854F0B"), 4: ("left","bottom","#993C1D")}
        q_pos = {1: (xr, yt), 2: (xl, yt), 3: (xr, yb), 4: (xl, yb)}
        for q, (ha, va, clr) in q_labels.items():
            px, py = q_pos[q]
            ax1.text(px, py, f"Q{q}", ha=ha, va=va, fontsize=6.5,
                     color=clr, fontweight="bold", alpha=0.8)

        ax1.set_xlabel(x_label, fontsize=7)
        ax1.set_ylabel("wRVU / Encounter", fontsize=7)
        ax1.tick_params(labelsize=6)
        ax1.set_facecolor("#F9F8F5")
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)
        ax1.set_title("Quadrant Position", fontsize=8, fontweight="bold",
                      color="#2C2C2A", pad=4)

        # ── Right: horizontal bar (providers anonymous) ───────────────────────
        bar_metric = ("wrvu_per_hour"
                      if (has_hour
                          and "wrvu_per_hour" in df.columns
                          and df["wrvu_per_hour"].notna().any())
                      else "wrvu_per_encounter")
        bar_label = "wRVU / Hour" if bar_metric == "wrvu_per_hour" else "wRVU / Encounter"

        sorted_df = df.sort_values(bar_metric, ascending=True).reset_index(drop=True)
        n = len(sorted_df)
        prov_idxs = sorted_df.index[
            sorted_df["provider_name"] == row["provider_name"]
        ].tolist()
        prov_idx = prov_idxs[0] if prov_idxs else 0

        bar_colors = [
            qhex if r["provider_name"] == row["provider_name"] else "#CFCDC6"
            for _, r in sorted_df.iterrows()
        ]
        ax2.barh(range(n), sorted_df[bar_metric], color=bar_colors, height=0.75)

        # Annotate highlighted bar
        prov_val = sorted_df.loc[prov_idx, bar_metric]
        ax2.text(
            prov_val + sorted_df[bar_metric].max() * 0.02,
            prov_idx,
            f"{prov_val:.2f}",
            va="center", fontsize=6, color=qhex, fontweight="bold",
        )

        # Median + percentile lines
        med_bar = sorted_df[bar_metric].median()
        p25_bar = sorted_df[bar_metric].quantile(0.25)
        p75_bar = sorted_df[bar_metric].quantile(0.75)
        for val, clr, lw, lab in [
            (p25_bar, "#854F0B", 0.7, "25th"),
            (med_bar, "#D4700A", 1.0, "Median"),
            (p75_bar, "#3B6D11", 0.7, "75th"),
        ]:
            ax2.axvline(val, color=clr, linestyle="--", linewidth=lw, alpha=0.8)
            ax2.text(val, n * 0.97, lab, ha="center", va="top",
                     fontsize=4.5, color=clr)

        ax2.set_yticks([])
        ax2.set_xlabel(bar_label, fontsize=7)
        ax2.tick_params(axis="x", labelsize=6)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        ax2.set_facecolor("white")
        rank_from_top = n - prov_idx
        ax2.set_title(
            f"Group Ranking  (#{rank_from_top} of {n})",
            fontsize=8, fontweight="bold", color="#2C2C2A", pad=4,
        )

        plt.tight_layout(pad=0.6, w_pad=1.2)
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, facecolor="white")
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception:
        return None


def generate_pdf_bytes(row, df,
                       report_period="",
                       department_name="Emergency Medicine",
                       institution="University of Chicago Medicine",
                       templates=None) -> bytes:
    """Build a provider productivity PDF and return raw bytes."""
    tpl = dict(DEFAULTS)
    if templates:
        tpl.update(templates)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.5*inch,   bottomMargin=0.6*inch,
    )
    W = letter[0] - 1.3*inch   # content width in points (~518 pt = 7.2 in)

    styles = getSampleStyleSheet()

    def sty(name, **kw):
        base = kw.pop("parent", "Normal")
        return ParagraphStyle(name, parent=styles[base], **kw)

    s_normal  = sty("sn",  fontSize=9,  leading=13, textColor=DGRAY)
    s_small   = sty("ss",  fontSize=8,  leading=11, textColor=DGRAY)
    s_caption = sty("sc",  fontSize=7.5,leading=10, textColor=MGRAY)
    s_bold    = sty("sb",  fontSize=9,  leading=13, textColor=DGRAY, fontName="Helvetica-Bold")
    s_h2      = sty("sh2", fontSize=12, leading=16, textColor=DGRAY, fontName="Helvetica-Bold")
    s_metric  = sty("sm",  fontSize=18, leading=22, textColor=MAROON, fontName="Helvetica-Bold",
                    alignment=TA_CENTER)
    s_mlabel  = sty("sml", fontSize=7.5,leading=10, textColor=MGRAY,  alignment=TA_CENTER)
    s_white   = sty("sw",  fontSize=9,  leading=13, textColor=white)
    s_white_b = sty("swb", fontSize=14, leading=18, textColor=white, fontName="Helvetica-Bold")

    provider = row.get("provider_name", "Provider")
    quadrant = int(row.get("quadrant", 4))
    qcolor   = QCOLORS[quadrant]
    qbg      = QBGS[quadrant]

    q_title = tpl.get(f"q{quadrant}_title", "")
    q_para1 = tpl.get(f"q{quadrant}_para1", "")
    q_para2 = tpl.get(f"q{quadrant}_para2", "")

    # Format name display
    if "," in provider:
        last, first = provider.split(",", 1)
        display_name = f"{first.strip()} {last.strip()}"
    else:
        display_name = provider

    story = []

    # ── Header bar ────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(f"<b>{display_name}</b>", s_white_b),
        Paragraph(f"{institution} · {department_name}", s_white),
        Paragraph(report_period,
                  sty("srp", fontSize=9, leading=13, textColor=white, alignment=TA_RIGHT)),
    ]]
    ht = Table(header_data, colWidths=[W*0.4, W*0.4, W*0.2])
    ht.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), MAROON),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0), (-1,-1), 10),
        ("LEFTPADDING",  (0,0), (0,-1),  14),
        ("RIGHTPADDING", (-1,0),(-1,-1), 14),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.16*inch))

    # ── Key metrics ───────────────────────────────────────────────────────────
    encs   = int(row.get("encounter_count", 0))
    wrvus  = row.get("total_wrvu", 0)
    rpu    = row.get("wrvu_per_encounter", 0)
    epm    = row.get("encounters_per_month", 0)
    n_mo   = int(row.get("n_months", 1))
    rank   = int(row.get("rank", 1))
    n_prov = len(df)

    # ShiftAdmin metrics (optional)
    has_shifts = ("wrvu_per_hour" in df.columns and df["wrvu_per_hour"].notna().any())
    wph   = row.get("wrvu_per_hour", None)
    eph   = row.get("encounters_per_hour", None)
    shfts = row.get("shifts_worked", None)
    hrs   = row.get("hours_worked", None)

    med_rpu = df["wrvu_per_encounter"].median()
    med_epm = df["encounters_per_month"].median()

    def delta(val, med):
        pct  = ((val - med) / med * 100) if med else 0
        sign = "+" if pct >= 0 else ""
        clr  = "#3B6D11" if pct >= 0 else "#993C1D"
        return f"<font color='{clr}'>{sign}{pct:.1f}% vs median</font>"

    if has_shifts and wph is not None and not math.isnan(float(wph)):
        # 6-column metrics with ShiftAdmin data
        col_w = W / 6
        metrics = [
            [Paragraph(f"{encs:,}", s_metric),
             Paragraph(f"{wrvus:,.1f}", s_metric),
             Paragraph(f"{rpu:.2f}", s_metric),
             Paragraph(f"{epm:.1f}", s_metric),
             Paragraph(f"{float(wph):.2f}", s_metric),
             Paragraph(f"{int(shfts) if shfts else '—'}", s_metric)],
            [Paragraph("Encounters",        s_mlabel),
             Paragraph("Total wRVUs",       s_mlabel),
             Paragraph("wRVU / Enc",        s_mlabel),
             Paragraph("Enc / Month",       s_mlabel),
             Paragraph("wRVU / Hour",       s_mlabel),
             Paragraph("Shifts",            s_mlabel)],
            [Paragraph(f"<font size=7>{n_mo}-mo</font>",
                       sty("s7a", fontSize=7, leading=10, textColor=MGRAY, alignment=TA_CENTER)),
             Paragraph(f"<font size=7>{n_mo}-mo</font>",
                       sty("s7b", fontSize=7, leading=10, textColor=MGRAY, alignment=TA_CENTER)),
             Paragraph(delta(rpu, med_rpu),
                       sty("sd1", fontSize=7, leading=10, alignment=TA_CENTER)),
             Paragraph(delta(epm, med_epm),
                       sty("sd2", fontSize=7, leading=10, alignment=TA_CENTER)),
             Paragraph("", sty("sd3", fontSize=7, leading=10, alignment=TA_CENTER)),
             Paragraph("", sty("sd4", fontSize=7, leading=10, alignment=TA_CENTER))],
        ]
        mt = Table(metrics, colWidths=[col_w]*6)
    else:
        # 4-column metrics — profee cube only
        col_w = W / 4
        metrics = [
            [Paragraph(f"{encs:,}", s_metric),
             Paragraph(f"{wrvus:,.1f}", s_metric),
             Paragraph(f"{rpu:.2f}", s_metric),
             Paragraph(f"{epm:.1f}", s_metric)],
            [Paragraph("Encounters",        s_mlabel),
             Paragraph("Total wRVUs",       s_mlabel),
             Paragraph("wRVU / Encounter",  s_mlabel),
             Paragraph("Encounters / Month",s_mlabel)],
            [Paragraph(f"<font size=7>{n_mo}-month period</font>",
                       sty("s7c", fontSize=7, leading=10, textColor=MGRAY, alignment=TA_CENTER)),
             Paragraph(f"<font size=7>{n_mo}-month period</font>",
                       sty("s7d", fontSize=7, leading=10, textColor=MGRAY, alignment=TA_CENTER)),
             Paragraph(delta(rpu, med_rpu),
                       sty("sd5", fontSize=7.5, leading=10, alignment=TA_CENTER)),
             Paragraph(delta(epm, med_epm),
                       sty("sd6", fontSize=7.5, leading=10, alignment=TA_CENTER))],
        ]
        mt = Table(metrics, colWidths=[col_w]*4)

    mt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), LGRAY),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",        (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",   (0,0), (-1,0),  10),
        ("BOTTOMPADDING",(0,-1),(-1,-1), 8),
        ("TOPPADDING",   (0,1), (-1,1),  2),
        ("LINEAFTER",    (0,0), (-2,-1), 0.5, HexColor("#D3D1C7")),
        ("BOX",          (0,0), (-1,-1), 0.5, HexColor("#D3D1C7")),
    ]))
    story.append(mt)
    story.append(Spacer(1, 0.14*inch))

    # ── Charts: scatter + bar ─────────────────────────────────────────────────
    fig_h_in = 2.8
    fig_w_in = W / inch   # ~7.2 inches
    charts_buf = _make_charts_png(row, df, fig_w=fig_w_in, fig_h=fig_h_in)
    if charts_buf is not None:
        story.append(RLImage(charts_buf, width=W, height=W * fig_h_in / fig_w_in))
        story.append(Spacer(1, 0.12*inch))

    # ── Rank bar ──────────────────────────────────────────────────────────────
    story.append(Paragraph("<b>Percentile Rank</b> (wRVU / Encounter)", s_bold))
    story.append(Spacer(1, 0.04*inch))

    rank_pct = _pct_rank(rpu, df["wrvu_per_encounter"])
    rank_row = [[
        Paragraph(f"Rank <b>{rank}</b> of {n_prov}", s_normal),
        Paragraph(f"<b>{rank_pct}th</b> percentile",
                  sty("srk", fontSize=9, leading=13, textColor=DGRAY, alignment=TA_RIGHT)),
    ]]
    rt = Table(rank_row, colWidths=[W*0.5, W*0.5])
    rt.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(rt)

    fill_w  = max(4, W * rank_pct / 100)
    bar_row = [["", ""]]
    bt = Table(bar_row, colWidths=[fill_w, W - fill_w], rowHeights=[8])
    bt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (0,0), qcolor),
        ("BACKGROUND",    (1,0), (1,0), HexColor("#D3D1C7")),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
    ]))
    story.append(bt)
    story.append(Spacer(1, 0.14*inch))

    # ── Quadrant placement ────────────────────────────────────────────────────
    story.append(Paragraph("<b>Quadrant Placement</b>", s_bold))
    story.append(Spacer(1, 0.05*inch))

    qlabels = {
        1: "High Throughput / High Complexity",
        2: "Lower Throughput / Higher Complexity",
        3: "High Throughput / Lower Complexity",
        4: "Lower Throughput / Lower Complexity",
    }
    q_data = [[
        Paragraph(f"<b>Q{quadrant}</b>",
                  sty("sqn", fontSize=13, leading=17, textColor=qcolor,
                      fontName="Helvetica-Bold")),
        Paragraph(qlabels[quadrant],
                  sty("sql", fontSize=9, leading=13, textColor=qcolor)),
        Paragraph(
            f"<b>Throughput</b> {'▲ Above' if quadrant in (1,3) else '▼ Below'} median  "
            f"<b>Complexity</b> {'▲ Above' if quadrant in (1,2) else '▼ Below'} median",
            sty("sqd", fontSize=7.5, leading=11, textColor=DGRAY, alignment=TA_RIGHT)
        ),
    ]]
    qt = Table(q_data, colWidths=[W*0.08, W*0.52, W*0.4])
    qt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), qbg),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ("LEFTPADDING",  (0,0), (0,0),   10),
        ("RIGHTPADDING", (-1,0),(-1,0),  10),
        ("LINEAFTER",    (0,0), (1,-1),  0.5, qcolor),
        ("BOX",          (0,0), (-1,-1), 1,   qcolor),
    ]))
    story.append(qt)
    story.append(Spacer(1, 0.14*inch))

    # ── Recommendation box ────────────────────────────────────────────────────
    story.append(Paragraph("<b>Feedback &amp; Recommendations</b>", s_bold))
    story.append(Spacer(1, 0.05*inch))

    rec_data = [
        [Paragraph(f"<b>{q_title}</b>",
                   sty("sqt", fontSize=9, leading=13, textColor=qcolor,
                       fontName="Helvetica-Bold"))],
        [Paragraph(q_para1, sty("sqp1", fontSize=8.5, leading=13, textColor=DGRAY))],
        [Paragraph(q_para2, sty("sqp2", fontSize=8.5, leading=13, textColor=DGRAY))],
    ]
    rxt = Table(rec_data, colWidths=[W])
    rxt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), qbg),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,-1),(-1,-1), 8),
        ("LEFTPADDING",  (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("LINEBEFORE",   (0,0), (0,-1),  4, qcolor),
        ("BOX",          (0,0), (-1,-1), 0.5, qcolor),
    ]))
    story.append(rxt)
    story.append(Spacer(1, 0.18*inch))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=HexColor("#D3D1C7")))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "All provider comparisons in this report are fully de-identified. "
        "Metrics are sourced from the profee billing cube and shift scheduling system. "
        "Questions? Contact ed.leadership@demo.com.",
        s_caption,
    ))

    doc.build(story)
    return buf.getvalue()
