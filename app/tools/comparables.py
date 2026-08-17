from __future__ import annotations

import sqlite3
from typing import Any

from app.config import DB_PATH


def comparable_lookup(features: dict, k: int = 5) -> list[dict]:
    """Return similar properties from SQLite based on matching underwriting attributes."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT property_id, address, city, state, construction_type, occupancy_type,
                   cat_zone, year_built, roof_age_years, square_footage, tiv, prior_claims_count_5yr
            FROM properties
            WHERE construction_type = ? AND occupancy_type = ? AND cat_zone = ?
            ORDER BY ABS(square_footage - ?) ASC
            LIMIT ?
        """
        rows = conn.execute(
            query,
            (
                features.get("construction_type"),
                features.get("occupancy_type"),
                features.get("cat_zone"),
                float(features.get("square_footage", 0)),
                k,
            ),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
