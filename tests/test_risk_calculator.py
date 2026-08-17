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


def test_low_risk_accept_high_seismic_zone_adds_fifteen_points():
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
        "seismic_zone": "V",
    }
    result = risk_score_calculator(features)
    assert result["score"] == 15
    assert "high_seismic_zone" in result["flags"]


def test_low_risk_accept_default_seismic_zone_preserves_score():
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
        "seismic_zone": "II",
    }
    result = risk_score_calculator(features)
    assert result["score"] == 0
    assert "high_seismic_zone" not in result["flags"]


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


def mitigation_features():
    return {
        "roof_age_years": 8,
        "construction_type": "Fire Resistive",
        "sprinkler_system": "N",
        "occupancy_type": "Office",
        "cat_zone": "None",
        "distance_to_coast_miles": 50,
        "distance_to_fire_zone_miles": 40,
        "prior_claims_count_5yr": 1,
        "tiv": 8_000_000,
        "fire_alarm": None,
        "flood_protection": None,
    }


def test_prototype_mitigation_baseline_with_none_fields_preserves_score():
    result = risk_score_calculator(mitigation_features())
    assert result["score"] == 0
    assert result["prototype_mitigation_model"]["mitigation_benefits"] == []
    assert result["prototype_mitigation_model"]["risk_adjusted_view"] > result["score"]


def test_prototype_mitigation_sprinkler():
    features = mitigation_features()
    features["sprinkler_system"] = "Y"
    result = risk_score_calculator(features)
    assert result["score"] == 0
    assert {item["factor"] for item in result["prototype_mitigation_model"]["mitigation_benefits"]} == {"sprinkler"}
    assert result["prototype_mitigation_model"]["mitigation_benefit"] == 40
    baseline = risk_score_calculator(mitigation_features())
    assert result["prototype_mitigation_model"]["risk_adjusted_view"] < baseline["prototype_mitigation_model"]["risk_adjusted_view"]


def test_prototype_mitigation_fire_alarm():
    features = mitigation_features()
    features["fire_alarm"] = True
    result = risk_score_calculator(features)
    assert result["score"] == 0
    assert result["prototype_mitigation_model"]["mitigation_benefits"] == [{"factor": "fire_alarm", "benefit": 20}]


def test_prototype_mitigation_flood_protection():
    features = mitigation_features()
    features["flood_protection"] = True
    result = risk_score_calculator(features)
    assert result["score"] == 0
    assert result["prototype_mitigation_model"]["mitigation_benefit"] == 25


def test_prototype_mitigation_combined_and_roof_age_adjustments():
    features = mitigation_features()
    features.update({"sprinkler_system": "Y", "fire_alarm": True, "flood_protection": True, "roof_age_years": 25})
    result = risk_score_calculator(features)
    model = result["prototype_mitigation_model"]
    assert result["score"] == 15
    assert model["mitigation_benefit"] == 85
    assert {item["factor"] for item in model["mitigation_benefits"]} == {"sprinkler", "fire_alarm", "flood_protection"}
    assert {item["factor"]: item["adjustment"] for item in model["protection_adjustments"]} == {
        "sprinkler": -40, "fire_alarm": -20, "flood_protection": -25, "roof_age": 2,
    }
