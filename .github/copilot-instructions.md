# uw-risk-copilot — GitHub Copilot Instructions

## Project

AI-assisted commercial-property underwriting capstone.

Runtime architecture:

React frontend
→ FastAPI
→ LangGraph orchestration
→ deterministic Python underwriting rules
→ Chroma/RAG + Gemini Vision + Gemini structured memo
→ SQLite persistence
→ dashboard / result / PDF

Python is the underwriting authority.
Gemini is an explanatory/evidence-extraction layer.
The React TypeScript risk engine is not a runtime authority.

## Active stack

- Python 3.13
- FastAPI
- LangGraph
- ChromaDB
- google-genai
- SQLite
- pytest
- React
- TypeScript
- Vite

The old Streamlit application and old TypeScript underwriting engine are not runtime components.

## Repository map

Backend:
- app/api/ — FastAPI endpoints
- app/agents/ — LangGraph orchestration and AI memo generation
- app/tools/ — deterministic risk, Vision, RAG, reference-property retrieval
- app/schemas.py — API/domain contracts
- app/db.py — persistence/reference data
- app/reports.py — PDF generation
- tests/ — automated validation
- scripts/ — development/setup utilities
- data/ — reference/demo assets

Frontend:
- src/api/ — backend API client
- src/components/ — dashboard, assessment, result UI
- src/context/ — application state
- src/types/ — backend-aligned types

Inspect existing consumers and tests before changing a contract.

## Core architecture rules

### Underwriting authority

Authoritative values are produced by deterministic Python:

- risk_score
- decision
- risk_flags
- risk_breakdown

Only Python determines the authoritative decision.

Gemini must never:
- invent a score
- change the decision
- override deterministic risk flags
- create underwriting thresholds
- create insurer-calibrated weights

### Indicative model

prototype_mitigation_model is an indicative analytical visualization.

It is not the authoritative underwriting score.

Keep these concepts separate:
- authoritative risk score
- indicative risk-adjusted view
- configured mitigation benefit

Do not present indicative values as insurer-approved or production-calibrated scores.

### AI memo

The structured AI memo contract is:

- property_summary
- key_risk_factors
- coverage_review
- decision
- rationale
- suggested_next_steps

The AI decision must exactly equal the deterministic decision.

AI output must be mechanically validated before persistence or display.

Do not produce fallback AI prose.

If Gemini fails:
- keep the deterministic decision
- mark AI output unavailable/incomplete
- do not fabricate or reuse stale AI text

Never mark AI output Available unless a valid memo passed validation.

## Prompt/context rules

Use explicit separation of:

- instruction
- property input/context
- retrieved evidence
- output contract

Keep prompts concise and task-specific.

For grounded generation, establish a source hierarchy.

Priority:

1. submitted property facts
2. deterministic underwriting result
3. directly supported Vision evidence
4. retrieved underwriting guidance
5. synthetic reference-property evidence

Lower-priority context must not overwrite higher-priority facts.

## Property-data integrity

Never silently convert missing data into a real property fact.

Examples:

- missing roof age ≠ 0 years
- missing year built ≠ 2000
- missing occupancy ≠ Office
- missing distance ≠ 0 miles
- missing value ≠ ₹0

Use explicit unknown/missing handling.

Do not let Vision overwrite submitted manual facts.

Vision observations must remain in a separate evidence namespace from submitted property facts where possible.

## Vision rules

Vision may report only directly visible evidence.

Vision must not infer:
- roof age
- claims
- TIV
- occupancy
- CAT zone
- seismic zone
- policy coverage
- historical maintenance
- construction characteristics not visibly supported

Use explicit uncertainty such as "not visible" or "unclear".

A Vision failure must never become fabricated property evidence.

## Coverage semantics

Requested coverage is not property exposure.

Examples:

- earthquake_cover = true does not prove earthquake exposure
- flood_cover = true does not prove flood exposure
- terrorism_cover = true does not prove terrorism exposure

Coverage selection may be discussed in coverage_review.

Coverage selection must not automatically change authoritative risk score unless an explicit deterministic rule exists.

## RAG rules

RAG provides underwriting context.

RAG evidence must never override:
- submitted property facts
- deterministic rules
- Vision evidence

RAG unavailable is not equivalent to "no relevant evidence".

Do not silently swallow retrieval failures.

Clearly distinguish:
- retrieval available with evidence
- retrieval available with no relevant evidence
- retrieval unavailable

## Reference properties

Records in the reference-property dataset are synthetic reference records.

Do not call them:
- real market comparables
- insurer historical comparables
- verified market data

unless independently verified.

Reference properties are evidence for retrieval/ranking only.

They must never overwrite facts about the submitted property.

Similarity weights are prototype ranking weights unless backed by explicit empirical evidence.

Do not describe prototype weights as insurer-calibrated.

## Data provenance

Keep these categories distinct:

- submitted/demo property data
- synthetic reference-property data
- external underwriting guidance
- Vision observations
- Gemini-generated analysis

Do not merge them into one undifferentiated "truth" source.

## Database rules

- Reads must not unexpectedly mutate application/reference data.
- Missing database values should remain NULL/unknown, not fabricated zeros.
- Avoid duplicate sources of truth.
- Preserve structured memo JSON as the current AI memo contract.
- Do not reintroduce legacy memo markdown unless an active consumer requires it.
- Do not delete demo/history records without explicit instruction.

## API/schema rules

- Preserve backend/frontend field-name compatibility.
- Do not create duplicate authoritative fields.
- Derived values must remain derived.
- Product segment should be derived where the existing architecture derives it; do not create a second user-controlled source.
- Reject unexpected request fields when doing so is compatible with the API contract.

## Coding rules

- Prefer small, localized changes.
- Inspect existing implementation before editing.
- Do not redesign working architecture without evidence.
- Do not add speculative abstractions.
- Reuse existing utilities and contracts.
- Keep configuration centralized in app/config.py.
- Never hardcode secrets or model credentials.
- Do not silently swallow errors that affect underwriting, AI, Vision, RAG, or persistence.
- Use parameterized SQL.
- Validate external/model output before persistence.
- Add/update tests for behavior changes.

## Validation

Use the narrowest relevant validation first, then expand for cross-layer changes.

Backend:
python -m pytest tests/ -v

Frontend:
npm run typecheck
npm run build

For API/UI/model changes, validate the actual runtime path.

Do not claim browser/runtime success from static inspection alone.

Do not claim tests/builds passed if the process was killed, interrupted, or not actually observed to exit 0.

## Change boundaries

Do not change without explicit requirement:
- underwriting thresholds
- mitigation weights
- RAG architecture
- Vision architecture
- Gemini model selection
- database cleanup policy
- frontend information architecture
- coverage semantics

When changing a model rule, identify:
1. existing behavior
2. evidence supporting the change
3. expected before/after behavior
4. regression tests

## External evidence

When a task requires real-world underwriting, insurance, regulatory, or product claims:
- verify current external sources
- distinguish source-backed facts from prototype assumptions
- do not convert qualitative evidence into arbitrary numerical weights
- do not claim loss-ratio, pricing, inspection-cost, or production performance improvements without outcome data

## Final-response discipline

When reporting work:
- state exactly what changed
- state what was verified
- separate verified facts from assumptions
- include failed or unavailable validation
- list remaining limitations
- do not claim production readiness
- do not claim insurer calibration or approval without evidence

Never fabricate validation evidence.