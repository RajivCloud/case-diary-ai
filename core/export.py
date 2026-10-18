"""Export the reviewed chargesheet draft as a Word document the IO can edit and file."""

from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.shared import Pt, RGBColor


def item_key(section: str, i: int) -> str:
    return f"{section}:{i}"


def build_docx(case: dict, report: dict, review: dict) -> bytes:
    decisions = review.get("decisions", {})

    def ok(section: str, i: int) -> bool:
        return decisions.get(item_key(section, i), {}).get("decision") != "Reject"

    def note(section: str, i: int) -> str:
        d = decisions.get(item_key(section, i), {})
        return f"  [IO: {d.get('decision')}{' - ' + d['note'] if d.get('note') else ''}]" if d.get("decision") else ""

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading("DRAFT FINAL REPORT (s.193 BNSS) - FOR IO REVIEW", level=1)
    p = doc.add_paragraph()
    r = p.add_run("AI-assisted draft prepared with CaseDiary.AI. Not a final document. Fictional demo data.")
    r.italic = True
    r.font.color.rgb = RGBColor(0x99, 0x33, 0x33)

    t = doc.add_table(rows=0, cols=2)
    t.style = "Light Grid Accent 1"
    for k, v in [("Case", case["case_id"]), ("FIR", f"{case.get('fir_no')} dated {case.get('fir_date')}"),
                 ("Police station", case.get("police_station", "")), ("Fraud type", case.get("fraud_type", "")),
                 ("Complainant", case.get("complainant", "")), ("Loss", f"Rs {int(case.get('loss_inr') or 0):,}"),
                 ("Investigating Officer", case.get("io_name", "")),
                 ("Reviewed by", f"{review.get('reviewed_by') or 'not yet reviewed'} {review.get('reviewed_at') or ''}")]:
        row = t.add_row().cells
        row[0].text, row[1].text = k, str(v)

    doc.add_heading("1. Brief facts and summary of evidence", level=2)
    doc.add_paragraph(report.get("summary", ""))
    if report.get("suggested_sections"):
        doc.add_paragraph("Sections suggested: " + "; ".join(report["suggested_sections"]))

    doc.add_heading("2. Accused", level=2)
    for i, a in enumerate(report.get("accused", [])):
        if not ok("accused", i):
            continue
        doc.add_paragraph(f"{a['name']} - {a['role']}{note('accused', i)}", style="List Number")
        for e in a.get("evidence", []):
            doc.add_paragraph(f"{e['point']} [{'; '.join(e.get('sources', []))}]", style="List Bullet 2")

    doc.add_heading("3. Persons examined and not charge-sheeted", level=2)
    for i, c in enumerate(report.get("cleared", [])):
        if ok("cleared", i):
            doc.add_paragraph(f"{c['name']}: {c['reason']} [{'; '.join(c.get('sources', []))}]{note('cleared', i)}",
                              style="List Bullet")

    doc.add_heading("4. Statements contradicted by records", level=2)
    for i, c in enumerate(report.get("contradictions", [])):
        if ok("contradictions", i):
            doc.add_paragraph(f"{c['person']} claimed: {c['claim']}. Contradicted by: {c['contradicted_by']} "
                              f"[{'; '.join(c.get('sources', []))}]{note('contradictions', i)}", style="List Bullet")

    doc.add_heading("5. Money trail", level=2)
    for m in report.get("money_trail", []):
        doc.add_paragraph(f"{m.get('from')} -> {m.get('to')}: Rs {int(m.get('amount') or 0):,} {m.get('when', '')} "
                          f"[{'; '.join(m.get('sources', []))}]", style="List Bullet")

    doc.add_heading("6. Readiness gaps to be fixed before filing", level=2)
    for i, g in enumerate(report.get("readiness_gaps", [])):
        if ok("readiness_gaps", i):
            doc.add_paragraph(f"{g['issue']} - Impact: {g['impact']} - Fix: {g['fix']}{note('readiness_gaps', i)}",
                              style="List Number")

    if report.get("next_actions"):
        doc.add_heading("7. Next actions", level=2)
        for a in report["next_actions"]:
            doc.add_paragraph(f"{a['action']}{' - ' + a['why'] if a.get('why') else ''}", style="List Bullet")

    doc.add_paragraph()
    doc.add_paragraph(f"Generated {datetime.now():%d-%m-%Y %H:%M}. Every point cites the case document paragraph "
                      "(DOC-xx ¶n), call record (CDR) or transaction (TXN) it relies on.").italic = True
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
