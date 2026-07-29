import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from app.schemas.analysis import RepositoryAnalysisReport

logger = logging.getLogger(__name__)

# ── Colour palette ──────────────────────────────────────────────────────────────
# Dark backgrounds (tables / banners)
DARK_BG  = colors.HexColor("#0F172A")
DARK_ROW = colors.HexColor("#1E293B")
DARK_ALT = colors.HexColor("#162032")
DARK_SEP = colors.HexColor("#334155")

# Accent
ACCENT   = colors.HexColor("#06B6D4")
ACCENT2  = colors.HexColor("#6366F1")
SUCCESS  = colors.HexColor("#10B981")
WARNING  = colors.HexColor("#F59E0B")
DANGER   = colors.HexColor("#EF4444")

# Severity badge colours
SEV_HIGH_BG    = colors.HexColor("#2D0A0A")
SEV_HIGH_FG    = colors.HexColor("#F87171")
SEV_MEDIUM_BG  = colors.HexColor("#2D1A00")
SEV_MEDIUM_FG  = colors.HexColor("#FCD34D")
SEV_LOW_BG     = colors.HexColor("#0A1F2D")
SEV_LOW_FG     = colors.HexColor("#60A5FA")

# Prose on white page
INK        = colors.HexColor("#111827")   # near-black — main body text
INK_MUTED  = colors.HexColor("#374151")   # slightly lighter prose
INK_SUB    = colors.HexColor("#6B7280")   # footnote / sub-labels
# On dark backgrounds (table cells)
ON_DARK        = colors.HexColor("#F1F5F9")
ON_DARK_MUTED  = colors.HexColor("#94A3B8")

# HTTP method colours
GET_COLOR    = colors.HexColor("#10B981")
POST_COLOR   = colors.HexColor("#F59E0B")
PUT_COLOR    = colors.HexColor("#3B82F6")
DELETE_COLOR = colors.HexColor("#EF4444")


# ── Helper: method colour ───────────────────────────────────────────────────────
def _method_color(method: str) -> colors.Color:
    return {
        "GET":    GET_COLOR,
        "POST":   POST_COLOR,
        "PUT":    PUT_COLOR,
        "PATCH":  PUT_COLOR,
        "DELETE": DELETE_COLOR,
    }.get(method.upper(), ACCENT2)


# ── Helper: severity colours ────────────────────────────────────────────────────
def _severity_colors(severity: str) -> tuple[colors.Color, colors.Color]:
    """Returns (bg, fg) for a severity level."""
    s = severity.lower()
    if s == "high":
        return SEV_HIGH_BG, SEV_HIGH_FG
    if s == "medium":
        return SEV_MEDIUM_BG, SEV_MEDIUM_FG
    return SEV_LOW_BG, SEV_LOW_FG


# ── Shared table style commands ─────────────────────────────────────────────────
def _base_table_style() -> list:
    return [
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]


