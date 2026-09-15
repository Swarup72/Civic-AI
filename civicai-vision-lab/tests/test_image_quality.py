from app.services import image_quality_service
from tests.conftest import (
    make_blurry_jpeg_bytes,
    make_dark_jpeg_bytes,
    make_low_resolution_jpeg_bytes,
    make_textured_jpeg_bytes,
)


def test_good_image_passes():
    data = make_textured_jpeg_bytes(seed=1, width=600, height=500)
    result = image_quality_service.assess_quality(data)
    assert result["passed"] is True
    assert result["corrupted"] is False
    assert result["resolutionOk"] is True
    assert result["blurOk"] is True
    assert result["qualityScore"] > 80


def test_blurry_image_flagged():
    data = make_blurry_jpeg_bytes()
    result = image_quality_service.assess_quality(data)
    assert result["blurOk"] is False
    assert result["passed"] is False
    assert any("blurry" in r for r in result["reasons"])


def test_low_resolution_flagged():
    data = make_low_resolution_jpeg_bytes(width=50, height=40)
    result = image_quality_service.assess_quality(data)
    assert result["resolutionOk"] is False
    assert result["passed"] is False
    assert any("Resolution" in r for r in result["reasons"])


def test_invalid_image_detected_as_corrupted():
    result = image_quality_service.assess_quality(b"this is not a real image, just garbage bytes")
    assert result["corrupted"] is True
    assert result["passed"] is False
    assert result["qualityScore"] == 0
    assert result["resolutionOk"] is False


def test_empty_bytes_detected_as_corrupted():
    result = image_quality_service.assess_quality(b"")
    assert result["corrupted"] is True
    assert result["passed"] is False


def test_dark_image_flagged_for_brightness():
    data = make_dark_jpeg_bytes()
    result = image_quality_service.assess_quality(data)
    assert result["brightnessOk"] is False
    assert any("dark" in r or "over-exposed" in r for r in result["reasons"])


def test_quality_score_is_bounded_0_to_100():
    for data in (
        make_textured_jpeg_bytes(seed=2),
        make_blurry_jpeg_bytes(),
        make_low_resolution_jpeg_bytes(),
        make_dark_jpeg_bytes(),
    ):
        result = image_quality_service.assess_quality(data)
        assert 0 <= result["qualityScore"] <= 100
