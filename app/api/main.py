from __future__ import annotations

import json
import math
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import DB_PATH
from app.db import fetch_history, fetch_submission_detail, init_db, save_submission
from app.schemas import indicative_product_segment

app = FastAPI(title="UW Risk Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def property_tiv_from_components(*values: float | None, fallback: float | None) -> float | None:
    supplied = [value for value in values if value is not None]
    if supplied:
        return sum(supplied)
    return fallback


@app.post("/underwrite/submit")
async def submit_underwriting(
    proposer_name: str | None = Form(default=None),
    insured_legal_name: str | None = Form(default=None),
    business_name: str | None = Form(default=None),
    contact_person: str | None = Form(default=None),
    designation: str | None = Form(default=None),
    mobile: str | None = Form(default=None),
    email: str | None = Form(default=None),
    policy_period_start: str | None = Form(default=None),
    policy_period_end: str | None = Form(default=None),
    interested_parties: str | None = Form(default=None),
    financial_institution: str | None = Form(default=None),
    property_id: str = Form(...),
    address: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    zip: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    construction_type: str = Form(...),
    year_built: int = Form(...),
    wall_material: str | None = Form(default=None),
    floor_material: str | None = Form(default=None),
    roof_material: str | None = Form(default=None),
    building_height_m: float | None = Form(default=None),
    roof_type: str | None = Form(default=None),
    roof_age_years: int | None = Form(default=None),
    square_footage: int = Form(...),
    occupancy_type: str = Form(...),
    business_activity: str | None = Form(default=None),
    is_manufacturing: bool | None = Form(default=None),
    manufacturing_process: str | None = Form(default=None),
    is_warehouse_storage: bool | None = Form(default=None),
    goods_stored: str | None = Form(default=None),
    num_stories: int = Form(...),
    sprinkler_system: str = Form(...),
    fire_alarm: bool | None = Form(default=None),
    flood_protection: bool | None = Form(default=None),
    generator: bool | None = Form(default=None),
    drainage: bool | None = Form(default=None),
    security_protective_safeguards: bool | None = Form(default=None),
    cat_zone: str = Form(...),
    policy_type: str | None = Form(default=None),
    seismic_zone: str = Form(default="II"),
    rsmd_cover: bool | None = Form(default=None),
    terrorism_cover: bool | None = Form(default=None),
    earthquake_cover: bool | None = Form(default=None),
    flood_cover: bool | None = Form(default=None),
    cyclone_wind_cover: bool | None = Form(default=None),
    distance_to_coast_miles: float | None = Form(default=None),
    distance_to_fire_zone_miles: float | None = Form(default=None),
    prior_claims_count_5yr: int | None = Form(default=None),
    prior_claims_total_amount: float | None = Form(default=None),
    last_loss_date: str | None = Form(default=None),
    building_value_inr: float | None = Form(default=None),
    plant_machinery_value_inr: float | None = Form(default=None),
    furniture_fixtures_equipment_value_inr: float | None = Form(default=None),
    stock_inventory_value_inr: float | None = Form(default=None),
    other_contents_value_inr: float | None = Form(default=None),
    contents_value_inr: float | None = Form(default=None),
    business_interruption_cover: bool | None = Form(default=None),
    business_interruption_value_inr: float | None = Form(default=None),
    annual_gross_profit_inr: float | None = Form(default=None),
    indemnity_period_months: int | None = Form(default=None),
    tiv: float | None = Form(default=None),
    submission_date: str = Form(...),
    image: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    total_value_at_risk_inr = property_tiv_from_components(
        building_value_inr,
        plant_machinery_value_inr,
        furniture_fixtures_equipment_value_inr,
        stock_inventory_value_inr,
        other_contents_value_inr if other_contents_value_inr is not None else contents_value_inr,
        fallback=tiv,
    )
    derived_policy_type = indicative_product_segment(total_value_at_risk_inr) if total_value_at_risk_inr is not None else policy_type
    raw_input = {
        "proposer_name": proposer_name,
        "insured_legal_name": insured_legal_name,
        "business_name": business_name,
        "contact_person": contact_person,
        "designation": designation,
        "mobile": mobile,
        "email": email,
        "policy_period_start": policy_period_start,
        "policy_period_end": policy_period_end,
        "interested_parties": interested_parties,
        "financial_institution": financial_institution,
        "property_id": property_id,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip,
        "latitude": latitude,
        "longitude": longitude,
        "construction_type": construction_type,
        "year_built": year_built,
        "wall_material": wall_material,
        "floor_material": floor_material,
        "roof_material": roof_material,
        "building_height_m": building_height_m,
        "roof_type": roof_type,
        "roof_age_years": roof_age_years,
        "square_footage": square_footage,
        "occupancy_type": occupancy_type,
        "business_activity": business_activity,
        "is_manufacturing": is_manufacturing,
        "manufacturing_process": manufacturing_process,
        "is_warehouse_storage": is_warehouse_storage,
        "goods_stored": goods_stored,
        "num_stories": num_stories,
        "sprinkler_system": sprinkler_system,
        "fire_alarm": fire_alarm,
        "flood_protection": flood_protection,
        "generator": generator,
        "drainage": drainage,
        "security_protective_safeguards": security_protective_safeguards,
        "cat_zone": cat_zone,
        "policy_type": derived_policy_type,
        "total_value_at_risk_inr": total_value_at_risk_inr,
        "seismic_zone": seismic_zone,
        "rsmd_cover": rsmd_cover,
        "terrorism_cover": terrorism_cover,
        "earthquake_cover": earthquake_cover,
        "flood_cover": flood_cover,
        "cyclone_wind_cover": cyclone_wind_cover,
        "distance_to_coast_miles": distance_to_coast_miles,
        "distance_to_fire_zone_miles": distance_to_fire_zone_miles,
        "prior_claims_count_5yr": prior_claims_count_5yr,
        "prior_claims_total_amount": prior_claims_total_amount,
        "last_loss_date": last_loss_date,
        "building_value_inr": building_value_inr,
        "plant_machinery_value_inr": plant_machinery_value_inr,
        "furniture_fixtures_equipment_value_inr": furniture_fixtures_equipment_value_inr,
        "stock_inventory_value_inr": stock_inventory_value_inr,
        "other_contents_value_inr": other_contents_value_inr,
        "contents_value_inr": contents_value_inr,
        "business_interruption_cover": business_interruption_cover,
        "business_interruption_value_inr": business_interruption_value_inr,
        "annual_gross_profit_inr": annual_gross_profit_inr,
        "indemnity_period_months": indemnity_period_months,
        "tiv": total_value_at_risk_inr,
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

    from app.agents.graph import run_graph
    result = run_graph(raw_input, image_path=image_path)
    result["raw_input"] = raw_input
    result["policy_type"] = derived_policy_type
    result["total_value_at_risk_inr"] = total_value_at_risk_inr
    result["prototype_mitigation_model"] = result.get("prototype_mitigation_model", {})
    model = result["prototype_mitigation_model"]
    result["authoritative_risk_score"] = result["risk_score"]
    result["mitigation_benefits"] = model.get("mitigation_benefits", [])
    result["prototype_mitigation_total"] = model.get("mitigation_benefit", 0)
    result["positive_factors"] = model.get("positive_factors", [])
    result["risk_profile"] = model.get("risk_profile", [])
    result["ai_memo_status"] = "Available" if result.get("memo_markdown") else "Unavailable"
    result["ai_memo_reason"] = result.get("memo_error") if not result.get("memo_markdown") else ""
    print(f"FINAL_EXTRACTED_FEATURE_KEYS={sorted(result.get('extracted_features', {}).keys())}")
    saved = save_submission(result)
    result["id"] = saved.get("id")
    return result


@app.post("/underwrite/preview")
async def preview_underwriting(request: Request) -> dict[str, Any]:
    """Run deterministic backend recalculation without creating a history record."""
    form = await request.form()

    def text(name: str) -> str | None:
        raw = form.get(name)
        return str(raw) if raw not in (None, "") else None

    def number(name: str) -> float | None:
        raw = text(name)
        if raw is None:
            return None
        try:
            parsed = float(raw)
        except ValueError:
            return None
        return None if math.isnan(parsed) else parsed

    def boolean(name: str) -> bool | None:
        raw = text(name)
        return None if raw is None else raw.lower() in ("true", "1", "yes", "on")

    preview_tiv = property_tiv_from_components(
        number("building_value_inr"),
        number("plant_machinery_value_inr"),
        number("furniture_fixtures_equipment_value_inr"),
        number("stock_inventory_value_inr"),
        number("other_contents_value_inr") if number("other_contents_value_inr") is not None else number("contents_value_inr"),
        fallback=number("tiv"),
    )
    features = {
        "roof_age_years": int(number("roof_age_years") or 0),
        "year_built": int(number("year_built") or 2000),
        "square_footage": number("square_footage") or 1000,
        "construction_type": text("construction_type"),
        "sprinkler_system": text("sprinkler_system"),
        "occupancy_type": text("occupancy_type"),
        "cat_zone": text("cat_zone"),
        "seismic_zone": text("seismic_zone") or "II",
        "distance_to_coast_miles": number("distance_to_coast_miles"),
        "distance_to_fire_zone_miles": number("distance_to_fire_zone_miles"),
        "prior_claims_count_5yr": number("prior_claims_count_5yr"),
        "prior_claims_total_amount": number("prior_claims_total_amount"),
        "tiv": preview_tiv,
        "fire_alarm": boolean("fire_alarm"),
        "flood_protection": boolean("flood_protection"),
        "generator": boolean("generator"),
        "drainage": boolean("drainage"),
        "security_protective_safeguards": boolean("security_protective_safeguards"),
    }
    from app.tools.risk_calculator import risk_score_calculator
    score_data = risk_score_calculator(features)
    model = score_data["prototype_mitigation_model"]
    return {
        "risk_score": score_data["score"],
        "authoritative_risk_score": score_data["score"],
        "risk_flags": score_data["flags"],
        "risk_breakdown": score_data["breakdown"],
        "prototype_mitigation_model": model,
        "mitigation_benefits": model["mitigation_benefits"],
        "prototype_mitigation_total": model["mitigation_benefit"],
        "positive_factors": model["positive_factors"],
        "risk_profile": model["risk_profile"],
    }


@app.get("/underwrite/history")
def history() -> list[dict[str, Any]]:
    return fetch_history()


@app.get("/underwrite/history/{submission_id}")
def history_detail(submission_id: int) -> dict[str, Any]:
    detail = fetch_submission_detail(submission_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return detail