# ── Main PDF generator ──────────────────────────────────────────────────────────
def generate_pdf(report: RepositoryAnalysisReport) -> bytes:
    buffer = io.BytesIO()
    W = A4[0] - 36 * mm  # usable width

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"AutoQA Report – {report.repository_name}",
    )

    # ── Style sheet ────────────────────────────────────────────────────────────
    # Banner (dark bg)
    h1 = ParagraphStyle("H1", fontSize=20, textColor=ON_DARK,
                        fontName="Helvetica-Bold", alignment=TA_LEFT, leading=24)
    # Section headings (white page, teal accent)
    h2 = ParagraphStyle("H2", fontSize=13, textColor=ACCENT,
                        fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4,
                        leading=16)
    # Sub-headings (white page, near-black)
    h3 = ParagraphStyle("H3", fontSize=10, textColor=INK,
                        fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=3,
                        leading=14)
    # Body prose (white page — dark ink)
    body = ParagraphStyle("Body", fontSize=9, textColor=INK, leading=14,
                          spaceAfter=4, fontName="Helvetica")
    # Monospaced (file paths, routes) — dark teal, readable on white
    mono = ParagraphStyle("Mono", fontSize=8, textColor=colors.HexColor("#0E7490"),
                          leading=12, fontName="Courier")
    # Secondary prose — still dark enough on white
    mid_style = ParagraphStyle("Mid", fontSize=8, textColor=INK_MUTED,
                               fontName="Helvetica", leading=12)
    # Bulleted steps
    step_style = ParagraphStyle("Step", fontSize=9, textColor=INK, leading=14,
                                leftIndent=12, fontName="Helvetica", spaceAfter=3)
    # Column header labels on DARK cells
    label_dark = ParagraphStyle("LabelDark", fontSize=7, textColor=ON_DARK_MUTED,
                                fontName="Helvetica-Bold", spaceBefore=0)
    # Evidence items (code references) — dark teal on white
    evidence_style = ParagraphStyle("Evidence", fontSize=8,
                                    textColor=colors.HexColor("#0E7490"),
                                    leading=12, leftIndent=14, fontName="Courier",
                                    spaceAfter=2)
    # Footer
    footer_style = ParagraphStyle("Footer", fontSize=7, textColor=INK_SUB,
                                  fontName="Helvetica", leading=10)
    # Stat box content (on dark bg)
    stat_style = ParagraphStyle("Stat", fontSize=9, textColor=ON_DARK,
                                fontName="Helvetica", leading=18, alignment=TA_CENTER)
    # Timestamp in header banner
    ts_style = ParagraphStyle("TS", fontSize=8, textColor=ON_DARK_MUTED,
                              fontName="Helvetica", alignment=TA_RIGHT, leading=12)

    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # 1. HEADER BANNER
    # ══════════════════════════════════════════════════════════════════════════
    banner_data = [[
        Paragraph("■  AutoQA Agent", h1),
        Paragraph(
            datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            ts_style,
        ),
    ]]
    banner = Table(banner_data, colWidths=[W * 0.65, W * 0.35])
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), DARK_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (0, -1),  16),
        ("RIGHTPADDING",  (-1, 0), (-1, -1), 16),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(banner)
    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # 2. REPO NAME & URL
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph(report.repository_name, h2))
    story.append(Paragraph(report.repository_url, mono))
    story.append(HRFlowable(width=W, color=ACCENT, thickness=0.5, spaceAfter=8))

    # ══════════════════════════════════════════════════════════════════════════
    # 3. STATS ROW
    # ══════════════════════════════════════════════════════════════════════════
    confidence = report.confidence_score
    conf_label = f"{confidence:.0f}%" if confidence is not None else "N/A"
    stats = [
        ("■ Files",       str(report.number_of_files)),
        ("■ APIs",        str(report.number_of_apis_discovered)),
        ("Branch",        report.metadata.get("default_branch") or "N/A"),
        ("■ Dirs",        str(report.project_structure_summary.directories)),
        ("■ Confidence",  conf_label),
    ]
    stat_cells = [[
        Paragraph(
            f'<font color="#94A3B8" size="7">{k}</font><br/>'
            f'<font color="#F1F5F9" size="13"><b>{v}</b></font>',
            stat_style,
        )
        for k, v in stats
    ]]
    stat_table = Table(stat_cells, colWidths=[W / 5] * 5)
    stat_table.setStyle(TableStyle([
        *_base_table_style(),
        ("BACKGROUND",    (0, 0), (-1, -1), DARK_BG),
        ("BOX",           (0, 0), (-1, -1), 0.5, ACCENT2),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, DARK_SEP),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════════════════
    # 4. LOW CONFIDENCE WARNING
    # ══════════════════════════════════════════════════════════════════════════
    if confidence is not None and confidence < 70:
        warn_data = [[Paragraph(
            f'⚠  <b>Low Confidence Analysis ({confidence:.0f}%)</b> — '
            'Limited evidence found. Manual review recommended.',
            ParagraphStyle("Warn", fontSize=9, textColor=WARNING,
                           fontName="Helvetica-Bold", leading=14),
        )]]
        warn_table = Table(warn_data, colWidths=[W])
        warn_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#1C1400")),
            ("BOX",           (0, 0), (-1, -1), 1, WARNING),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ]))
        story.append(warn_table)
        story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # 5. README SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    if report.readme_summary:
        story.append(Paragraph("■  README Summary", h2))
        story.append(Paragraph(report.readme_summary, body))
        story.append(HRFlowable(width=W, color=ACCENT, thickness=0.5, spaceAfter=6))

    # ══════════════════════════════════════════════════════════════════════════
    # 6. AI ANALYSIS (GROQ)
    # ══════════════════════════════════════════════════════════════════════════
    ai = report.ai_explanation or {}
    if ai:
        story.append(Paragraph("■  AI Analysis (Groq · llama-3.1-8b-instant)", h2))

        if ai.get("project_overview"):
            story.append(Paragraph("Project Overview", h3))
            story.append(Paragraph(ai["project_overview"], body))
            story.append(Spacer(1, 4))

        if ai.get("use_case"):
            story.append(Paragraph(f"Use Case: {ai['use_case']}", body))

        if ai.get("complexity_level"):
            story.append(Paragraph(f"Complexity: {ai['complexity_level']}", body))
            story.append(Spacer(1, 4))

        if ai.get("workflow"):
            story.append(Paragraph("Workflow", h3))
            for i, step in enumerate(ai["workflow"], 1):
                story.append(Paragraph(f"  Step {i}. {step}", step_style))
            story.append(Spacer(1, 4))

        if ai.get("key_technologies"):
            story.append(Paragraph("Key Technologies", h3))
            for tech, desc in ai["key_technologies"].items():
                story.append(Paragraph(f"<b>{tech}</b>: {desc}", body))
            story.append(Spacer(1, 4))

        if ai.get("api_summary"):
            story.append(Paragraph("API Summary", h3))
            story.append(Paragraph(ai["api_summary"], body))

        story.append(HRFlowable(width=W, color=ACCENT2, thickness=0.5, spaceAfter=6))

    # ══════════════════════════════════════════════════════════════════════════
    # 7. DETECTED FEATURES
    # ══════════════════════════════════════════════════════════════════════════
    if report.detected_features:
        story.append(Paragraph("■  Detected Features", h2))
        for feature in report.detected_features:
            story.append(Paragraph(f"<b>{feature.name}</b>", h3))
            for ev in feature.evidence:
                story.append(Paragraph(f"  › {ev}", evidence_style))
            story.append(Spacer(1, 4))
        story.append(HRFlowable(width=W, color=ACCENT, thickness=0.5, spaceAfter=6))

    # ══════════════════════════════════════════════════════════════════════════
    # 8. ARCHITECTURE NOTES
    # ══════════════════════════════════════════════════════════════════════════
    if report.architecture_notes:
        story.append(Paragraph("■  Architecture Notes", h2))
        story.append(Paragraph(report.architecture_notes, body))
        story.append(HRFlowable(width=W, color=ACCENT, thickness=0.5, spaceAfter=6))

    # ══════════════════════════════════════════════════════════════════════════
    # 9. TECHNOLOGY STACK
    # ══════════════════════════════════════════════════════════════════════════
    tech = report.technology_stack
    story.append(Paragraph("■  Technology Stack", h2))
    stack_rows = [
        [Paragraph("<b>Category</b>", label_dark), Paragraph("<b>Technologies</b>", label_dark)],
        ["Frontend",   ", ".join(tech.frontend)   or "—"],
        ["Backend",    ", ".join(tech.backend)    or "—"],
        ["Languages",  ", ".join(tech.languages)  or "—"],
        ["Databases",  ", ".join(tech.databases)  or "—"],
        ["Frameworks", ", ".join(tech.frameworks) or "—"],
    ]
    stack_table = Table(stack_rows, colWidths=[W * 0.28, W * 0.72])
    stack_table.setStyle(TableStyle([
        *_base_table_style(),
        ("BACKGROUND",    (0, 0), (-1, 0),  DARK_ROW),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [DARK_BG, DARK_ALT]),
        ("TEXTCOLOR",     (0, 0), (-1, -1), ON_DARK),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("BOX",           (0, 0), (-1, -1), 0.5, ACCENT),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, DARK_SEP),
    ]))
    story.append(stack_table)
    story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════════════════
    # 10. MODULE SUMMARIES
    # ══════════════════════════════════════════════════════════════════════════
    if report.module_summaries:
        story.append(Paragraph("■  Module Summaries", h2))
        for mod_name, mod_summary in report.module_summaries.items():
            story.append(Paragraph(f"<b>{mod_name}/</b> — {mod_summary}", body))
        story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # 11. API INVENTORY
    # ══════════════════════════════════════════════════════════════════════════
    if report.api_inventory:
        story.append(Paragraph("■  API Inventory", h2))
        api_rows = [[
            Paragraph("<b>Method</b>",    label_dark),
            Paragraph("<b>Path</b>",      label_dark),
            Paragraph("<b>Framework</b>", label_dark),
            Paragraph("<b>File</b>",      label_dark),
            Paragraph("<b>Line</b>",      label_dark),
        ]]
        for ep in report.api_inventory:
            mc = _method_color(ep.method)
            api_rows.append([
                Paragraph(
                    f'<font color="{mc.hexval()}"><b>{ep.method}</b></font>',
                    mono,
                ),
                Paragraph(ep.path, mono),
                Paragraph(ep.framework,
                          ParagraphStyle("fw", fontSize=8, textColor=ON_DARK,
                                         fontName="Helvetica", leading=12)),
                Paragraph(
                    ep.file[-38:] if len(ep.file) > 38 else ep.file,
                    ParagraphStyle("fp", fontSize=7, textColor=ON_DARK_MUTED,
                                   fontName="Helvetica", leading=11),
                ),
                Paragraph(
                    str(ep.line_number or "—"),
                    ParagraphStyle("ln", fontSize=8, textColor=ON_DARK,
                                   fontName="Helvetica", leading=12, alignment=TA_RIGHT),
                ),
            ])
        api_col_w = [W*0.10, W*0.22, W*0.15, W*0.43, W*0.10]
        api_table = Table(api_rows, colWidths=api_col_w)
        api_table.setStyle(TableStyle([
            *_base_table_style(),
            ("BACKGROUND",    (0, 0), (-1, 0),  DARK_ROW),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [DARK_BG, DARK_ALT]),
            ("TEXTCOLOR",     (0, 0), (-1, -1), ON_DARK),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("BOX",           (0, 0), (-1, -1), 0.5, ACCENT),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, DARK_SEP),
            ("ALIGN",         (4, 0), (4, -1),  "RIGHT"),
        ]))
        story.append(api_table)
        story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════════════════
    # 12. BUG REPORT  ← NEW SECTION
    # ══════════════════════════════════════════════════════════════════════════
    ci = report.code_insights
    if ci is not None and ci.issues:
        issues = sorted(
            ci.issues,
            key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.severity.lower(), 3),
        )

        story.append(Paragraph("■  Bug & Code Quality Report", h2))

        # Summary chips row
        high_n   = sum(1 for i in issues if i.severity.lower() == "high")
        medium_n = sum(1 for i in issues if i.severity.lower() == "medium")
        low_n    = sum(1 for i in issues if i.severity.lower() == "low")

        summary_data = [[
            Paragraph(
                f'<font color="#F87171"><b>● HIGH</b></font>  <font color="#F1F5F9" size="12"><b>{high_n}</b></font>',
                ParagraphStyle("sc", fontSize=9, textColor=ON_DARK, fontName="Helvetica",
                               alignment=TA_CENTER, leading=14),
            ),
            Paragraph(
                f'<font color="#FCD34D"><b>● MEDIUM</b></font>  <font color="#F1F5F9" size="12"><b>{medium_n}</b></font>',
                ParagraphStyle("sc", fontSize=9, textColor=ON_DARK, fontName="Helvetica",
                               alignment=TA_CENTER, leading=14),
            ),
            Paragraph(
                f'<font color="#60A5FA"><b>● LOW</b></font>  <font color="#F1F5F9" size="12"><b>{low_n}</b></font>',
                ParagraphStyle("sc", fontSize=9, textColor=ON_DARK, fontName="Helvetica",
                               alignment=TA_CENTER, leading=14),
            ),
            Paragraph(
                f'<font color="#94A3B8">TOTAL</font>  <font color="#F1F5F9" size="12"><b>{len(issues)}</b></font>',
                ParagraphStyle("sc", fontSize=9, textColor=ON_DARK, fontName="Helvetica",
                               alignment=TA_CENTER, leading=14),
            ),
        ]]
        summary_table = Table(summary_data, colWidths=[W / 4] * 4)
        summary_table.setStyle(TableStyle([
            *_base_table_style(),
            ("BACKGROUND",    (0, 0), (-1, -1), DARK_BG),
            ("BOX",           (0, 0), (-1, -1), 0.5, DANGER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, DARK_SEP),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 8))

        # Issue rows table
        bug_rows = [[
            Paragraph("<b>Severity</b>", label_dark),
            Paragraph("<b>File</b>",     label_dark),
            Paragraph("<b>Line</b>",     label_dark),
            Paragraph("<b>Issue</b>",    label_dark),
            Paragraph("<b>Suggestion</b>", label_dark),
        ]]

        MAX_BUGS = 60   # cap to avoid bloating the PDF
        for issue in issues[:MAX_BUGS]:
            _, sev_fg = _severity_colors(issue.severity)
            file_short = issue.file[-36:] if len(issue.file) > 36 else issue.file
            suggestion  = issue.suggestion or "—"
            if len(suggestion) > 80:
                suggestion = suggestion[:77] + "…"

            bug_rows.append([
                Paragraph(
                    f'<font color="{sev_fg.hexval()}"><b>{issue.severity.upper()}</b></font>',
                    ParagraphStyle("sev", fontSize=7, fontName="Helvetica-Bold",
                                   textColor=ON_DARK, alignment=TA_CENTER, leading=10),
                ),
                Paragraph(
                    file_short,
                    ParagraphStyle("bf", fontSize=7, textColor=ON_DARK_MUTED,
                                   fontName="Courier", leading=10),
                ),
                Paragraph(
                    str(issue.line) if issue.line else "—",
                    ParagraphStyle("bl", fontSize=7, textColor=ON_DARK,
                                   fontName="Helvetica", leading=10, alignment=TA_RIGHT),
                ),
                Paragraph(
                    issue.message,
                    ParagraphStyle("bm", fontSize=8, textColor=ON_DARK,
                                   fontName="Helvetica", leading=11),
                ),
                Paragraph(
                    suggestion,
                    ParagraphStyle("bs", fontSize=7, textColor=ON_DARK_MUTED,
                                   fontName="Helvetica", leading=11),
                ),
            ])

        bug_col_w = [W*0.10, W*0.26, W*0.07, W*0.31, W*0.26]
        bug_table = Table(bug_rows, colWidths=bug_col_w, repeatRows=1)
        bug_table.setStyle(TableStyle([
            *_base_table_style(),
            ("BACKGROUND",    (0, 0), (-1, 0),  DARK_ROW),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [DARK_BG, DARK_ALT]),
            ("TEXTCOLOR",     (0, 0), (-1, -1), ON_DARK),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("BOX",           (0, 0), (-1, -1), 0.5, DANGER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, DARK_SEP),
            ("ALIGN",         (2, 0), (2, -1),  "RIGHT"),   # Line col right-aligned
            ("ALIGN",         (0, 0), (0, -1),  "CENTER"),  # Severity col centred
        ]))
        story.append(bug_table)

        if len(issues) > MAX_BUGS:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"… and {len(issues) - MAX_BUGS} more issues not shown (total: {len(issues)})",
                mid_style,
            ))

        story.append(HRFlowable(width=W, color=DANGER, thickness=0.5, spaceAfter=6))
        story.append(Spacer(1, 4))

    # ══════════════════════════════════════════════════════════════════════════
    # 13. CODE INSIGHTS (file analysis stats + patterns + module summaries)
    # ══════════════════════════════════════════════════════════════════════════
    if ci is not None:
        story.append(Paragraph("■  Code Insights (Hierarchical Analysis)", h2))

        # Stats row (dark bg)
        cache_pct = f"{ci.cache_hit_rate * 100:.0f}%"
        ci_stats = [
            ("■ Files Analyzed", str(len(ci.analyzed_files))),
            ("■ Files Skipped",  str(ci.skipped_files_count)),
            ("■ Cache Hit Rate", cache_pct),
        ]
        ci_stat_cells = [[
            Paragraph(
                f'<font color="#94A3B8" size="7">{k}</font><br/>'
                f'<font color="#F1F5F9" size="13"><b>{v}</b></font>',
                stat_style,
            )
            for k, v in ci_stats
        ]]
        ci_stat_table = Table(ci_stat_cells, colWidths=[W / 3] * 3)
        ci_stat_table.setStyle(TableStyle([
            *_base_table_style(),
            ("BACKGROUND",    (0, 0), (-1, -1), DARK_BG),
            ("BOX",           (0, 0), (-1, -1), 0.5, ACCENT2),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, DARK_SEP),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(ci_stat_table)
        story.append(Spacer(1, 8))

        if ci.cache_hit_rate > 0:
            story.append(Paragraph(
                f"■ {cache_pct} cache hit rate — re-analysis was fast "
                "(summaries reused from previous run)",
                mid_style,
            ))
            story.append(Spacer(1, 6))

        if ci.notable_patterns:
            story.append(Paragraph("Notable Patterns Detected", h3))
            for pattern in ci.notable_patterns[:20]:
                story.append(Paragraph(f"  › {pattern}", evidence_style))
            story.append(Spacer(1, 6))

        if ci.module_summaries:
            story.append(Paragraph("Enriched Module Summaries", h3))
            for mod_name, mod_summary in ci.module_summaries.items():
                story.append(Paragraph(f"<b>{mod_name}/</b> — {mod_summary}", body))
            story.append(Spacer(1, 6))

        story.append(HRFlowable(width=W, color=ACCENT, thickness=0.5, spaceAfter=6))

    # ══════════════════════════════════════════════════════════════════════════
    # 14. FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    story.append(HRFlowable(width=W, color=DARK_SEP, thickness=0.5))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Report ID: {report.analysis_id}  •  AutoQA Agent  •  "
        f"{datetime.utcnow().strftime('%Y-%m-%d')}",
        footer_style,
    ))

    doc.build(story)
    return buffer.getvalue()
