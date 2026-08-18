from __future__ import annotations

import math

# Authoritative scoring point values — prototype calibration, not filed rating rules
_ROOF_OLD_SCORE = 25        # roof > 30 years
_ROOF_AGING_SCORE = 15      # roof > 20 years
_FRAME_SCORE = 10           # combustible frame construction
_NO_SPRINKLER_HH = 10       # warehouse/industrial without sprinkler
_HIGH_CAT_SCORE = 20        # primary CAT perils (Wind/Flood/Wildfire)
_HIGH_SEISMIC_SCORE = 15    # seismic zone IV or V
_COASTAL_SCORE = 15         # < 1 mile to coast
_WILDLAND_SCORE = 15        # < 1 mile to wildland-urban interface
_ADVERSE_LOSS_SCORE = 15    # > 2 prior claims in 5 years
_HIGH_TIV_SCORE = 5         # TIV > ₹20M
# Flood protection declared benefit; must equal actual cat_score reduction for consistency
_FLOOD_PROTECTION_BENEFIT = 20


def _clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, round(value)))


def _safe_float(value: object, default: float = 0) -> float:
    try:
        parsed = float(value if value is not None else default)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(parsed) else parsed


def _safe_int(value: object, default: int = 0) -> int:
    return int(_safe_float(value, default))


def _risk_level(score: int) -> str:
    if score >= 85:
        return "Critical"
    if score >= 70:
        return "Very High"
    if score >= 50:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"


def _indicative_risk_action(score: int) -> str:
    """Indicative risk action for the live preview — not an authoritative underwriting decision."""
    if score >= 85:
        return "High Risk"
    if score >= 30:
        return "Elevated Risk"
    return "Standard Risk"


def prototype_mitigation_model(features: dict, authoritative_score: int) -> dict:
    """Return teammate-style live risk visualization data from Python."""
    roof_age = _safe_int(features.get("roof_age_years"))
    _yb = features.get("year_built")
    year_built = _safe_int(_yb) if _yb is not None else None
    current_year = _safe_int(features.get("current_year"), 2026)
    square_footage = max(_safe_float(features.get("square_footage"), 1000), 1)
    construction_type = str(features.get("construction_type") or "")
    occupancy_type = str(features.get("occupancy_type") or "")
    cat_zone = str(features.get("cat_zone") or "None")
    seismic_zone = str(features.get("seismic_zone") or "II")
    sprinkler_enabled = str(features.get("sprinkler_system") or "").upper() == "Y"
    fire_alarm_enabled = features.get("fire_alarm") is True
    flood_protection_enabled = features.get("flood_protection") is True

    cat_base = {"None": 12, "Hail": 35, "Wind": 62, "Flood": 68, "Wildfire": 72, "Earthquake": 58}.get(cat_zone, 25)
    if seismic_zone in ("IV", "V"):
        cat_base += 10
    if _safe_float(features.get("distance_to_coast_miles"), 99) < 1:
        cat_base += 12
    if _safe_float(features.get("distance_to_fire_zone_miles"), 99) < 1:
        cat_base += 12
    cat_score = _clamp(cat_base - (20 if flood_protection_enabled and cat_zone == "Flood" else 0))

    construction_score = {
        "Fire Resistive": 18,
        "Masonry Non-Combustible": 28,
        "Non-Combustible": 35,
        "Joisted Masonry": 48,
        "Frame": 75,
        "Masonry": 35,
        "Concrete": 24,
        "Steel": 34,
        "Wood": 78,
    }.get(construction_type, 40)
    occupancy_score = {
        "Office": 20,
        "Retail": 35,
        "Warehouse": 45,
        "Industrial": 50,
        "Mixed-Use": 42,
        "Multifamily": 38,
        "Restaurant": 45,
    }.get(occupancy_type, 30)
    protection_score = 100
    protection_score -= 40 if sprinkler_enabled else 0
    protection_score -= 20 if fire_alarm_enabled else 0
    protection_score += min(20, round((roof_age - 20) / 2)) if roof_age > 20 else 0
    protection_score = _clamp(protection_score)
    claims = _safe_int(features.get("prior_claims_count_5yr"))
    # Clamp claim amount to non-negative before log10 to prevent domain errors
    claim_amount = max(0.0, _safe_float(features.get("prior_claims_total_amount"), 0))
    loss_history_score = _clamp(claims * 12 + math.log10(claim_amount + 1) * 8)
    # age_score is an indicative visualization dimension; 0 when year_built is not supplied
    age_score = _clamp(max(0, current_year - year_built)) if year_built is not None else 0
    climate_score = _clamp(30 + (cat_score * 0.35))

    risk_profile = [
        {"id": "climate", "name": "Climate Risk", "score": climate_score},
        {"id": "cat", "name": "CAT Exposure", "score": cat_score},
        {"id": "construction", "name": "Construction Risk", "score": construction_score},
        {"id": "occupancy", "name": "Occupancy Risk", "score": occupancy_score},
        {"id": "protection", "name": "Protection Risk", "score": protection_score},
        {"id": "loss", "name": "Loss History Risk", "score": loss_history_score},
        {"id": "age", "name": "Property Age Risk", "score": age_score},
    ]
    risk_adjusted_view = _clamp(
        climate_score * 0.20
        + cat_score * 0.20
        + construction_score * 0.15
        + occupancy_score * 0.10
        + protection_score * 0.15
        + loss_history_score * 0.15
        + age_score * 0.05
    )

    benefits: list[dict[str, int | str]] = []
    adjustments: list[dict[str, int | str]] = []
    if str(features.get("sprinkler_system", "")).upper() == "Y":
        benefits.append({"factor": "sprinkler", "benefit": 40})
        adjustments.append({"factor": "sprinkler", "adjustment": -40})
    if features.get("fire_alarm") is True:
        benefits.append({"factor": "fire_alarm", "benefit": 20})
        adjustments.append({"factor": "fire_alarm", "adjustment": -20})
    if features.get("flood_protection") is True:
        if cat_zone == "Flood":
            # flood_protection reduces cat_score only in flood-zone exposure
            benefits.append({"factor": "flood_protection", "benefit": _FLOOD_PROTECTION_BENEFIT})
            adjustments.append({"factor": "flood_protection", "adjustment": -_FLOOD_PROTECTION_BENEFIT})
        else:
            benefits.append({"factor": "flood_protection", "benefit": 0})
    if roof_age > 20:
        adjustments.append({"factor": "roof_age", "adjustment": min(20, round((roof_age - 20) / 2))})
    for factor in ("generator", "drainage", "security_protective_safeguards"):
        if features.get(factor) is True:
            benefits.append({"factor": factor, "benefit": 0})
    positive_factors = [
        {"id": item["factor"], "name": str(item["factor"]).replace("_", " ").title(), "benefit": item["benefit"]}
        for item in benefits
        if int(item["benefit"]) > 0
    ]
    return {
        "model": "prototype_mitigation_model",
        "authoritative_score": authoritative_score,
        "mitigation_benefit": sum(int(item["benefit"]) for item in benefits),
        "risk_adjusted_view": risk_adjusted_view,
        "risk_level": _risk_level(risk_adjusted_view),
        "recommendation": _indicative_risk_action(risk_adjusted_view),
        "mitigation_benefits": benefits,
        "protection_adjustments": adjustments,
        "risk_profile": risk_profile,
        "positive_factors": positive_factors,
        "property_size_band": "Large" if square_footage >= 100_000 else "Standard",
    }


