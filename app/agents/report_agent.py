from __future__ import annotations

import json

from google import genai

from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME
from app.toon import toon_encode


def generate_memo(state: dict) -> str:
    """Generate a polished markdown memo using a senior underwriting persona."""
    # Gracefully fall back if API key is not available
    if not GEMINI_API_KEY:
        return f"""
## Property Summary
- Property ID: {state.get('property_id')}
- Address: {state.get('raw_input', {}).get('address', '')}
- City: {state.get('raw_input', {}).get('city', '')}

## Key Risk Factors
{', '.join(state.get('risk_flags', [])) or 'No specific risk flags identified.'}

## Decision
**{state.get('decision', 'PENDING')}**

Risk Score: {state.get('risk_score', 0)}/100

## Suggested Next Steps
Continue with standard underwriting review process.
"""
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        guidelines = toon_encode([{"chunk": chunk} for chunk in state.get("guideline_chunks", [])])
        comparables = toon_encode(state.get("comparables", [])) if state.get("comparables") else "[]"
        property_features = json.dumps(
            state.get("extracted_features") or state.get("raw_input", {}),
            indent=2,
            sort_keys=True,
        )

        prompt = f"""
You are a senior commercial underwriting analyst. Draft a concise but polished underwriting memo in markdown.

Supplied property and extracted features (the sole source of property facts):
{property_features}

Property summary:
- Property ID: {state.get('property_id')}
- Address: {state.get('raw_input', {}).get('address', '')}
- City: {state.get('raw_input', {}).get('city', '')}
- Occupancy: {state.get('raw_input', {}).get('occupancy_type', '')}
- Construction: {state.get('raw_input', {}).get('construction_type', '')}
- CAT Zone: {state.get('raw_input', {}).get('cat_zone', '')}
- Roof age: {state.get('raw_input', {}).get('roof_age_years', '')}
- Prior claims: {state.get('raw_input', {}).get('prior_claims_count_5yr', '')}

Decision: {state.get('decision', '')}
Risk score: {state.get('risk_score', 0)}
Risk flags: {', '.join(state.get('risk_flags', [])) or 'none'}
Rationale: {state.get('rationale', '')}

Underwriting guideline excerpts:
{guidelines}

Comparable data:
{comparables}

Write markdown with sections: '## Property Summary', '## Key Risk Factors', '## Decision', '## Suggested Next Steps'. Keep it practical and underwriting-focused. Refer to supplied underwriting guidance naturally (for example, "per the roof age guideline") rather than using mechanical section-number citations.

Strict grounding rules:
1. Use only facts explicitly present in the supplied property and extracted features. Never invent, infer, assume, or embellish property characteristics.
2. When a field is supplied, use its exact value. If sprinkler_system is Y, never describe sprinkler or fire suppression as missing, unknown, absent, or unverified.
3. State that a threshold is exceeded only when the supplied value is greater than that threshold. Describe a value equal to a threshold as "at threshold", not "above" or "exceeding" it.
4. Include a property risk factor only when it is present in the deterministic Risk flags above. Do not create additional risk factors from general guidance.
5. The Decision, Risk Score, and Key Risk Factors must exactly match the deterministic Decision, Risk score, and Risk flags above.
6. RAG guideline excerpts provide underwriting context only. They must not override supplied property data or deterministic rules, and general guideline language must not become a property-specific fact.
7. Suggested next steps must address actual deterministic risk flags only and must not assume unverified deficiencies.
"""

        print(f"[generate_memo] PROMPT:\n{prompt}")
        response = client.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt)
        text = getattr(response, "text", None) or str(response)
        return text.strip()
    except (ValueError, Exception) as e:
        # Print the actual error instead of silent fallback
        print(f"[generate_memo] EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        # Fall back to template if API call fails
        return f"""
## Property Summary
- Property ID: {state.get('property_id')}
- Address: {state.get('raw_input', {}).get('address', '')}
- City: {state.get('raw_input', {}).get('city', '')}

## Key Risk Factors
{', '.join(state.get('risk_flags', [])) or 'No specific risk flags identified.'}

## Decision
**{state.get('decision', 'PENDING')}**

Risk Score: {state.get('risk_score', 0)}/100

## Suggested Next Steps
Continue with standard underwriting review process.
"""
