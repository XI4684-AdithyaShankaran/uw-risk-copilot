import json
import sqlite3

from PIL import Image

from app import db
from app.reports import build_submission_pdf


def test_cleanup_is_deterministic_and_retains_canonical_tidell(tmp_path, monkeypatch):
    database_path = tmp_path / "uw_risk.db"
    monkeypatch.setattr(db, "DB_PATH", database_path)
    monkeypatch.setattr(db, "PROPERTIES_CSV", tmp_path / "missing.csv")
    db.init_db()
    conn = sqlite3.connect(database_path)
    for property_id in ("TEST-001", "REAL-IN-TIDEL-001", "REAL-IN-TIDEL-001"):
        payload = {"property_id": property_id, "decision": "Accept", "risk_score": 5}
        conn.execute(
            "INSERT INTO submissions (property_id, raw_input, decision, risk_score, result_json) VALUES (?, ?, ?, ?, ?)",
            (property_id, json.dumps({"property_id": property_id}), "Accept", 5, json.dumps(payload)),
        )
    conn.commit()
    conn.close()

    result = db.backup_and_cleanup_demo_database(tmp_path / "backup.db")
    assert (tmp_path / "backup.db").exists()
    assert result["before"] == 3
    assert result["after"] == 1
    retained = db.fetch_history()
    assert len(retained) == 1
    assert retained[0]["property_id"] == "REAL-IN-TIDEL-001"


def test_pdf_builder_returns_nonempty_pdf():
    pdf = build_submission_pdf({"property_id": "TIDEL", "risk_score": 5, "decision": "Accept", "risk_flags": [], "risk_breakdown": {}, "raw_input": {}, "extracted_features": {}, "ai_memo_status": "Unavailable", "ai_memo_reason": "test"})
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 100


def test_pdf_builder_embeds_submitted_image(tmp_path):
    image_path = tmp_path / "property.jpg"
    Image.new("RGB", (320, 180), color=(40, 100, 130)).save(image_path)
    pdf = build_submission_pdf({
        "property_id": "IMAGE-PDF-001",
        "risk_score": 5,
        "decision": "Accept",
        "risk_flags": [],
        "risk_breakdown": {},
        "raw_input": {},
        "extracted_features": {"image_status": "usable", "image_risk_evidence_used": True},
        "image_path": str(image_path),
        "ai_memo_status": "Unavailable",
        "ai_memo_reason": "test",
    })
    assert pdf.startswith(b"%PDF")
    assert b"/Subtype /Image" in pdf
