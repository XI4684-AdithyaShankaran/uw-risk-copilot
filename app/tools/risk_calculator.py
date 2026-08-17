from __future__ import annotations


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

    roof_age = int(features.get("roof_age_years", 0))
    if roof_age > 30:
        score += 25
        breakdown["roof_age"] = 25
        flags.append("roof_replacement_likely")
    elif roof_age > 20:
        score += 15
        breakdown["roof_age"] = 15
        flags.append("aging_roof")

    if features.get("construction_type") == "Frame":
        score += 10
        breakdown["construction"] = 10
        flags.append("combustible_construction")

    sprinkler = str(features.get("sprinkler_system", "")).upper()
    occupancy = str(features.get("occupancy_type", ""))
    if sprinkler == "N" and occupancy in ("Warehouse", "Industrial"):
        score += 10
        breakdown["sprinkler"] = 10
        flags.append("no_sprinkler_high_hazard_occupancy")

    cat_zone = features.get("cat_zone")
    if cat_zone in ("Wildfire", "Flood", "Wind"):
        score += 20
        breakdown["cat_zone"] = 20
        flags.append("high_cat_zone_exposure")

    if features.get("seismic_zone", "II") in ("IV", "V"):
        score += 15
        breakdown["seismic_zone"] = 15
        flags.append("high_seismic_zone")

    if float(features.get("distance_to_coast_miles", 0)) < 1:
        score += 15
        breakdown["coastal"] = 15
        flags.append("coastal_wind_surge_exposure")

    if float(features.get("distance_to_fire_zone_miles", 0)) < 1:
        score += 15
        breakdown["wildland"] = 15
        flags.append("wildland_urban_interface")

    if int(features.get("prior_claims_count_5yr", 0)) > 2:
        score += 15
        breakdown["loss_history"] = 15
        flags.append("adverse_loss_history")

    if float(features.get("tiv", 0)) > 20_000_000:
        score += 5
        breakdown["tiv"] = 5
        flags.append("high_tiv_concentration")

    score = min(score, 100)
    return {"score": score, "flags": flags, "breakdown": breakdown}
