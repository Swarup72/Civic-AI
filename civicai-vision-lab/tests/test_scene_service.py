from app.services import scene_service
from tests.conftest import make_flat_jpeg_bytes, make_textured_jpeg_bytes


def test_same_scene_detected():
    """Same seed, zero shift = the exact same underlying image (a second
    photo of the identical scene, framed identically)."""
    before = make_textured_jpeg_bytes(seed=42, shift=0)
    after = make_textured_jpeg_bytes(seed=42, shift=0)
    result = scene_service.compare_scenes(before, after)
    assert result["sameScene"] is True
    assert result["matchScore"] > 0.3
    assert isinstance(result["explanation"], list) and result["explanation"]


def test_same_scene_detected_with_slight_reframing():
    """Same seed, small shift = a slightly different framing of the same
    physical scene (simulating an authority standing a bit differently)."""
    before = make_textured_jpeg_bytes(seed=42, shift=0)
    after = make_textured_jpeg_bytes(seed=42, shift=5)
    result = scene_service.compare_scenes(before, after)
    assert result["sameScene"] is True


def test_wrong_scene_detected():
    """Different seeds = genuinely different random textures - no real
    geometric correspondence should be found."""
    before = make_textured_jpeg_bytes(seed=1)
    after = make_textured_jpeg_bytes(seed=999)
    result = scene_service.compare_scenes(before, after)
    assert result["sameScene"] is False
    assert result["matchScore"] < 0.3


def test_ambiguous_scene_returns_none_for_low_texture_images():
    """Flat, textureless images produce ~zero ORB keypoints - the comparison
    is genuinely inconclusive, and must be reported as None, never coerced
    into a False (which would misrepresent 'unknown' as 'confirmed different')."""
    before = make_flat_jpeg_bytes(color=(120, 140, 160))
    after = make_flat_jpeg_bytes(color=(120, 140, 160))
    result = scene_service.compare_scenes(before, after)
    assert result["sameScene"] is None
    assert result["matchScore"] == 0.0


def test_invalid_image_bytes_returns_none_scene():
    result = scene_service.compare_scenes(b"not an image", b"also not an image")
    assert result["sameScene"] is None
    assert any("could not be decoded" in r for r in result["explanation"])


def test_one_valid_one_invalid_image_returns_none_scene():
    valid = make_textured_jpeg_bytes(seed=1)
    result = scene_service.compare_scenes(valid, b"garbage")
    assert result["sameScene"] is None


def test_match_score_is_always_between_0_and_1():
    cases = [
        (make_textured_jpeg_bytes(seed=1), make_textured_jpeg_bytes(seed=1)),
        (make_textured_jpeg_bytes(seed=1), make_textured_jpeg_bytes(seed=2)),
        (make_flat_jpeg_bytes(), make_flat_jpeg_bytes()),
    ]
    for before, after in cases:
        result = scene_service.compare_scenes(before, after)
        assert 0.0 <= result["matchScore"] <= 1.0
