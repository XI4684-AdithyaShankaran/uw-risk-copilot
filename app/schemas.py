from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DECISION_THRESHOLDS = {
    "Accept": (0, 30),
    "Refer": (31, 60),
    "Decline (mitigation possible)": (61, 84),
    "Auto-Decline": (85, 100),
}


class PropertySubmission(BaseModel):
    model_config = ConfigDict(extra="ignore")

    property_id: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    zip: str = Field(..., min_length=1)
    latitude: float
    longitude: float
    construction_type: str
    year_built: int
    roof_type: str
    roof_age_years: int
    square_footage: int
    occupancy_type: str
    num_stories: int
    sprinkler_system: str
    cat_zone: Literal["Wind", "Hail", "Wildfire", "Flood", "Earthquake", "None"]
    policy_type: Literal["SFSP", "Bharat Sookshma Udyam Suraksha", "Bharat Laghu Udyam Suraksha", "Larger-risk/commercial property segment"] | None = None
    total_value_at_risk_inr: float | None = None
    seismic_zone: Literal["II", "III", "IV", "V"] = "II"
    rsmd_cover: bool | None = None
    distance_to_coast_miles: float
    distance_to_fire_zone_miles: float
    prior_claims_count_5yr: int
    prior_claims_total_amount: float
    tiv: float
    submission_date: str


class UWDecision(BaseModel):
    decision: str
    rationale: str


def decision_from_score(score: int) -> str:
    if 0 <= score <= 30:
        return "Accept"
    if 31 <= score <= 60:
        return "Refer"
    if 61 <= score <= 84:
        return "Decline (mitigation possible)"
    return "Auto-Decline"


def indicative_product_segment(total_value_at_risk_inr: float) -> str:
    if total_value_at_risk_inr <= 50_000_000:
        return "Bharat Sookshma Udyam Suraksha"
    if total_value_at_risk_inr <= 500_000_000:
        return "Bharat Laghu Udyam Suraksha"
    return "Larger-risk/commercial property segment"


def build_default_state() -> dict[str, Any]:
    return {
        "property_id": "",
        "raw_input": {},
        "image_path": None,
        "extracted_features": {},
        "guideline_chunks": [],
        "risk_score": 0,
        "risk_flags": [],
        "risk_breakdown": {},
        "comparables": [],
        "decision": "Accept",
        "rationale": "",
        "memo_markdown": "",
    }
