from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PropertySubmission(BaseModel):
    model_config = ConfigDict(extra="ignore")

    proposer_name: str | None = None
    insured_legal_name: str | None = None
    business_name: str | None = None
    contact_person: str | None = None
    designation: str | None = None
    mobile: str | None = None
    email: str | None = None
    policy_period_start: date | None = None
    policy_period_end: date | None = None
    interested_parties: str | None = None
    financial_institution: str | None = None
    property_id: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    zip: str = Field(..., min_length=1)
    latitude: float
    longitude: float
    construction_type: str
    year_built: int
    wall_material: str | None = None
    floor_material: str | None = None
    roof_material: str | None = None
    building_height_m: float | None = None
    roof_type: str | None = None
    roof_age_years: int | None = None
    square_footage: int
    occupancy_type: str
    business_activity: str | None = None
    is_manufacturing: bool | None = None
    manufacturing_process: str | None = None
    is_warehouse_storage: bool | None = None
    goods_stored: str | None = None
    num_stories: int
    sprinkler_system: str
    fire_alarm: bool | None = None
    flood_protection: bool | None = None
    generator: bool | None = None
    drainage: bool | None = None
    security_protective_safeguards: bool | None = None
    cat_zone: Literal["Wind", "Hail", "Wildfire", "Flood", "Earthquake", "None"]
    policy_type: Literal["SFSP", "Bharat Sookshma Udyam Suraksha", "Bharat Laghu Udyam Suraksha", "Larger-risk/commercial property segment"] | None = None
    total_value_at_risk_inr: float | None = None
    seismic_zone: Literal["II", "III", "IV", "V"] = "II"
    # Coverage selection only — descriptive, not scored in this prototype.
    rsmd_cover: bool | None = None
    terrorism_cover: bool | None = None
    earthquake_cover: bool | None = None
    flood_cover: bool | None = None
    cyclone_wind_cover: bool | None = None
    distance_to_coast_miles: float | None = None
    distance_to_fire_zone_miles: float | None = None
    prior_claims_count_5yr: int | None = None
    prior_claims_total_amount: float | None = None
    last_loss_date: date | None = None
    building_value_inr: float | None = None
    plant_machinery_value_inr: float | None = None
    furniture_fixtures_equipment_value_inr: float | None = None
    stock_inventory_value_inr: float | None = None
    other_contents_value_inr: float | None = None
    contents_value_inr: float | None = None
    business_interruption_cover: bool | None = None
    business_interruption_value_inr: float | None = None
    annual_gross_profit_inr: float | None = None
    indemnity_period_months: int | None = None
    tiv: float | None = None
    submission_date: str


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
