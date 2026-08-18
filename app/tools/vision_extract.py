from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from PIL import Image, UnidentifiedImageError

from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME, GEMINI_TIMEOUT_MS

# Keys Vision is permitted to contribute; manual submission fields cannot be overwritten
_VISION_KEYS = frozenset({
    "image_status", "image_reason", "image_risk_evidence_used",
    "visible_roof_condition", "visible_structural_damage",
    "vegetation_defensible_space", "general_maintenance_level", "visible_hazards",
})
# Observation keys used to derive evidence usability in Python (not trusted from Gemini)
_OBSERVATION_KEYS = (
    "visible_roof_condition", "visible_structural_damage",
    "vegetation_defensible_space", "general_maintenance_level", "visible_hazards",
)
_NOT_VISIBLE = {"not visible", "unclear", "none", "n/a", ""}


def _evidence_usable(extracted: dict) -> bool:
    """Python derives evidence usability — not trusted from the model response."""
    for key in _OBSERVATION_KEYS:
        value = extracted.get(key)
        if value and str(value).lower().strip() not in _NOT_VISIBLE:
            return True
    return False


def extract_property_features(image_path: str | None, manual_fields: dict) -> dict:
    """Extract risk-relevant property features from an image and merge with manual fields."""
    prop_id = manual_fields.get("property_id", "unknown")

    if image_path is None:
        return {**manual_fields, "image_status": "Unavailable", "image_reason": "No image submitted", "image_risk_evidence_used": False}

    path = Path(image_path)
    if not path.exists():
        return {**manual_fields, "image_status": "Unavailable", "image_reason": "Submitted image was not found", "image_risk_evidence_used": False}

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
        print(f"[vision_extract] {prop_id} image_status=unusable reason={reason}")
        return {
            **manual_fields,
            "image_status": "unusable",
            "image_reason": reason,
            "image_risk_evidence_used": False,
        }

    if not GEMINI_API_KEY:
        return {**manual_fields, "image_status": "Unavailable", "image_reason": "GEMINI_API_KEY is not set", "image_risk_evidence_used": False}

    try:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
    except Exception as e:
        print(f"[vision_extract] {prop_id} client_init_failed error={type(e).__name__}")
        return {**manual_fields, "image_status": "Unavailable", "image_reason": f"Vision client initialization failed: {type(e).__name__}", "image_risk_evidence_used": False}

    prompt = (
        "You are a commercial-property inspection evidence extractor.\n\n"
        "TASK:\n"
        "Extract only directly visible property-condition evidence from the supplied image.\n\n"
        "SOURCE:\n"
        "The image is the only source. Manual underwriting fields are not visual evidence and are not supplied.\n\n"
        "OUTPUT:\n"
        "Return JSON with exactly these keys: "
        "image_status, image_reason, image_risk_evidence_used, "
        "visible_roof_condition, visible_structural_damage, vegetation_defensible_space, "
        "general_maintenance_level, visible_hazards. "
        "Values must be short strings or arrays only. No markdown.\n\n"
        "GROUNDING:\n"
        "Only state what is directly visible. Do not infer: construction type, occupancy, year built, "
        "TIV, claims, CAT zone, seismic zone, sprinkler status, fire alarm status, roof age, "
        "maintenance history, or policy information unless unambiguously visible in the image.\n\n"
        "UNCERTAINTY:\n"
        "Use 'not visible' when the image does not support a conclusion. "
        "Use 'unclear' when visible but cannot be reliably assessed.\n\n"
        "EVIDENCE:\n"
        "Set image_status to 'usable' only when at least one meaningful property-condition "
        "observation is directly supported by the image."
    )

    try:
        mime_type = mimetypes.guess_type(path)[0] or "image/jpeg"
        with open(path, "rb") as f:
            image_bytes = f.read()
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=[prompt, image_part],
        )
        text = getattr(response, "text", None) or str(response)
        cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`\n ")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        extracted = json.loads(cleaned)

        # Strip unexpected keys — Vision must not inject fields outside its contract
        unexpected = set(extracted.keys()) - _VISION_KEYS
        if unexpected:
            print(f"[vision_extract] {prop_id} stripping unexpected keys={sorted(unexpected)}")
        vision_data = {k: v for k, v in extracted.items() if k in _VISION_KEYS and v is not None}

        # Python derives evidence usability — do not trust model's self-assessment
        evidence_used = _evidence_usable(vision_data)
        vision_data["image_risk_evidence_used"] = evidence_used

        # Downgrade usable claim if no observations support it
        if vision_data.get("image_status") == "usable" and not evidence_used:
            vision_data["image_status"] = "unusable"
            vision_data["image_reason"] = "no substantive observations found despite usable claim"

        # Manual fields are authoritative; Vision observations only fill designated keys
        merged = dict(manual_fields)
        merged.update(vision_data)
        merged.setdefault("image_status", "unusable")
        merged.setdefault("image_reason", "vision could not establish relevant property condition")
        merged.setdefault("image_risk_evidence_used", False)

        print(f"[vision_extract] {prop_id} status={merged['image_status']} evidence_used={evidence_used}")
        return merged
    except json.JSONDecodeError:
        print(f"[vision_extract] {prop_id} status=failed error=invalid_json_response")
        return {**manual_fields, "image_status": "Unavailable", "image_reason": "Vision returned invalid JSON", "image_risk_evidence_used": False}
    except Exception as e:
        print(f"[vision_extract] {prop_id} status=failed error={type(e).__name__}: {str(e)[:80]}")
        return {**manual_fields, "image_status": "Unavailable", "image_reason": f"Vision request failed: {type(e).__name__}", "image_risk_evidence_used": False}
