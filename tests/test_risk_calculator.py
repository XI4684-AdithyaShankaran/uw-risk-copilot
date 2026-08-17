from app.tools.risk_calculator import risk_score_calculator


def test_low_risk_accept():
    features = {
        "roof_age_years": 8,
        "construction_type": "Fire Resistive",
        "sprinkler_system": "Y",
        "occupancy_type": "Office",
        "cat_zone": "None",
        "distance_to_coast_miles": 50,
        "distance_to_fire_zone_miles": 40,
        "prior_claims_count_5yr": 1,
        "tiv": 8_000_000,
    }
    result = risk_score_calculator(features)
    assert result["score"] == 0
    assert result["flags"] == []


def test_mid_risk_refer():
    features = {
        "roof_age_years": 25,
        "construction_type": "Frame",
        "sprinkler_system": "Y",
        "occupancy_type": "Warehouse",
        "cat_zone": "Wind",
        "distance_to_coast_miles": 0.5,
        "distance_to_fire_zone_miles": 2,
        "prior_claims_count_5yr": 2,
        "tiv": 12_000_000,
    }
    result = risk_score_calculator(features)
    assert 31 <= result["score"] <= 60
    assert "aging_roof" in result["flags"]


def test_high_risk_auto_decline():
    features = {
        "roof_age_years": 35,
        "construction_type": "Frame",
        "sprinkler_system": "N",
        "occupancy_type": "Industrial",
        "cat_zone": "Wildfire",
        "distance_to_coast_miles": 0.2,
        "distance_to_fire_zone_miles": 0.5,
        "prior_claims_count_5yr": 4,
        "tiv": 25_000_000,
    }
    result = risk_score_calculator(features)
    assert result["score"] >= 85
    assert "roof_replacement_likely" in result["flags"]
    assert "auto_decline" not in result["flags"]
