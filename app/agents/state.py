from __future__ import annotations

from typing import TypedDict


class UWState(TypedDict):
    property_id: str
    raw_input: dict
    image_path: str | None
    extracted_features: dict
    guideline_chunks: list[str]
    risk_score: int
    risk_flags: list[str]
    risk_breakdown: dict
    comparables: list[dict]
    decision: str
    rationale: str
    memo_markdown: str
