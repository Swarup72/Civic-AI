"""
End-to-end pipeline tests — analysis_service.analyze_before_after() calling
all four other services together, exactly as the API route does."""
from app.services import analysis_service
from tests.conftest import make_flat_jpeg_bytes, make_low_resolution_jpeg_bytes, make_textured_jpeg_bytes


def test_successful_pipeline_end_to_end(write_image):
    before_path = write_image(make_textured_jpeg_bytes(seed=10, shift=0), "before.jpg")
    after_path = write_image(make_textured_jpeg_bytes(seed=10, shift=0), "after.jpg")

    result = analysis_service.analyze_before_after(before_path, after_path)

    # Every top-level key the API contract promises must be present.
    for key in ("beforeQuality", "afterQuality", "scene", "beforeVision", "afterVision", "evidence"):
        assert key in result

    assert result["beforeQuality"]["passed"] is True
    assert result["afterQuality"]["passed"] is True
    assert result["scene"]["sameScene"] is True  # identical synthetic scene

    # Vision model ships unavailable in this prototype by design - the
    # pipeline must still complete and report that honestly, not crash.
    assert result["beforeVision"]["status"] == "unavailable"
    assert result["afterVision"]["status"] == "unavailable"

    evidence = result["evidence"]
    assert evidence["breakdown"]["sameLocation"] == 40
    assert evidence["assessment"] in ("likely_fixed", "inconclusive", "likely_not_fixed")
    assert isinstance(evidence["explanation"], list) and evidence["explanation"]


def test_pipeline_with_wrong_scene(write_image):
    before_path = write_image(make_textured_jpeg_bytes(seed=1), "before.jpg")
    after_path = write_image(make_textured_jpeg_bytes(seed=999), "after.jpg")

    result = analysis_service.analyze_before_after(before_path, after_path)

    assert result["scene"]["sameScene"] is False
    assert result["evidence"]["breakdown"]["sameLocation"] == 0
    assert result["evidence"]["assessment"] == "likely_not_fixed"


def test_failed_pipeline_with_invalid_after_image(write_image):
    """A corrupted/invalid 'after' image must not crash the pipeline - every
    stage degrades honestly instead."""
    before_path = write_image(make_textured_jpeg_bytes(seed=1), "before.jpg")
    after_path = write_image(b"not a real image at all", "after.jpg")

    result = analysis_service.analyze_before_after(before_path, after_path)

    assert result["afterQuality"]["corrupted"] is True
    assert result["scene"]["sameScene"] is None  # can't compare against an undecodable image
    assert result["afterVision"]["status"] in ("unavailable", "invalid_image")
    assert result["evidence"]["evidenceScore"] < 50
    assert result["evidence"]["assessment"] == "likely_not_fixed"


def test_failed_pipeline_with_missing_files():
    """Nonexistent paths (e.g. an upload that never actually landed on disk)
    must not raise - every service treats unreadable bytes as invalid input,
    not a crash."""
    result = analysis_service.analyze_before_after("/tmp/does_not_exist_before.jpg", "/tmp/does_not_exist_after.jpg")
    assert result["beforeQuality"]["corrupted"] is True
    assert result["afterQuality"]["corrupted"] is True
    assert result["evidence"]["evidenceScore"] == 0
    assert result["evidence"]["assessment"] == "likely_not_fixed"


def test_pipeline_with_low_resolution_images(write_image):
    before_path = write_image(make_low_resolution_jpeg_bytes(), "before.jpg")
    after_path = write_image(make_low_resolution_jpeg_bytes(), "after.jpg")

    result = analysis_service.analyze_before_after(before_path, after_path)

    assert result["beforeQuality"]["resolutionOk"] is False
    assert result["afterQuality"]["resolutionOk"] is False
    # Quality still contributes SOME points proportionally, never negative.
    assert result["evidence"]["breakdown"]["imageQuality"] >= 0


def test_pipeline_with_ambiguous_scene(write_image):
    before_path = write_image(make_flat_jpeg_bytes(), "before.jpg")
    after_path = write_image(make_flat_jpeg_bytes(), "after.jpg")

    result = analysis_service.analyze_before_after(before_path, after_path)

    assert result["scene"]["sameScene"] is None
    assert result["evidence"]["breakdown"]["sameLocation"] == 0


def test_pipeline_response_is_json_serializable(write_image):
    """Guards against a stray numpy scalar or non-JSON-safe type slipping
    into the response (a real bug class with OpenCV/numpy-heavy code)."""
    import json

    before_path = write_image(make_textured_jpeg_bytes(seed=7), "before.jpg")
    after_path = write_image(make_textured_jpeg_bytes(seed=7), "after.jpg")

    result = analysis_service.analyze_before_after(before_path, after_path)
    json.dumps(result)  # raises TypeError if anything isn't JSON-serializable