def risk_score_calculator(features: dict) -> dict:
    """Deterministic underwriting risk scoring rules."""
    score = 0
    flags: list[str] = []
    breakdown: dict[str, int] = {
        "roof_age": 0,
        "construction": 0,
        "sprinkler": 0,
        "cat_zone": 0,
        "seismic_zone": 0,
        "coastal": 0,
        "wildland": 0,
        "loss_history": 0,
        "tiv": 0,
    }

    roof_age = _safe_int(features.get("roof_age_years"))
    if roof_age > 30:
        score += _ROOF_OLD_SCORE
        breakdown["roof_age"] = _ROOF_OLD_SCORE
        flags.append("roof_replacement_likely")
    elif roof_age > 20:
        score += _ROOF_AGING_SCORE
        breakdown["roof_age"] = _ROOF_AGING_SCORE
        flags.append("aging_roof")

    if features.get("construction_type") == "Frame":
        score += _FRAME_SCORE
        breakdown["construction"] = _FRAME_SCORE
        flags.append("combustible_construction")

    sprinkler = str(features.get("sprinkler_system", "")).upper()
    occupancy = str(features.get("occupancy_type", ""))
    if sprinkler == "N" and occupancy in ("Warehouse", "Industrial"):
        score += _NO_SPRINKLER_HH
        breakdown["sprinkler"] = _NO_SPRINKLER_HH
        flags.append("no_sprinkler_high_hazard_occupancy")

    cat_zone = features.get("cat_zone")
    # Primary CAT perils only → authoritative scoring (Wind/Flood/Wildfire are well-calibrated)
    if cat_zone in ("Wildfire", "Flood", "Wind"):
        score += _HIGH_CAT_SCORE
        breakdown["cat_zone"] = _HIGH_CAT_SCORE
        flags.append("high_cat_zone_exposure")
    # Hail/Earthquake: captured as exposure indicator; no authoritative score (no calibrated rule)
    elif cat_zone in ("Hail", "Earthquake"):
        flags.append("moderate_cat_zone_captured")

    if features.get("seismic_zone", "II") in ("IV", "V"):
        score += _HIGH_SEISMIC_SCORE
        breakdown["seismic_zone"] = _HIGH_SEISMIC_SCORE
        flags.append("high_seismic_zone")

    # Use _safe_float with explicit non-negative guard to prevent bad inputs triggering flags
    _coast = _safe_float(features.get("distance_to_coast_miles"), 99)
    if features.get("distance_to_coast_miles") is not None and 0 <= _coast < 1:
        score += _COASTAL_SCORE
        breakdown["coastal"] = _COASTAL_SCORE
        flags.append("coastal_wind_surge_exposure")

    _firezone = _safe_float(features.get("distance_to_fire_zone_miles"), 99)
    if features.get("distance_to_fire_zone_miles") is not None and 0 <= _firezone < 1:
        score += _WILDLAND_SCORE
        breakdown["wildland"] = _WILDLAND_SCORE
        flags.append("wildland_urban_interface")

    if _safe_int(features.get("prior_claims_count_5yr")) > 2:
        score += _ADVERSE_LOSS_SCORE
        breakdown["loss_history"] = _ADVERSE_LOSS_SCORE
        flags.append("adverse_loss_history")

    if _safe_float(features.get("tiv")) > 20_000_000:
        score += _HIGH_TIV_SCORE
        breakdown["tiv"] = _HIGH_TIV_SCORE
        flags.append("high_tiv_concentration")

    score = min(score, 100)
    model_features = {**features, "risk_breakdown": breakdown}
    return {
        "score": score,
        "flags": flags,
        "breakdown": breakdown,
        "prototype_mitigation_model": prototype_mitigation_model(model_features, score),
    }
