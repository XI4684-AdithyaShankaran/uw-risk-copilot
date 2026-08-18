import json
from unittest.mock import Mock

import requests
from google.genai.errors import ClientError

import app.agents.report_agent as report_agent


def test_generate_memo_exposes_resource_exhausted_failure(monkeypatch):
    response = requests.Response()
    response.status_code = 429
    response.reason = "RESOURCE_EXHAUSTED"
    response._content = json.dumps(
        {
            "error": {
                "message": "RESOURCE_EXHAUSTED",
                "status": "RESOURCE_EXHAUSTED",
            }
        }
    ).encode()
    quota_error = ClientError(429, response)

    client = Mock()
    client.models.generate_content.side_effect = quota_error
    monkeypatch.setattr(report_agent, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(report_agent.genai, "Client", lambda api_key, **kwargs: client)

    state = {
        "property_id": "MEMO-FAILURE-001",
        "raw_input": {"address": "100 Test Road", "city": "Mumbai"},
        "risk_score": 0,
        "risk_flags": [],
        "decision": "Accept",
        "rationale": "Deterministic score is acceptable.",
    }

    state["memo_json"] = report_agent.generate_memo(state)

    assert state["ai_memo_status"] == "Unavailable"
    assert "RESOURCE_EXHAUSTED" in state["ai_memo_reason"]
    assert state["memo_json"] == {}
    client.models.generate_content.assert_called_once()


def _valid_state():
    return {"raw_input": {"property_id": "TIDEL", "roof_age_years": None}, "decision": "Accept", "risk_score": 5, "risk_flags": ["high_tiv_concentration"]}


def test_structured_memo_accepts_grounded_response(monkeypatch):
    client = Mock()
    client.models.generate_content.return_value.text = '{"property_summary":["TIDEL"],"key_risk_factors":["high_tiv_concentration"],"coverage_review":["No additional coverage extensions requested."],"decision":"Accept","rationale":"Grounded rationale","suggested_next_steps":["Review concentration"]}'
    monkeypatch.setattr(report_agent, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(report_agent.genai, "Client", lambda api_key, **kwargs: client)
    state = _valid_state()
    memo = report_agent.generate_memo(state)
    assert memo["decision"] == "Accept"
    assert "coverage_review" in memo
    assert state["ai_memo_status"] == "Available"


def test_structured_memo_rejects_invalid_contract(monkeypatch):
    client = Mock()
    client.models.generate_content.return_value.text = '{"decision":"Accept"}'
    monkeypatch.setattr(report_agent, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(report_agent.genai, "Client", lambda api_key, **kwargs: client)
    state = _valid_state()
    assert report_agent.generate_memo(state) == {}
    assert state["ai_memo_status"] == "Incomplete"


def test_structured_memo_rejects_returned_score(monkeypatch):
    client = Mock()
    client.models.generate_content.return_value.text = '{"property_summary":["TIDEL"],"key_risk_factors":["high_tiv_concentration"],"coverage_review":["None"],"decision":"Accept","rationale":"x","suggested_next_steps":["x"],"risk_score":99}'
    monkeypatch.setattr(report_agent, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(report_agent.genai, "Client", lambda api_key, **kwargs: client)
    state = _valid_state()
    assert report_agent.generate_memo(state) == {}
    assert state["ai_memo_status"] == "Incomplete"


def test_structured_memo_rejects_decision_flag_and_roof_claims(monkeypatch):
    monkeypatch.setattr(report_agent, "GEMINI_API_KEY", "test-key")
    client = Mock()
    monkeypatch.setattr(report_agent.genai, "Client", lambda api_key, **kwargs: client)
    for response in (
        '{"property_summary":["TIDEL"],"key_risk_factors":["high_tiv_concentration"],"coverage_review":["None"],"decision":"Refer","rationale":"x","suggested_next_steps":["x"]}',
        '{"property_summary":["TIDEL"],"key_risk_factors":["invented hazard"],"coverage_review":["None"],"decision":"Accept","rationale":"x","suggested_next_steps":["x"]}',
        '{"property_summary":["TIDEL roof is 8 years old"],"key_risk_factors":["high_tiv_concentration"],"coverage_review":["None"],"decision":"Accept","rationale":"x","suggested_next_steps":["x"]}',
    ):
        client.models.generate_content.return_value.text = response
        state = _valid_state()
        assert report_agent.generate_memo(state) == {}
        assert state["ai_memo_status"] == "Incomplete"


def test_coverage_review_rejects_invented_quantitative_claims(monkeypatch):
    """coverage_review must not contain invented monetary amounts, rates, or regulatory mandates."""
    monkeypatch.setattr(report_agent, "GEMINI_API_KEY", "test-key")
    client = Mock()
    monkeypatch.setattr(report_agent.genai, "Client", lambda api_key, **kwargs: client)
    invented_claims = [
        '{"property_summary":["TIDEL"],"key_risk_factors":["high_tiv_concentration"],"coverage_review":["A ₹500,000 deductible applies."],"decision":"Accept","rationale":"x","suggested_next_steps":["x"]}',
        '{"property_summary":["TIDEL"],"key_risk_factors":["high_tiv_concentration"],"coverage_review":["5% loading rate applies."],"decision":"Accept","rationale":"x","suggested_next_steps":["x"]}',
        '{"property_summary":["TIDEL"],"key_risk_factors":["high_tiv_concentration"],"coverage_review":["Mandatory under IRDAI circular."],"decision":"Accept","rationale":"x","suggested_next_steps":["x"]}',
    ]
    for response in invented_claims:
        client.models.generate_content.return_value.text = response
        state = _valid_state()
        assert report_agent.generate_memo(state) == {}
        assert state["ai_memo_status"] == "Incomplete"


def test_coverage_review_rejects_unrequested_peril_reference(monkeypatch):
    """coverage_review must not reference a peril not present in the submission's requested coverages."""
    monkeypatch.setattr(report_agent, "GEMINI_API_KEY", "test-key")
    client = Mock()
    monkeypatch.setattr(report_agent.genai, "Client", lambda api_key, **kwargs: client)
    # earthquake_cover not requested (not in raw_input), yet memo mentions earthquake
    client.models.generate_content.return_value.text = (
        '{"property_summary":["TIDEL"],"key_risk_factors":["high_tiv_concentration"],'
        '"coverage_review":["Earthquake coverage should be reviewed due to seismic exposure."],'
        '"decision":"Accept","rationale":"x","suggested_next_steps":["x"]}'
    )
    state = _valid_state()  # raw_input has no earthquake_cover field
    assert report_agent.generate_memo(state) == {}
    assert state["ai_memo_status"] == "Incomplete"


def test_coverage_review_accepts_requested_peril_reference(monkeypatch):
    """coverage_review may reference a peril when the corresponding coverage field is True."""
    monkeypatch.setattr(report_agent, "GEMINI_API_KEY", "test-key")
    client = Mock()
    monkeypatch.setattr(report_agent.genai, "Client", lambda api_key, **kwargs: client)
    client.models.generate_content.return_value.text = (
        '{"property_summary":["TIDEL"],"key_risk_factors":["high_tiv_concentration"],'
        '"coverage_review":["Earthquake cover requested; review applicability under selected product."],'
        '"decision":"Accept","rationale":"x","suggested_next_steps":["x"]}'
    )
    state = _valid_state()
    state["raw_input"]["earthquake_cover"] = True  # explicitly requested
    memo = report_agent.generate_memo(state)
    assert memo.get("decision") == "Accept"
    assert state["ai_memo_status"] == "Available"
