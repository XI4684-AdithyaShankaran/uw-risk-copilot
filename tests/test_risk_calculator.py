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


def test_prototype_mitigation_flood_protection_only_in_flood_zone():
    """flood_protection has benefit=25 and reduces cat_score only when cat_zone==Flood."""
    base = mitigation_features()

    # non-flood zone: benefit must be 0, adj_view must not change
    wind_no_fp = risk_score_calculator({**base, "cat_zone": "Wind", "flood_protection": False})
    wind_fp    = risk_score_calculator({**base, "cat_zone": "Wind", "flood_protection": True})
    assert wind_fp["prototype_mitigation_model"]["mitigation_benefit"] == 0
    assert wind_fp["prototype_mitigation_model"]["risk_adjusted_view"] == wind_no_fp["prototype_mitigation_model"]["risk_adjusted_view"]
    fp_benefit_wind = next((x["benefit"] for x in wind_fp["prototype_mitigation_model"]["mitigation_benefits"] if x["factor"]=="flood_protection"), None)
    assert fp_benefit_wind == 0

    # flood zone: benefit must be 20 (consistent with cat_score reduction of 20), adj_view must decrease
    flood_no_fp = risk_score_calculator({**base, "cat_zone": "Flood", "flood_protection": False})
    flood_fp    = risk_score_calculator({**base, "cat_zone": "Flood", "flood_protection": True})
    assert flood_fp["prototype_mitigation_model"]["mitigation_benefit"] == 20
    assert flood_fp["prototype_mitigation_model"]["risk_adjusted_view"] < flood_no_fp["prototype_mitigation_model"]["risk_adjusted_view"]
    fp_benefit_flood = next((x["benefit"] for x in flood_fp["prototype_mitigation_model"]["mitigation_benefits"] if x["factor"]=="flood_protection"), None)
    assert fp_benefit_flood == 20


def test_prototype_mitigation_combined_and_roof_age_adjustments():
    features = mitigation_features()
    # flood_protection benefit is 0 outside flood zone; only sprinkler+fire_alarm contribute
    features.update({"sprinkler_system": "Y", "fire_alarm": True, "flood_protection": True, "roof_age_years": 25})
    result = risk_score_calculator(features)
    model = result["prototype_mitigation_model"]
    assert result["score"] == 15
    assert model["mitigation_benefit"] == 60  # sprinkler(40) + fire_alarm(20); flood_protection=0 for non-flood zone
    fp_benefit = next((x["benefit"] for x in model["mitigation_benefits"] if x["factor"]=="flood_protection"), None)
    assert fp_benefit == 0
    assert {item["factor"]: item["adjustment"] for item in model["protection_adjustments"]} == {
        "sprinkler": -40, "fire_alarm": -20, "roof_age": 2,
    }


def test_hail_cat_zone_captured_not_scored():
    """Hail is a named STFI peril (IRDAI SFSP Tempest); captured as exposure flag, not scored."""
    base = mitigation_features()
    result_none = risk_score_calculator({**base, "cat_zone": "None"})
    result_hail = risk_score_calculator({**base, "cat_zone": "Hail"})
    assert result_hail["score"] == result_none["score"], "Hail must not change authoritative score"
    assert result_hail["breakdown"]["cat_zone"] == 0
    assert "moderate_cat_zone_captured" in result_hail["flags"]
    assert "high_cat_zone_exposure" not in result_hail["flags"]


def test_earthquake_cat_zone_captured_not_scored():
    """Earthquake is a named IRDAI SFSP peril; captured as exposure flag, not scored."""
    base = mitigation_features()
    result_none = risk_score_calculator({**base, "cat_zone": "None"})
    result_eq   = risk_score_calculator({**base, "cat_zone": "Earthquake"})
    assert result_eq["score"] == result_none["score"], "Earthquake cat_zone must not change authoritative score"
    assert result_eq["breakdown"]["cat_zone"] == 0
    assert "moderate_cat_zone_captured" in result_eq["flags"]
    assert "high_cat_zone_exposure" not in result_eq["flags"]


def test_earthquake_cat_seismic_zone_no_double_count():
    """Earthquake CAT and seismic zone IV score independently: seismic adds, earthquake does not."""
    base = mitigation_features()
    base_score = risk_score_calculator({**base, "cat_zone": "None", "seismic_zone": "II"})["score"]
    result = risk_score_calculator({**base, "cat_zone": "Earthquake", "seismic_zone": "IV"})
    # Only seismic_zone IV adds +15; earthquake cat_zone adds 0
    assert result["breakdown"]["cat_zone"] == 0
    assert result["breakdown"]["seismic_zone"] == 15
    assert result["score"] == base_score + 15
    assert "moderate_cat_zone_captured" in result["flags"]
    assert "high_seismic_zone" in result["flags"]


def result_none_score(base: dict) -> int:
    return risk_score_calculator({**base, "cat_zone": "None"})["score"]
