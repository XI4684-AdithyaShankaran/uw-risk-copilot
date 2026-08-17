from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME


def extract_property_features(image_path: str | None, manual_fields: dict) -> dict:
    """Extract risk-relevant property features from an image and merge with manual fields."""
    if image_path is None:
        return dict(manual_fields)

    path = Path(image_path)
    if not path.exists():
        return dict(manual_fields)

    # Gracefully fall back if API key is not available
    if not GEMINI_API_KEY:
        return dict(manual_fields)

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except (ValueError, Exception) as e:
        # Print the actual error instead of silent fallback
        print(f"[extract_property_features] CLIENT INIT ERROR: {type(e).__name__}: {str(e)}")
        return dict(manual_fields)

    prompt = (
        "Review this commercial property image and return a compact JSON object with these keys: "
        "visible_roof_condition, visible_structural_damage, vegetation_defensible_space, "
        "general_maintenance_level, visible_hazards. "
        "Use values as short strings or arrays only; no markdown."
    )

    try:
        print(f"[extract_property_features] Calling vision API for {path}")
        mime_type = mimetypes.guess_type(path)[0] or "image/jpeg"
        with open(path, "rb") as f:
            image_bytes = f.read()
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=[prompt, image_part],
        )
        text = getattr(response, "text", None) or str(response)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`\n ")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        extracted = json.loads(cleaned)
        merged = dict(manual_fields)
        merged.update({k: v for k, v in extracted.items() if v is not None})
        print(f"[extract_property_features] SUCCESS: merged {len(extracted)} vision fields")
        return merged
    except Exception as e:
        print(f"[extract_property_features] VISION ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return dict(manual_fields)
