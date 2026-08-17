from __future__ import annotations

import csv
import json
import argparse
import random

from app.agents.graph import run_graph
from app.config import DB_PATH, PROPERTIES_CSV
from app.db import init_db


def load_properties() -> list[dict]:
    rows = []
    with PROPERTIES_CSV.open("r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append({k: (v if v != "" else None) for k, v in row.items()})
    return rows


def persist_scores(limit: int | None = None) -> None:
    init_db()
    records = load_properties()
    selected_records = random.sample(records, min(limit, len(records))) if limit is not None else records
    completed = 0
    errors = []
    for record in selected_records:
        try:
            raw = {
                "property_id": record["property_id"],
                "address": record["address"],
                "city": record["city"],
                "state": record["state"],
                "zip": record["zip"],
                "latitude": float(record["latitude"]),
                "longitude": float(record["longitude"]),
                "construction_type": record["construction_type"],
                "year_built": int(record["year_built"]),
                "roof_type": record["roof_type"],
                "roof_age_years": int(record["roof_age_years"]),
                "square_footage": int(record["square_footage"]),
                "occupancy_type": record["occupancy_type"],
                "num_stories": int(record["num_stories"]),
                "sprinkler_system": record["sprinkler_system"],
                "cat_zone": record["cat_zone"],
                "distance_to_coast_miles": float(record["distance_to_coast_miles"]),
                "distance_to_fire_zone_miles": float(record["distance_to_fire_zone_miles"]),
                "prior_claims_count_5yr": int(record["prior_claims_count_5yr"]),
                "prior_claims_total_amount": float(record["prior_claims_total_amount"]),
                "tiv": float(record["tiv"]),
                "submission_date": record["submission_date"],
            }
            result = run_graph(raw)
            from app.db import save_submission
            save_submission(result)
            completed += 1
        except Exception as exc:
            errors.append((record["property_id"], f"{type(exc).__name__}: {exc}"))
            print(f"ERROR {record['property_id']}: {type(exc).__name__}: {exc}")
    print(f"Processed {completed} properties into SQLite.")
    print(f"Errors: {len(errors)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Randomly process at most this many properties.")
    args = parser.parse_args()
    persist_scores(limit=args.limit)
