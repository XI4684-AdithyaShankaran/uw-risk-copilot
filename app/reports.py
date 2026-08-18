from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as ReportImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from app.config import BASE_DIR


def _text(value: Any) -> str:
    if value is None or value == "":
        return "Not provided"
    if isinstance(value, list):
        return "; ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"{key.replace('_', ' ').title()}: {_text(item)}" for key, item in value.items())
    return str(value)


def _bullet_list(story: list, items: list[str], styles: Any) -> None:
    for item in items:
        story.append(Paragraph(f"• {_text(item)}", styles["Normal"]))


def _submitted_image_path(submission: dict[str, Any]) -> Path | None:
    raw_path = submission.get("image_path")
    if not raw_path:
        return None
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = BASE_DIR / path
    return path if path.is_file() else None


def build_submission_pdf(submission: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    raw = submission.get("raw_input", {})
    features = submission.get("extracted_features", {})
    memo = submission.get("memo_json") or {}
    sub_date = raw.get("submission_date") or date.today().isoformat()

    story: list[Any] = [
        Paragraph("Commercial Property Underwriting Report", styles["Title"]),
        Paragraph("AI-Assisted Underwriting Analysis", styles["Heading3"]),
        Paragraph(f"Report generated: {date.today().isoformat()}  |  Submission date: {sub_date}", styles["Normal"]),
        Spacer(1, 10),
    ]

    # ── Property summary ──────────────────────────────────────────────────────
    story.append(Paragraph("Property Summary", styles["Heading2"]))
    story.append(Paragraph(_text(submission.get("property_id")), styles["Normal"]))
    story.append(Paragraph(
        f"Location: {_text(raw.get('address'))}, {_text(raw.get('city'))}, "
        f"{_text(raw.get('state'))} {_text(raw.get('zip'))}",
        styles["Normal"],
    ))
    if memo.get("property_summary"):
        _bullet_list(story, memo["property_summary"], styles)
    story.append(Spacer(1, 6))

    # ── Authoritative decision ────────────────────────────────────────────────
    story.append(Paragraph("Authoritative Underwriting Decision", styles["Heading2"]))
    decision_rows = [
        ["Risk score", _text(submission.get("risk_score"))],
        ["Decision", _text(submission.get("decision"))],
        ["Risk flags", _text(submission.get("risk_flags"))],
        ["Total value at risk (INR)", _text(submission.get("total_value_at_risk_inr"))],
        ["Policy segment", _text(raw.get("policy_type") or submission.get("policy_type"))],
    ]
    dec_table = Table(decision_rows, colWidths=[55 * mm, 115 * mm])
    dec_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eaf6ee")),
    ]))
    story.append(dec_table)
    story.append(Spacer(1, 8))

    # ── Risk breakdown ────────────────────────────────────────────────────────
    story.append(Paragraph("Risk Score Breakdown", styles["Heading2"]))
    breakdown = submission.get("risk_breakdown") or {}
    bd_rows = [["Risk Factor", "Points"]]
    for factor, points in breakdown.items():
        bd_rows.append([factor.replace("_", " ").title(), str(points)])
    if len(bd_rows) > 1:
        bd_table = Table(bd_rows, colWidths=[90 * mm, 30 * mm])
        bd_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d4838")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(bd_table)
    story.append(Spacer(1, 6))

    # ── Key risk factors (from AI memo) ───────────────────────────────────────
    if memo.get("key_risk_factors"):
        story.append(Paragraph("Key Risk Factors", styles["Heading2"]))
        _bullet_list(story, memo["key_risk_factors"], styles)
        story.append(Spacer(1, 4))

    # ── Coverage review (from AI memo) ────────────────────────────────────────
    if memo.get("coverage_review"):
        story.append(Paragraph("Coverage Review", styles["Heading2"]))
        _bullet_list(story, memo["coverage_review"], styles)
        story.append(Spacer(1, 4))

    # ── AI rationale ──────────────────────────────────────────────────────────
    if memo.get("rationale"):
        story.append(Paragraph("Underwriting Rationale", styles["Heading2"]))
        story.append(Paragraph(memo["rationale"], styles["Normal"]))
        story.append(Spacer(1, 4))

    # ── Suggested next steps (from AI memo) ───────────────────────────────────
    if memo.get("suggested_next_steps"):
        story.append(Paragraph("Suggested Next Steps", styles["Heading2"]))
        _bullet_list(story, memo["suggested_next_steps"], styles)
        story.append(Spacer(1, 4))
    elif not memo:
        story.append(Paragraph("Suggested Next Steps", styles["Heading2"]))
        story.append(Paragraph(
            f"AI-assisted analysis unavailable: {_text(submission.get('ai_memo_reason'))}. "
            "Review the deterministic risk flags and available guideline evidence before final underwriting action.",
            styles["Normal"],
        ))
        story.append(Spacer(1, 4))

    # ── Image review ──────────────────────────────────────────────────────────
    story.append(Paragraph("Property Image Assessment", styles["Heading2"]))
    img_rows = [
        ["Status", _text(features.get("image_status"))],
        ["Reason", _text(features.get("image_reason"))],
        ["Evidence used", _text(features.get("image_risk_evidence_used"))],
    ]
    for obs_key in ("visible_roof_condition", "visible_structural_damage", "general_maintenance_level", "visible_hazards"):
        val = features.get(obs_key)
        if val and str(val).lower() not in ("not visible", "none", ""):
            img_rows.append([obs_key.replace("_", " ").title(), _text(val)])
    img_table = Table(img_rows, colWidths=[55 * mm, 115 * mm])
    img_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
    story.append(img_table)
    submitted_image = _submitted_image_path(submission)
    if submitted_image is not None:
        report_image = ReportImage(str(submitted_image))
        max_width, max_height = 170 * mm, 95 * mm
        scale = min(max_width / report_image.imageWidth, max_height / report_image.imageHeight, 1)
        report_image.drawWidth = report_image.imageWidth * scale
        report_image.drawHeight = report_image.imageHeight * scale
        story.append(Spacer(1, 5))
        story.append(report_image)
        story.append(Paragraph(
            f"Submitted property image: {_text(submitted_image.name)}. Visual observations above are evidence-extraction outputs, not authoritative property facts.",
            styles["Italic"],
        ))
    story.append(Spacer(1, 6))

    # ── Guideline evidence (concise excerpts) ────────────────────────────────
    chunks = [c for c in submission.get("guideline_chunks", []) if c and str(c).strip()]
    if chunks:
        story.append(Paragraph("Underwriting Evidence (Guidelines)", styles["Heading2"]))
        for chunk in chunks:
            excerpt = str(chunk)[:200] + ("…" if len(str(chunk)) > 200 else "")
            story.append(Paragraph(f"• {excerpt}", styles["Normal"]))
        story.append(Spacer(1, 6))

    # ── Reference properties ──────────────────────────────────────────────────
    story.append(Paragraph("Reference Properties", styles["Heading2"]))
    story.append(Paragraph("Synthetic reference data — not verified market comparables.", styles["Normal"]))
    comps = [c for c in submission.get("comparables", []) if isinstance(c, dict)]
    if comps:
        comp_keys = ["property_id", "city", "state", "construction_type", "occupancy_type", "cat_zone", "year_built", "tiv"]
        comp_headers = [k.replace("_", " ").title() for k in comp_keys]
        comp_data = [comp_headers] + [[_text(c.get(k)) for k in comp_keys] for c in comps]
        comp_col_w = [22 * mm, 22 * mm, 14 * mm, 26 * mm, 18 * mm, 16 * mm, 14 * mm, 20 * mm]
        comp_table = Table(comp_data, colWidths=comp_col_w, repeatRows=1)
        comp_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d4838")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7faf8")]),
        ]))
        story.append(comp_table)
    else:
        story.append(Paragraph("No reference properties available.", styles["Normal"]))
    document.build(story)
    return buffer.getvalue()
