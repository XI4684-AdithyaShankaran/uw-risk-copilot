from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.config import DB_PATH, PROPERTIES_CSV


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
                        float(row.get("latitude") or 0),
                        float(row.get("longitude") or 0),
                        row.get("construction_type"),
                        int(row.get("year_built") or 0),
                        row.get("roof_type"),
                        int(row.get("roof_age_years") or 0),
                        int(row.get("square_footage") or 0),
                        row.get("occupancy_type"),
                        int(row.get("num_stories") or 0),
                        row.get("sprinkler_system"),
                        row.get("cat_zone"),
                        float(row.get("distance_to_coast_miles") or 0),
                        float(row.get("distance_to_fire_zone_miles") or 0),
                        int(row.get("prior_claims_count_5yr") or 0),
                        float(row.get("prior_claims_total_amount") or 0),
                        float(row.get("tiv") or 0),
                        row.get("submission_date"),
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
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
                memo_markdown TEXT,
                result_json TEXT,
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
    finally:
        conn.close()


def save_submission(state: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = get_connection()
    try:
        payload = state.get("raw_input", {})
        decision = state.get("decision", "")
        risk_score = state.get("risk_score", 0)
        risk_flags = ", ".join(state.get("risk_flags", []))
        risk_breakdown = state.get("risk_breakdown", {})
        prototype_mitigation_model = state.get("prototype_mitigation_model", {})
        memo = state.get("memo_markdown", "")
        result_json = json.dumps(state, ensure_ascii=False)

        cursor = conn.execute(
            """
            INSERT INTO submissions (
                property_id, raw_input, decision, risk_score, risk_flags,
                risk_breakdown, prototype_mitigation_model, memo_markdown, result_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.get("property_id", payload.get("property_id", "")),
                json.dumps(payload, ensure_ascii=False),
                decision,
                risk_score,
                risk_flags,
                json.dumps(risk_breakdown, ensure_ascii=False),
                json.dumps(prototype_mitigation_model, ensure_ascii=False),
                memo,
                result_json,
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
            "memo_markdown": memo,
        }
    finally:
        conn.close()


def fetch_history() -> list[dict[str, Any]]:
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, property_id, raw_input, decision, risk_score, risk_flags, risk_breakdown, prototype_mitigation_model, memo_markdown, created_at
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
                    "memo_markdown": row["memo_markdown"],
                    "total_value_at_risk_inr": raw_input.get("total_value_at_risk_inr", raw_input.get("tiv")),
                    "created_at": row["created_at"],
                }
            )
        return results
    finally:
        conn.close()


def fetch_submission_detail(submission_id: int) -> dict[str, Any] | None:
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, property_id, raw_input, decision, risk_score, risk_flags,
                   risk_breakdown, prototype_mitigation_model, memo_markdown,
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

        detail.setdefault("property_id", row["property_id"])
        detail.setdefault("raw_input", raw_input)
        detail.setdefault("decision", row["decision"])
        detail.setdefault("risk_score", row["risk_score"])
        detail.setdefault("risk_flags", [flag.strip() for flag in str(row["risk_flags"]).split(",") if flag.strip()])
        detail.setdefault("risk_breakdown", risk_breakdown)
        detail.setdefault("prototype_mitigation_model", prototype_mitigation_model)
        detail.setdefault("memo_markdown", row["memo_markdown"] or "")
        detail.setdefault("extracted_features", {})
        detail.setdefault("guideline_chunks", [])
        detail.setdefault("comparables", [])
        detail.setdefault("rationale", "")
        detail.setdefault("ai_memo_status", "Available" if detail.get("memo_markdown") else "Unavailable")
        detail.setdefault("ai_memo_reason", "")
        detail.setdefault("policy_type", raw_input.get("policy_type"))
        detail.setdefault("total_value_at_risk_inr", raw_input.get("total_value_at_risk_inr"))
        detail["id"] = row["id"]
        detail["created_at"] = row["created_at"]
        return detail
    finally:
        conn.close()
