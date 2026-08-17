from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.graph import run_graph
from app.config import DB_PATH
from app.db import fetch_history, init_db, save_submission
from app.schemas import indicative_product_segment

app = FastAPI(title="UW Risk Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/underwrite/submit")
async def submit_underwriting(
    property_id: str = Form(...),
    address: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    zip: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    construction_type: str = Form(...),
    year_built: int = Form(...),
    roof_type: str = Form(...),
    roof_age_years: int = Form(...),
    square_footage: int = Form(...),
    occupancy_type: str = Form(...),
    num_stories: int = Form(...),
    sprinkler_system: str = Form(...),
    cat_zone: str = Form(...),
    policy_type: str | None = Form(default=None),
    seismic_zone: str = Form(default="II"),
    rsmd_cover: bool | None = Form(default=None),
    distance_to_coast_miles: float = Form(...),
    distance_to_fire_zone_miles: float = Form(...),
    prior_claims_count_5yr: int = Form(...),
    prior_claims_total_amount: float = Form(...),
    tiv: float = Form(...),
    submission_date: str = Form(...),
    image: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    total_value_at_risk_inr = tiv
    derived_policy_type = indicative_product_segment(total_value_at_risk_inr)
    raw_input = {
        "property_id": property_id,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip,
        "latitude": latitude,
        "longitude": longitude,
        "construction_type": construction_type,
        "year_built": year_built,
        "roof_type": roof_type,
        "roof_age_years": roof_age_years,
        "square_footage": square_footage,
        "occupancy_type": occupancy_type,
        "num_stories": num_stories,
        "sprinkler_system": sprinkler_system,
        "cat_zone": cat_zone,
        "policy_type": derived_policy_type,
        "total_value_at_risk_inr": total_value_at_risk_inr,
        "seismic_zone": seismic_zone,
        "rsmd_cover": rsmd_cover,
        "distance_to_coast_miles": distance_to_coast_miles,
        "distance_to_fire_zone_miles": distance_to_fire_zone_miles,
        "prior_claims_count_5yr": prior_claims_count_5yr,
        "prior_claims_total_amount": prior_claims_total_amount,
        "tiv": tiv,
        "submission_date": submission_date,
    }
    image_path = None
    if image is not None:
        local_dir = DB_PATH.parent / "images_uploads"
        local_dir.mkdir(parents=True, exist_ok=True)
        image_path = str(local_dir / f"{property_id}_{image.filename}")
        image_bytes = await image.read()
        with open(image_path, "wb") as out:
            out.write(image_bytes)
        print("IMAGE_RECEIVED=true")
        print(f"IMAGE_SIZE_BYTES={len(image_bytes)}")
        print(f"IMAGE_MIME_TYPE={image.content_type or 'unknown'}")
        print(f"[POST /underwrite/submit] IMAGE RECEIVED: {image.filename}, SIZE: {len(image_bytes)} bytes")

    result = run_graph(raw_input, image_path=image_path)
    result["raw_input"] = raw_input
    result["policy_type"] = derived_policy_type
    result["total_value_at_risk_inr"] = total_value_at_risk_inr
    result["ai_memo_status"] = "Available" if result.get("memo_markdown") else "Unavailable"
    result["ai_memo_reason"] = result.get("memo_error") if not result.get("memo_markdown") else ""
    print(f"FINAL_EXTRACTED_FEATURE_KEYS={sorted(result.get('extracted_features', {}).keys())}")
    save_submission(result)
    return result


@app.get("/underwrite/history")
def history() -> list[dict[str, Any]]:
    return fetch_history()
