from __future__ import annotations

from typing import NotRequired, TypedDict


class MemoState(TypedDict):
    property_summary: list[str]
    key_risk_factors: list[str]
    coverage_review: list[str]
    decision: str
    rationale: str
    suggested_next_steps: list[str]


class UWState(TypedDict):
    property_id: str
    raw_input: dict
    image_path: str | None
    extracted_features: dict
    guideline_chunks: list[str]
    risk_score: int
    risk_flags: list[str]
    risk_breakdown: dict
    prototype_mitigation_model: dict
    comparables: list[dict]
    decision: str
    rationale: str  # propagated from memo_json["rationale"] after report generation
    memo_json: dict  # MemoState shape when AI succeeds, {} when unavailable
    ai_memo_status: NotRequired[str]
    ai_memo_reason: NotRequired[str]
    memo_error: NotRequired[str]
