from __future__ import annotations

import json
import re
from typing import Any

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME, GEMINI_TIMEOUT_MS


MEMO_FIELDS = {
    "property_summary",
    "key_risk_factors",
    "coverage_review",
    "decision",
    "rationale",
    "suggested_next_steps",
}


def _failure(state: dict, status: str, reason: str) -> dict[str, Any]:
    state["memo_error"] = reason
    state["ai_memo_reason"] = reason
    state["ai_memo_status"] = status
    return {}


def _validate_memo(candidate: Any, state: dict) -> dict[str, Any]:
    if not isinstance(candidate, dict) or set(candidate) != MEMO_FIELDS:
        return _failure(state, "Incomplete", "Invalid structured memo shape")
    if not all(isinstance(candidate[field], list) and candidate[field] for field in MEMO_FIELDS if field != "decision" and field != "rationale"):
        return _failure(state, "Incomplete", "Structured memo contains empty required sections")
    if not isinstance(candidate["decision"], str) or candidate["decision"] != state.get("decision"):
        return _failure(state, "Incomplete", "Structured memo decision differs from deterministic decision")
    if not isinstance(candidate["rationale"], str) or not candidate["rationale"].strip():
        return _failure(state, "Incomplete", "Structured memo rationale is empty")
    flags = set(state.get("risk_flags", []))
    for item in candidate["key_risk_factors"]:
        if not isinstance(item, str) or not any(flag.lower() in item.lower() or flag.replace("_", " ").lower() in item.lower() for flag in flags):
            return _failure(state, "Incomplete", "Structured memo contains an unsupported risk factor")
    raw = state.get("raw_input", {})
    if raw.get("roof_age_years") is None:
        text = json.dumps(candidate).lower()
        if re.search(r"\b(roof|roofing).{0,30}\b\d+\s*(years?|yrs?)\b", text):
            return _failure(state, "Incomplete", "Structured memo contains unsupported roof-age claim")
    # Reject invented monetary values, invented rate percentages, and fabricated regulatory mandates in coverage_review
    _invented = [
        r"[₹$]\s*\d",                                   # specific monetary amounts
        r"\d+\s*%\s*(loading|rate|premium|deductible)",  # invented rate percentages
        r"mandatory under\b",                             # fabricated mandate claims
        r"required by (irdai|law|regulation)\b",         # fabricated compliance claims
    ]
    for item in candidate.get("coverage_review", []):
        if isinstance(item, str) and any(re.search(p, item, re.IGNORECASE) for p in _invented):
            return _failure(state, "Incomplete", "coverage_review contains an unsupported quantitative or regulatory claim")
    # Source-based grounding: a peril mentioned in coverage_review must map to a requested coverage field
    _coverage_map = {
        r"\bearth\s*quake\b": "earthquake_cover",
        r"\bflood\b": "flood_cover",
        r"\bcyclone\b": "cyclone_wind_cover",
        r"\brsmd\b": "rsmd_cover",
        r"\bterror": "terrorism_cover",
        r"\bbusiness\s+interruption\b": "business_interruption_cover",
    }
    for item in candidate.get("coverage_review", []):
        if isinstance(item, str):
            item_lower = item.lower()
            for pattern, field in _coverage_map.items():
                if re.search(pattern, item_lower) and not raw.get(field):
                    return _failure(state, "Incomplete", f"coverage_review references a peril not present in requested coverage ({field})")
    state["ai_memo_status"] = "Available"
    state["memo_error"] = ""
    return candidate


def generate_memo(state: dict) -> dict[str, Any]:
    """Generate and mechanically validate a grounded structured AI memo."""
    if not GEMINI_API_KEY:
        return _failure(state, "Unavailable", "missing API key")

    pid = state.get("raw_input", {}).get("property_id", "unknown")
    print(f"[generate_memo] {pid} starting")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
        ground_truth = {
            "property_facts": state.get("raw_input", {}),
            "vision_evidence": state.get("extracted_features", {}),
            "deterministic_result": {
                "decision": state.get("decision"),
                "risk_score": state.get("risk_score"),
                "risk_flags": state.get("risk_flags", []),
                "risk_breakdown": state.get("risk_breakdown", {}),
            },
            "underwriting_guidance": state.get("guideline_chunks", []),
        }

        prompt = f"""
You are an explanatory AI layer. Return JSON only with exactly these six keys:
property_summary, key_risk_factors, coverage_review, decision, rationale, suggested_next_steps.
property_summary, key_risk_factors, coverage_review, and suggested_next_steps must be arrays of strings.
decision and rationale must be strings.

Use source priority exactly: PROPERTY FACTS, VISION EVIDENCE, DETERMINISTIC RESULT, UNDERWRITING GUIDANCE.
Guidance is contextual evidence and never a property fact. Missing facts remain missing.
The decision must exactly equal the deterministic decision. Do not return a score.
Key risk factors may mention only deterministic risk flags.

REQUESTED COVERAGE IS NOT EXPOSURE.
Requested coverage and extensions describe what the applicant wants insured.
Do not treat requested coverage as evidence that the property is exposed to that peril.
Do not convert a selected coverage into a risk factor, score adjustment, hazard observation, or loss expectation
unless the deterministic underwriting result or supplied evidence explicitly supports that conclusion.
coverage_review must list the requested coverage extensions found in property_facts,
and may identify review considerations such as product applicability, coverage dependencies,
exclusions or deductibles requiring review, or additional underwriting evidence needed.
coverage_review must NOT override the deterministic decision or risk score.
coverage_review must NOT contain invented monetary amounts, invented premium rates, invented regulatory mandates,
or invented mandatory deductible values. Do not invent any specific financial or compliance figures.
If no coverage extensions are requested, coverage_review must contain ["No additional coverage extensions requested."].

Ground truth:
{json.dumps(ground_truth, indent=2, sort_keys=True)}
"""

        response = client.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt)
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            return _failure(state, "Incomplete", "empty response")
        cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
        try:
            candidate = json.loads(cleaned)
        except json.JSONDecodeError:
            return _failure(state, "Incomplete", "invalid JSON response")
        result = _validate_memo(candidate, state)
        if result:
            print(f"[generate_memo] {pid} status=Available")
        return result
    except Exception as e:
        print(f"[generate_memo] {pid} status=failed error={type(e).__name__}: {str(e)[:120]}")
        error_text = f"{type(e).__name__}: {str(e)}"
        response = getattr(e, "response", None)
        if response is not None:
            error_text = f"{error_text} {getattr(response, 'text', '')} {getattr(response, '_content', b'')}"
        if getattr(e, "code", None) == 429 or getattr(e, "status_code", None) == 429 or "429" in error_text:
            error_text = f"RESOURCE_EXHAUSTED: {error_text}"
        return _failure(state, "Unavailable", error_text)
