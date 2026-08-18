from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from app.agents.state import UWState
from app.schemas import decision_from_score
from app.tools.comparables import comparable_lookup
from app.tools.rag_lookup import rag_lookup
from app.tools.risk_calculator import risk_score_calculator
from app.tools.vision_extract import extract_property_features


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
    state["prototype_mitigation_model"] = score_data["prototype_mitigation_model"]
    return state


def fetch_comparables_node(state: UWState) -> UWState:
    state["comparables"] = comparable_lookup(state.get("extracted_features", state.get("raw_input", {})), k=5)
    return state


def synthesize_decision_node(state: UWState) -> UWState:
    # Deterministic authority: Python rules set the decision; AI only explains.
    state["decision"] = decision_from_score(state["risk_score"])
    return state


def generate_report_node(state: UWState) -> UWState:
    from app.agents.report_agent import generate_memo
    memo = generate_memo(state)
    state["memo_json"] = memo
    # Surface rationale for downstream consumers (empty string when AI unavailable)
    state["rationale"] = memo.get("rationale", "") if memo else ""
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
        "prototype_mitigation_model": {},
        "comparables": [],
        "decision": "Accept",
        "rationale": "",
        "memo_json": {},
    }
    result = graph.invoke(initial)
    return result
