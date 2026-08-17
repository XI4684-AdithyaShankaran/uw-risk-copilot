from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.agents.state import UWState
from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME
from app.schemas import decision_from_score
from app.toon import toon_encode
from app.tools.comparables import comparable_lookup
from app.tools.rag_lookup import rag_lookup
from app.tools.risk_calculator import risk_score_calculator
from app.tools.vision_extract import extract_property_features
from google import genai


def intake_node(state: UWState) -> UWState:
    state["raw_input"] = state.get("raw_input", {})
    state["property_id"] = str(state["raw_input"].get("property_id", ""))
    state["image_path"] = state.get("image_path")
    return state


def extract_features_node(state: UWState) -> UWState:
    extracted = extract_property_features(state.get("image_path"), state.get("raw_input", {}))
    state["extracted_features"] = extracted
    return state


def rag_guidelines_node(state: UWState) -> UWState:
    query = (
        f"construction type {state['raw_input'].get('construction_type', '')}, occupancy {state['raw_input'].get('occupancy_type', '')}, "
        f"roof age {state['raw_input'].get('roof_age_years', '')}, cat zone {state['raw_input'].get('cat_zone', '')}, "
        f"claims {state['raw_input'].get('prior_claims_count_5yr', '')}"
    )
    chunks = rag_lookup(query, k=4)
    state["guideline_chunks"] = chunks
    return state


def score_risk_node(state: UWState) -> UWState:
    score_data = risk_score_calculator(state.get("extracted_features", state.get("raw_input", {})))
    state["risk_score"] = int(score_data["score"])
    state["risk_flags"] = score_data["flags"]
    state["risk_breakdown"] = score_data["breakdown"]
    return state


def fetch_comparables_node(state: UWState) -> UWState:
    state["comparables"] = comparable_lookup(state.get("extracted_features", state.get("raw_input", {})), k=5)
    return state


def synthesize_decision_node(state: UWState) -> UWState:
    threshold_decision = decision_from_score(state["risk_score"])
    guidelines_toon = toon_encode([{"chunk": chunk} for chunk in state.get("guideline_chunks", [])])
    comparables_toon = toon_encode(state.get("comparables", [])) if state.get("comparables") else "[]"

    prompt = f"""
You are the underwriting risk decision synthesis layer.
Your job is to justify and narrate the threshold-based decision, not replace it.

Deterministic threshold decision: {threshold_decision}
Property risk score: {state['risk_score']}
Risk flags: {', '.join(state.get('risk_flags', [])) or 'none'}

Relevant underwriting guideline excerpts:
{guidelines_toon}

Comparable properties:
{comparables_toon}

Return valid JSON only with exactly these keys:
- decision
- rationale

Rules:
1. decision must be exactly the deterministic threshold decision.
2. rationale must be 2-3 sentences explaining the observed risk factors and why this score fits the threshold.
3. Keep tone analytical and underwriting-focused.
"""

    # Gracefully fall back if API key is not available
    if GEMINI_API_KEY:
        print("[synthesize_decision_node] BEFORE: Attempting Gemini API call with GEMINI_API_KEY set")
        try:
            print(f"[synthesize_decision_node] Creating genai.Client with API key...")
            client = genai.Client(api_key=GEMINI_API_KEY)
            print(f"[synthesize_decision_node] Calling models.generate_content()")
            response = client.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt)
            text = getattr(response, "text", None) or str(response)
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`\n ")
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].strip()
            parsed = {}
            try:
                import json
                parsed = json.loads(cleaned)
            except Exception:
                parsed = {"decision": threshold_decision, "rationale": "Risk factors and score align with the deterministic underwriting threshold."}

            state["decision"] = parsed.get("decision", threshold_decision)
            state["rationale"] = parsed.get("rationale", "Risk factors and score align with the deterministic underwriting threshold.")
            print(f"[synthesize_decision_node] AFTER: Gemini call succeeded, decision={state['decision']}")
        except (ValueError, Exception) as e:
            # API key invalid or not available, use defaults
            print(f"[synthesize_decision_node] EXCEPTION CAUGHT: {type(e).__name__}: {str(e)}")
            state["decision"] = threshold_decision
            state["rationale"] = "Risk factors and score align with the deterministic underwriting threshold."
            print(f"[synthesize_decision_node] Using fallback decision={state['decision']}")
    else:
        # No API key, use defaults
        print("[synthesize_decision_node] BEFORE: GEMINI_API_KEY is not set, using defaults")
        state["decision"] = threshold_decision
        state["rationale"] = "Risk factors and score align with the deterministic underwriting threshold."
        print(f"[synthesize_decision_node] AFTER: Using fallback decision={state['decision']}")
    return state


def generate_report_node(state: UWState) -> UWState:
    from app.agents.report_agent import generate_memo

    state["memo_markdown"] = generate_memo(state)
    return state


def route_after_score(state: UWState) -> Literal["fetch_comparables", "synthesize_decision"]:
    # Auto-decline fast path: if score is 85+, the system can skip comparables and proceed directly
    # to synthesis because the risk profile is already beyond the underwriting threshold.
    if state["risk_score"] >= 85:
        return "synthesize_decision"
    return "fetch_comparables"


def build_graph() -> StateGraph:
    workflow = StateGraph(UWState)
    workflow.add_node("intake", intake_node)
    workflow.add_node("extract_features", extract_features_node)
    workflow.add_node("rag_guidelines", rag_guidelines_node)
    workflow.add_node("score_risk", score_risk_node)
    workflow.add_node("fetch_comparables", fetch_comparables_node)
    workflow.add_node("synthesize_decision", synthesize_decision_node)
    workflow.add_node("generate_report", generate_report_node)

    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "extract_features")
    workflow.add_edge("extract_features", "rag_guidelines")
    workflow.add_edge("rag_guidelines", "score_risk")
    workflow.add_conditional_edges(
        "score_risk",
        route_after_score,
        {"fetch_comparables": "fetch_comparables", "synthesize_decision": "synthesize_decision"},
    )
    workflow.add_edge("fetch_comparables", "synthesize_decision")
    workflow.add_edge("synthesize_decision", "generate_report")
    workflow.add_edge("generate_report", END)
    return workflow


graph = build_graph().compile()


def run_graph(raw_input: dict, image_path: str | None = None) -> UWState:
    initial: UWState = {
        "property_id": str(raw_input.get("property_id", "")),
        "raw_input": raw_input,
        "image_path": image_path,
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
    result = graph.invoke(initial)
    return result
