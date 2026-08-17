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
    monkeypatch.setattr(report_agent.genai, "Client", lambda api_key: client)

    state = {
        "property_id": "MEMO-FAILURE-001",
        "raw_input": {"address": "100 Test Road", "city": "Mumbai"},
        "risk_score": 0,
        "risk_flags": [],
        "decision": "Accept",
        "rationale": "Deterministic score is acceptable.",
    }

    state["memo_markdown"] = report_agent.generate_memo(state)
    state["ai_memo_status"] = "Available" if state["memo_markdown"] else "Unavailable"
    state["ai_memo_reason"] = state.get("memo_error", "") if not state["memo_markdown"] else ""

    assert state["ai_memo_status"] == "Unavailable"
    assert "RESOURCE_EXHAUSTED" in state["ai_memo_reason"]
    assert state["memo_markdown"] == ""
    client.models.generate_content.assert_called_once()
