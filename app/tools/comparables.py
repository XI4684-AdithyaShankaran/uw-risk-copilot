from __future__ import annotations

import math
import sqlite3

from app.config import DB_PATH

# Prototype similarity weights — not insurer-calibrated
_SIMILARITY_WEIGHTS = {"square_footage": 0.30, "tiv": 0.30, "year_built": 0.20, "roof_age_years": 0.10, "prior_claims_count_5yr": 0.10}
_SCALES = {"square_footage": 1_000_000, "tiv": 1_000_000_000, "year_built": 50, "roof_age_years": 30, "prior_claims_count_5yr": 5}
_K_MIN, _K_MAX = 1, 20

_SELECT_COLS = "property_id, address, city, state, construction_type, occupancy_type, cat_zone, year_built, roof_age_years, square_footage, tiv, prior_claims_count_5yr"


def _safe(value: object) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        f = float(value)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _similarity_distance(target: dict, row: dict) -> float:
    dist = 0.0
    for field, weight in _SIMILARITY_WEIGHTS.items():
        tv, rv = _safe(target.get(field)), _safe(row.get(field))
        if tv is not None and rv is not None:
            scale = _SCALES.get(field) or 1
            dist += weight * abs(tv - rv) / scale
    return dist


def comparable_lookup(features: dict, k: int = 5) -> list[dict]:
    """Return reference properties from SQLite ranked by multi-attribute similarity.

    These are synthetic reference records, not verified market comparables.
    """
    k = max(_K_MIN, min(_K_MAX, k))
    target_id = features.get("property_id")
    target_sqft = _safe(features.get("square_footage"))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Fetch candidates matching primary underwriting attributes (relaxed to avoid empty result)
        candidates: list[sqlite3.Row] = []
        for query, params in [
            # Level 1: exact occupancy + construction + CAT match
            (
                f"SELECT {_SELECT_COLS} FROM properties WHERE construction_type = ? AND occupancy_type = ? AND cat_zone = ?{' AND property_id != ?' if target_id else ''} LIMIT 50",
                (features.get("construction_type"), features.get("occupancy_type"), features.get("cat_zone")) + ((target_id,) if target_id else ()),
            ),
            # Level 2: occupancy + construction match (relax CAT)
            (
                f"SELECT {_SELECT_COLS} FROM properties WHERE construction_type = ? AND occupancy_type = ?{' AND property_id != ?' if target_id else ''} LIMIT 50",
                (features.get("construction_type"), features.get("occupancy_type")) + ((target_id,) if target_id else ()),
            ),
            # Level 3: occupancy match only
            (
                f"SELECT {_SELECT_COLS} FROM properties WHERE occupancy_type = ?{' AND property_id != ?' if target_id else ''} LIMIT 50",
                (features.get("occupancy_type"),) + ((target_id,) if target_id else ()),
            ),
        ]:
            rows = conn.execute(query, params).fetchall()
            if rows:
                candidates = rows
                break

        if not candidates:
            return []

        # Rank in Python using weighted multi-attribute similarity
        ranked = sorted(
            (dict(row) for row in candidates),
            key=lambda row: (_similarity_distance(features, row), row.get("property_id", "")),
        )
        return ranked[:k]
    finally:
        conn.close()
