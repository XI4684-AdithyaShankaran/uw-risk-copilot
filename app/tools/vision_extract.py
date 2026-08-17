from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from PIL import Image, UnidentifiedImageError

from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME


def extract_property_features(image_path: str | None, manual_fields: dict) -> dict:
    """Extract risk-relevant property features from an image and merge with manual fields."""
    if image_path is None:
        return dict(manual_fields)

    path = Path(image_path)
    if not path.exists():
        return dict(manual_fields)

    try:
        with Image.open(path) as image:
            width, height = image.size
            if width <= 0 or height <= 0:
                reason = "invalid image dimensions"
            else:
                pixels = image.convert("RGB").resize((64, 64)).getdata()
                channels = list(zip(*pixels))
                channel_ranges = [max(channel) - min(channel) for channel in channels]
                reason = "near-uniform pixel content" if max(channel_ranges) <= 3 else ""
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        reason = f"image could not be decoded: {type(exc).__name__}"

    if reason:
        print("IMAGE_VALIDATION_STATUS=unusable")
        print(f"IMAGE_VALIDATION_REASON={reason}")
        print("VISION_CALLED=false")
        return {
            **manual_fields,
            "image_status": "unusable",
            "image_reason": reason,
            "image_risk_evidence_used": False,
        }

    print("IMAGE_VALIDATION_STATUS=valid")
    print("IMAGE_VALIDATION_REASON=decoded and non-uniform")

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
        "image_status, image_reason, image_risk_evidence_used, "
        "visible_roof_condition, visible_structural_damage, vegetation_defensible_space, "
        "general_maintenance_level, visible_hazards. "
        "Classify image_status as usable only if relevant property condition is meaningfully visible. "
        "Set image_risk_evidence_used true only when observations are supported by the image. "
        "Use 'not visible' for indeterminate observations; do not infer from form fields. "
        "Use values as short strings or arrays only; no markdown."
    )

    try:
        print("VISION_CALLED=true")
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
        merged.setdefault("image_status", "unusable")
        merged.setdefault("image_reason", "vision could not establish relevant property condition")
        merged.setdefault("image_risk_evidence_used", False)
        print(f"EXTRACTED_FEATURE_KEYS={sorted(merged.keys())}")
        print(f"[extract_property_features] SUCCESS: merged {len(extracted)} vision fields")
        return merged
    except Exception as e:
        print(f"[extract_property_features] VISION ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return dict(manual_fields)
