from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

import app.tools.vision_extract as vision_module
from app.tools.vision_extract import extract_property_features


MANUAL = {"property_id": "TEST-001", "construction_type": "Non-Combustible", "sprinkler_system": "Y", "roof_age_years": None}

VALID_VISION_RESPONSE = json.dumps({
    "image_status": "usable",
    "image_reason": "roof and facade visible",
    "image_risk_evidence_used": True,
    "visible_roof_condition": "flat roof, intact",
    "visible_structural_damage": "none observed",
    "vegetation_defensible_space": "not visible",
    "general_maintenance_level": "good",
    "visible_hazards": "none",
})


# ── no image ──────────────────────────────────────────────────────────────────

def test_no_image_returns_unavailable():
    result = extract_property_features(None, MANUAL)
    assert result["image_status"] == "Unavailable"
    assert result["image_risk_evidence_used"] is False
    assert result["construction_type"] == "Non-Combustible"  # manual fields preserved


# ── missing file ──────────────────────────────────────────────────────────────

def test_missing_file_returns_unavailable(tmp_path):
    result = extract_property_features(str(tmp_path / "nonexistent.jpg"), MANUAL)
    assert result["image_status"] == "Unavailable"
    assert "not found" in result["image_reason"]


# ── corrupt image ─────────────────────────────────────────────────────────────

def test_corrupt_image_returns_unusable(tmp_path):
    corrupt = tmp_path / "bad.jpg"
    corrupt.write_bytes(b"not_an_image")
    result = extract_property_features(str(corrupt), MANUAL)
    assert result["image_status"] == "unusable"
    assert result["image_risk_evidence_used"] is False


# ── blank/uniform image ───────────────────────────────────────────────────────

def test_uniform_image_returns_unusable(tmp_path):
    from PIL import Image as PILImage
    img_path = tmp_path / "blank.jpg"
    img = PILImage.new("RGB", (64, 64), color=(200, 200, 200))
    img.save(img_path)
    result = extract_property_features(str(img_path), MANUAL)
    assert result["image_status"] == "unusable"
    assert result["image_risk_evidence_used"] is False


# ── missing API key ───────────────────────────────────────────────────────────

def test_missing_api_key_returns_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(vision_module, "GEMINI_API_KEY", "")
    img_path = _make_real_image(tmp_path)  # non-uniform so local validation passes
    result = extract_property_features(img_path, MANUAL)
    assert result["image_status"] == "Unavailable"
    assert "API_KEY" in result["image_reason"]


def _make_real_image(tmp_path):
    """Return path to a valid non-uniform image that passes local validation."""
    from PIL import Image as PILImage
    img_path = tmp_path / "property.jpg"
    img = PILImage.new("RGB", (200, 200))
    pixels = [(i % 255, (i * 2) % 255, (i * 3) % 255) for i in range(200 * 200)]
    img.putdata(pixels)
    img.save(img_path)
    return str(img_path)


def _patched_client(response_text: str, monkeypatch, tmp_path):
    """Patch the Gemini client to return a controlled response."""
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    monkeypatch.setattr(vision_module, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(vision_module.genai, "Client", lambda api_key, **kwargs: mock_client)
    return _make_real_image(tmp_path)


# ── Gemini invalid JSON ───────────────────────────────────────────────────────

def test_invalid_json_response_returns_unavailable(tmp_path, monkeypatch):
    img_path = _patched_client("not json at all", monkeypatch, tmp_path)
    result = extract_property_features(img_path, MANUAL)
    assert result["image_status"] == "Unavailable"
    assert result["image_risk_evidence_used"] is False


# ── Gemini unexpected keys stripped ──────────────────────────────────────────

def test_unexpected_keys_are_stripped(tmp_path, monkeypatch):
    response = json.dumps({
        **json.loads(VALID_VISION_RESPONSE),
        "construction_type": "Frame",   # must NOT overwrite manual field
        "roof_age_years": 35,           # must NOT overwrite manual field (None)
        "random_hallucination": "x",    # must be stripped
    })
    img_path = _patched_client(response, monkeypatch, tmp_path)
    result = extract_property_features(img_path, MANUAL)
    # Manual fields are authoritative
    assert result["construction_type"] == "Non-Combustible"
    assert result["roof_age_years"] is None
    # Unexpected Vision fields must not appear
    assert "random_hallucination" not in result


# ── Gemini image_status=usable with no real evidence ─────────────────────────

def test_usable_claim_downgraded_when_no_evidence(tmp_path, monkeypatch):
    response = json.dumps({
        "image_status": "usable",
        "image_reason": "image looks fine",
        "image_risk_evidence_used": True,   # Gemini claims True
        "visible_roof_condition": "not visible",
        "visible_structural_damage": "not visible",
        "vegetation_defensible_space": "not visible",
        "general_maintenance_level": "not visible",
        "visible_hazards": "not visible",
    })
    img_path = _patched_client(response, monkeypatch, tmp_path)
    result = extract_property_features(img_path, MANUAL)
    # Python overrides — no observations → not usable
    assert result["image_status"] == "unusable"
    assert result["image_risk_evidence_used"] is False


# ── Python derives evidence usability ────────────────────────────────────────

def test_evidence_used_derived_from_observations(tmp_path, monkeypatch):
    img_path = _patched_client(VALID_VISION_RESPONSE, monkeypatch, tmp_path)
    result = extract_property_features(img_path, MANUAL)
    assert result["image_status"] == "usable"
    assert result["image_risk_evidence_used"] is True  # Python derived from observations


# ── Vision must not overwrite submitted manual fields ────────────────────────

def test_vision_cannot_overwrite_sprinkler_field(tmp_path, monkeypatch):
    """Submitted sprinkler_system=Y must not be overwritten by Vision output."""
    response = json.dumps({
        "image_status": "usable",
        "image_reason": "property visible",
        "image_risk_evidence_used": True,
        "visible_roof_condition": "metal deck visible",
        "visible_structural_damage": "none",
        "vegetation_defensible_space": "not visible",
        "general_maintenance_level": "good",
        "visible_hazards": "none",
        "sprinkler_system": "N",  # Vision must not inject this
    })
    img_path = _patched_client(response, monkeypatch, tmp_path)
    manual_with_sprinkler = {**MANUAL, "sprinkler_system": "Y"}
    result = extract_property_features(img_path, manual_with_sprinkler)
    assert result["sprinkler_system"] == "Y"  # manual field preserved
