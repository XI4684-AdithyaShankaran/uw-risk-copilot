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
                memo_markdown TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    ensure_properties_table()
    seed_properties_from_csv()


def save_submission(state: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = get_connection()
    try:
        payload = state.get("raw_input", {})
        decision = state.get("decision", "")
        risk_score = state.get("risk_score", 0)
        risk_flags = ", ".join(state.get("risk_flags", []))
        risk_breakdown = state.get("risk_breakdown", {})
        memo = state.get("memo_markdown", "")

        cursor = conn.execute(
            """
            INSERT INTO submissions (property_id, raw_input, decision, risk_score, risk_flags, risk_breakdown, memo_markdown)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.get("property_id", payload.get("property_id", "")),
                json.dumps(payload, ensure_ascii=False),
                decision,
                risk_score,
                risk_flags,
                json.dumps(risk_breakdown, ensure_ascii=False),
                memo,
            ),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "property_id": state.get("property_id", payload.get("property_id", "")),
            "decision": decision,
            "risk_score": risk_score,
            "risk_flags": state.get("risk_flags", []),
            "risk_breakdown": risk_breakdown,
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
            SELECT id, property_id, raw_input, decision, risk_score, risk_flags, risk_breakdown, memo_markdown, created_at
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
            results.append(
                {
                    "id": row["id"],
                    "property_id": row["property_id"],
                    "raw_input": raw_input,
                    "decision": row["decision"],
                    "risk_score": row["risk_score"],
                    "risk_flags": [flag.strip() for flag in str(row["risk_flags"]).split(",") if flag.strip()],
                    "risk_breakdown": risk_breakdown,
                    "memo_markdown": row["memo_markdown"],
                    "created_at": row["created_at"],
                }
            )
        return results
    finally:
        conn.close()
