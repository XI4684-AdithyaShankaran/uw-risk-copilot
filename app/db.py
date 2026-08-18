from __future__ import annotations

import csv
import json
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import DB_PATH, PROPERTIES_CSV

# Initialized once per process — prevents reseed/schema-check on every read
_db_ready = False


def _parse_float(value: str | None) -> float | None:
    if not value or value.strip() == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_int(value: str | None) -> int | None:
    if not value or value.strip() == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_properties_table() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS properties (
                property_id TEXT PRIMARY KEY,
                address TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                latitude REAL,
                longitude REAL,
                construction_type TEXT,
                year_built INTEGER,
                roof_type TEXT,
                roof_age_years INTEGER,
                square_footage INTEGER,
                occupancy_type TEXT,
                num_stories INTEGER,
                sprinkler_system TEXT,
                cat_zone TEXT,
                distance_to_coast_miles REAL,
                distance_to_fire_zone_miles REAL,
                prior_claims_count_5yr INTEGER,
                prior_claims_total_amount REAL,
                tiv REAL,
                submission_date TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
def seed_properties_from_csv() -> None:
    ensure_properties_table()
    if not PROPERTIES_CSV.exists():
        return
    conn = get_connection()
    try:
        with PROPERTIES_CSV.open("r", encoding="utf-8", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO properties (
                        property_id, address, city, state, zip, latitude, longitude,
                        construction_type, year_built, roof_type, roof_age_years,
                        square_footage, occupancy_type, num_stories, sprinkler_system,
                        cat_zone, distance_to_coast_miles, distance_to_fire_zone_miles,
                        prior_claims_count_5yr, prior_claims_total_amount, tiv, submission_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("property_id"),
                        row.get("address"),
                        row.get("city"),
                        row.get("state"),
                        row.get("zip"),
                        _parse_float(row.get("latitude")),
                        _parse_float(row.get("longitude")),
                        row.get("construction_type"),
                        _parse_int(row.get("year_built")),
                        row.get("roof_type"),
                        _parse_int(row.get("roof_age_years")),
                        _parse_int(row.get("square_footage")),
                        row.get("occupancy_type"),
                        _parse_int(row.get("num_stories")),
                        row.get("sprinkler_system"),
                        row.get("cat_zone"),
                        _parse_float(row.get("distance_to_coast_miles")),
                        _parse_float(row.get("distance_to_fire_zone_miles")),
                        _parse_int(row.get("prior_claims_count_5yr")),
                        _parse_float(row.get("prior_claims_total_amount")),
                        _parse_float(row.get("tiv")),
                        row.get("submission_date"),
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    global _db_ready
    if _db_ready:
        return
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id TEXT NOT NULL,
                raw_input TEXT NOT NULL,
                decision TEXT,
                risk_score INTEGER,
                risk_flags TEXT,
                risk_breakdown TEXT,
                prototype_mitigation_model TEXT,
                memo_json TEXT,
                memo_markdown TEXT,
                result_json TEXT,
                record_type TEXT NOT NULL DEFAULT 'production',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    ensure_properties_table()
    ensure_submission_columns()
    seed_properties_from_csv()
    _db_ready = True


def ensure_submission_columns() -> None:
    conn = get_connection()
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(submissions)")}
        if "prototype_mitigation_model" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN prototype_mitigation_model TEXT")
            conn.commit()
        if "result_json" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN result_json TEXT")
            conn.commit()
        if "memo_json" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN memo_json TEXT")
            conn.commit()
        if "record_type" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN record_type TEXT NOT NULL DEFAULT 'production'")
            conn.commit()
    finally:
        conn.close()


def save_submission(state: dict[str, Any]) -> dict[str, Any]:
    conn = get_connection()
    try:
        payload = state.get("raw_input", {})
        decision = state.get("decision", "")
        risk_score = state.get("risk_score", 0)
        risk_flags = ", ".join(state.get("risk_flags", []))
        risk_breakdown = state.get("risk_breakdown", {})
        prototype_mitigation_model = state.get("prototype_mitigation_model", {})
        memo_json = state.get("memo_json", {})
        result_json = json.dumps(state, ensure_ascii=False)

        cursor = conn.execute(
            """
            INSERT INTO submissions (
                property_id, raw_input, decision, risk_score, risk_flags,
                risk_breakdown, prototype_mitigation_model, memo_json, result_json, record_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.get("property_id", payload.get("property_id", "")),
                json.dumps(payload, ensure_ascii=False),
                decision,
                risk_score,
                risk_flags,
                json.dumps(risk_breakdown, ensure_ascii=False),
                json.dumps(prototype_mitigation_model, ensure_ascii=False),
                json.dumps(memo_json, ensure_ascii=False),
                result_json,
                state.get("record_type", "production"),
            ),
        )
        conn.commit()
        state_with_id = {**state, "id": cursor.lastrowid}
        conn.execute(
            "UPDATE submissions SET result_json = ? WHERE id = ?",
            (json.dumps(state_with_id, ensure_ascii=False), cursor.lastrowid),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "property_id": state.get("property_id", payload.get("property_id", "")),
            "decision": decision,
            "risk_score": risk_score,
            "risk_flags": state.get("risk_flags", []),
            "risk_breakdown": risk_breakdown,
            "prototype_mitigation_model": prototype_mitigation_model,
            "memo_json": memo_json,
        }
    finally:
        conn.close()


def fetch_history() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, property_id, raw_input, decision, risk_score, risk_flags, risk_breakdown, prototype_mitigation_model, memo_json, record_type, created_at
            FROM submissions
            ORDER BY id DESC
            """
        ).fetchall()
        results = []
        for row in rows:
            raw_input = {}
            try:
                raw_input = json.loads(row["raw_input"]) if row["raw_input"] else {}
            except Exception:
                raw_input = {}
            risk_breakdown = {}
            try:
                risk_breakdown = json.loads(row["risk_breakdown"]) if row["risk_breakdown"] else {}
            except Exception:
                risk_breakdown = {}
            prototype_mitigation_model = {}
            try:
                prototype_mitigation_model = json.loads(row["prototype_mitigation_model"] or "{}")
            except Exception:
                prototype_mitigation_model = {}
            memo_json = {}
            try:
                memo_json = json.loads(row["memo_json"] or "{}")
            except Exception:
                memo_json = {}
            results.append(
                {
                    "id": row["id"],
                    "property_id": row["property_id"],
                    "raw_input": raw_input,
                    "decision": row["decision"],
                    "risk_score": row["risk_score"],
                    "risk_flags": [flag.strip() for flag in str(row["risk_flags"]).split(",") if flag.strip()],
                    "risk_breakdown": risk_breakdown,
                    "prototype_mitigation_model": prototype_mitigation_model,
                    "memo_json": memo_json,
                    "record_type": row["record_type"],
                    "total_value_at_risk_inr": raw_input.get("total_value_at_risk_inr", raw_input.get("tiv")),
                    "created_at": row["created_at"],
                }
            )
        return results
    finally:
        conn.close()


def fetch_submission_detail(submission_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, property_id, raw_input, decision, risk_score, risk_flags,
                     risk_breakdown, prototype_mitigation_model, memo_json,
                   record_type,
                   result_json, created_at
            FROM submissions
            WHERE id = ?
            """,
            (submission_id,),
        ).fetchone()
        if row is None:
            return None

        detail: dict[str, Any] = {}
        try:
            detail = json.loads(row["result_json"] or "{}")
        except Exception:
            detail = {}

        raw_input = {}
        try:
            raw_input = json.loads(row["raw_input"]) if row["raw_input"] else {}
        except Exception:
            raw_input = {}
        risk_breakdown = {}
        try:
            risk_breakdown = json.loads(row["risk_breakdown"]) if row["risk_breakdown"] else {}
        except Exception:
            risk_breakdown = {}
        prototype_mitigation_model = {}
        try:
            prototype_mitigation_model = json.loads(row["prototype_mitigation_model"] or "{}")
        except Exception:
            prototype_mitigation_model = {}
        memo_json = {}
        try:
            memo_json = json.loads(row["memo_json"] or "{}")
        except Exception:
            memo_json = {}

        detail.setdefault("property_id", row["property_id"])
        detail.setdefault("raw_input", raw_input)
        detail.setdefault("decision", row["decision"])
        detail.setdefault("risk_score", row["risk_score"])
        detail.setdefault("risk_flags", [flag.strip() for flag in str(row["risk_flags"]).split(",") if flag.strip()])
        detail.setdefault("risk_breakdown", risk_breakdown)
        detail.setdefault("prototype_mitigation_model", prototype_mitigation_model)
        detail.setdefault("memo_json", memo_json)
        detail.setdefault("record_type", row["record_type"])
        detail.setdefault("extracted_features", {})
        detail.setdefault("guideline_chunks", [])
        detail.setdefault("comparables", [])
        detail.setdefault("rationale", "")
        detail["ai_memo_status"] = "Available" if detail.get("memo_json") else "Unavailable"
        if detail["ai_memo_status"] != "Available":
            detail["ai_memo_reason"] = detail.get("ai_memo_reason") or "Structured AI memo was not stored for this record"
        detail.setdefault("ai_memo_reason", "")
        detail.setdefault("policy_type", raw_input.get("policy_type"))
        detail.setdefault("total_value_at_risk_inr", raw_input.get("total_value_at_risk_inr"))
        detail["id"] = row["id"]
        detail["created_at"] = row["created_at"]
        return detail
    finally:
        conn.close()


def backup_and_cleanup_demo_database(backup_path: Path) -> dict[str, Any]:
    """Back up SQLite, classify old rows, and retain only valid canonical demo data."""
    init_db()
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB_PATH, backup_path)
    conn = get_connection()
    try:
        before = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        rows = conn.execute("SELECT id, property_id, result_json FROM submissions ORDER BY id DESC").fetchall()
        canonical_ids: list[int] = []
        marker_words = ("TEST", "SMOKE", "UPLOAD", "FORMDATA", "REQUEST", "TRACE", "GROUNDED")
        for row in rows:
            property_id = str(row["property_id"] or "")
            try:
                detail = json.loads(row["result_json"] or "{}")
                valid_detail = bool(detail.get("property_id") and detail.get("decision") is not None and detail.get("risk_score") is not None)
            except Exception:
                valid_detail = False
            if property_id == "REAL-IN-TIDEL-001" and valid_detail and not canonical_ids:
                canonical_ids.append(row["id"])
        retained = set(canonical_ids)
        delete_ids = [row["id"] for row in rows if row["id"] not in retained]
        if delete_ids:
            conn.executemany("DELETE FROM submissions WHERE id = ?", [(row_id,) for row_id in delete_ids])
        conn.execute("UPDATE submissions SET record_type = 'demo' WHERE id IN ({})".format(",".join("?" for _ in canonical_ids)), canonical_ids) if canonical_ids else None
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        return {"backup_path": str(backup_path), "before": before, "after": after, "retained_ids": sorted(retained), "removed_ids": delete_ids, "timestamp": datetime.now().isoformat()}
    finally:
        conn.close()
