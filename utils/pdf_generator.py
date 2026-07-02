# =============================================================================
#  utils/pdf_generator.py — DEMO version
#  Generates a single-page provider productivity report PDF using reportlab.
# =============================================================================
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import io, math

# ── Brand colours ─────────────────────────────────────────────────────────────
MAROON  = HexColor("#800000")
BLUE    = HexColor("#185FA5")
GREEN   = HexColor("#3B6D11")
AMBER   = HexColor("#854F0B")
RED     = HexColor("#993C1D")
LGRAY   = HexColor("#F5F3EE")
MGRAY   = HexColor("#B4B2A9")
DGRAY   = HexColor("#2C2C2A")

QCOLORS = {1: HexColor("#3B6D11"), 2: HexColor("#185FA5"),
           3: HexColor("#854F0B"), 4: HexColor("#993C1D")}
QBGS    = {1: HexColor("#EAF3DE"), 2: HexColor("#E6F1FB"),
           3: HexColor("#FAEEDA"), 4: HexColor("#FAECE7")}

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
    if valid.empty: return 50
    return round(100 * (valid < value).sum() / len(valid))


def generate_pdf_bytes(row, df,
                       report_period="",
                       department_name="Emergency Medicine",
                       institution="University of Chicago Medicine",
                       templates=None) -> bytes:
    """
    Build a provider productivity PDF and return raw bytes.
    """
    tpl = dict(DEFAULTS)
    if templates:
        tpl.update(templates)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.5*inch,   bottomMargin=0.6*inch,
    )

    W = letter[0] - 1.3*inch   # content width

    styles = getSampleStyleSheet()

    # Custom styles
    def sty(name, **kw):
        base = kw.pop("parent", "Normal")
        s = ParagraphStyle(name, parent=styles[base], **kw)
        return s

    s_normal  = sty("sn",  fontSize=9,  leading=13, textColor=DGRAY)
    s_small   = sty("ss",  fontSize=8,  leading=11, textColor=DGRAY)
    s_caption = sty("sc",  fontSize=7.5,leading=10, textColor=MGRAY)
    s_bold    = sty("sb",  fontSize=9,  leading=13, textColor=DGRAY, fontName="Helvetica-Bold")
    s_h2      = sty("sh2", fontSize=12, leading=16, textColor=DGRAY, fontName="Helvetica-Bold")
    s_metric  = sty("sm",  fontSize=18, leading=22, textColor=MAROON, fontName="Helvetica-Bold", alignment=TA_CENTER)
    s_mlabel  = sty("sml", fontSize=7.5,leading=10, textColor=MGRAY,  alignment=TA_CENTER)
    s_white   = sty("sw",  fontSize=9,  leading=13, textColor=white)
    s_white_b = sty("swb", fontSize=14, leading=18, textColor=white, fontName="Helvetica-Bold")
    s_center  = sty("sctr",fontSize=9,  leading=13, textColor=DGRAY, alignment=TA_CENTER)

    provider = row.get("provider_name", "Provider")
    quadrant = int(row.get("quadrant", 4))
    qcolor   = QCOLORS[quadrant]
    qbg      = QBGS[quadrant]

    q_title = tpl.get(f"q{quadrant}_title", "")
    q_para1 = tpl.get(f"q{quadrant}_para1", "")
    q_para2 = tpl.get(f"q{quadrant}_para2", "")

    # Format name: "Last, First" → "First Last" for display
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
        Paragraph(report_period, sty("srp", fontSize=9, leading=13, textColor=white, alignment=TA_RIGHT)),
    ]]
    ht = Table(header_data, colWidths=[W*0.4, W*0.4, W*0.2])
    ht.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), MAROON),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",  (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING", (0,0), (0,-1), 14),
        ("RIGHTPADDING",(-1,0),(-1,-1),14),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.18*inch))

    # ── Key metrics ───────────────────────────────────────────────────────────
    encs   = int(row.get("encounter_count", 0))
    wrvus  = row.get("total_wrvu", 0)
    rpu    = row.get("wrvu_per_encounter", 0)
    epm    = row.get("encounters_per_month", 0)
    n_mo   = int(row.get("n_months", 1))
    rank   = int(row.get("rank", 1))
    n_prov = len(df)

    # Group medians
    med_rpu = df["wrvu_per_encounter"].median()
    med_epm = df["encounters_per_month"].median()

    def delta(val, med):
        pct = ((val - med) / med * 100) if med else 0
        sign = "+" if pct >= 0 else ""
        return f"<font color='{'#3B6D11' if pct>=0 else '#993C1D'}'>{sign}{pct:.1f}% vs median</font>"

    col_w = W / 4
    metrics = [
        [Paragraph(f"{encs:,}", s_metric), Paragraph(f"{wrvus:,.1f}", s_metric),
         Paragraph(f"{rpu:.2f}", s_metric), Paragraph(f"{epm:.1f}", s_metric)],
        [Paragraph("Encounters", s_mlabel), Paragraph("Total wRVUs", s_mlabel),
         Paragraph("wRVU / Encounter", s_mlabel), Paragraph("Encounters / Month", s_mlabel)],
        [Paragraph(f"<font size=7>{n_mo}-mo period</font>", sty("s7", fontSize=7, leading=10, textColor=MGRAY, alignment=TA_CENTER)),
         Paragraph(f"<font size=7>{n_mo}-mo period</font>", sty("s7b", fontSize=7, leading=10, textColor=MGRAY, alignment=TA_CENTER)),
         Paragraph(delta(rpu, med_rpu), sty("sd1", fontSize=7.5, leading=10, alignment=TA_CENTER)),
         Paragraph(delta(epm, med_epm), sty("sd2", fontSize=7.5, leading=10, alignment=TA_CENTER))],
    ]
    mt = Table(metrics, colWidths=[col_w]*4)
    mt.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), LGRAY),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",       (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",  (0,0), (-1,0), 10),
        ("BOTTOMPADDING",(0,-1),(-1,-1),8),
        ("TOPPADDING",  (0,1), (-1,1), 2),
        ("LINEAFTER",   (0,0), (2,-1), 0.5, HexColor("#D3D1C7")),
        ("BOX",         (0,0), (-1,-1), 0.5, HexColor("#D3D1C7")),
    ]))
    story.append(mt)
    story.append(Spacer(1, 0.14*inch))

    # ── Rank bar ─────────────────────────────────────────────────────────────
    story.append(Paragraph(f"<b>Group Rank</b> (by wRVU/encounter)", s_bold))
    story.append(Spacer(1, 0.04*inch))

    # Simple rank display
    rank_pct = _pct_rank(rpu, df["wrvu_per_encounter"])
    rank_data = [[
        Paragraph(f"Rank <b>{rank}</b> of {n_prov}", s_normal),
        Paragraph(f"<b>{rank_pct}th</b> percentile", sty("srk", fontSize=9, leading=13, textColor=DGRAY, alignment=TA_RIGHT)),
    ]]
    rt = Table(rank_data, colWidths=[W*0.5, W*0.5])
    rt.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(rt)

    # Percentile bar
    bar_w_pt = W
    fill_w   = max(4, bar_w_pt * rank_pct / 100)
    bar_data = [["", ""]]
    bt = Table(bar_data, colWidths=[fill_w, bar_w_pt - fill_w], rowHeights=[8])
    bt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,0), qcolor),
        ("BACKGROUND", (1,0), (1,0), HexColor("#D3D1C7")),
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
        Paragraph(f"<b>Q{quadrant}</b>", sty("sqn", fontSize=13, leading=17, textColor=qcolor, fontName="Helvetica-Bold")),
        Paragraph(qlabels[quadrant], sty("sql", fontSize=9, leading=13, textColor=qcolor)),
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

    rec_data = [[
        Paragraph(f"<b>{q_title}</b>", sty("sqt", fontSize=9, leading=13, textColor=qcolor, fontName="Helvetica-Bold")),
    ], [
        Paragraph(q_para1, sty("sqp1", fontSize=8.5, leading=13, textColor=DGRAY)),
    ], [
        Paragraph(q_para2, sty("sqp2", fontSize=8.5, leading=13, textColor=DGRAY)),
    ]]
    rxt = Table(rec_data, colWidths=[W])
    rxt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), qbg),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,-1),(-1,-1), 8),
        ("LEFTPADDING",  (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("LINEBEFORE",   (0,0), (0,-1), 4, qcolor),
        ("BOX",          (0,0), (-1,-1), 0.5, qcolor),
    ]))
    story.append(rxt)
    story.append(Spacer(1, 0.18*inch))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=HexColor("#D3D1C7")))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "All provider comparisons in this report are fully de-identified. "
        "Metrics are sourced from the profee billing cube. "
        "Questions? Contact EDPhysicianLeadership@uchicagomedicine.org.",
        s_caption,
    ))

    doc.build(story)
    return buf.getvalue()
