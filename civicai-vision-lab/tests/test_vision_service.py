"""
vision_service.py adapter tests — all 5 required states.

"unavailable", "load_failed", and "invalid_image" are exercised FOR REAL
against this module's actual code paths (no model backend is implemented in
this prototype by design, so a model directory with content genuinely raises
today — see vision_service.py's own docstring). "ok" and "inference_failed"
are exercised via a monkeypatched fake model, since no real model ships with
this prototype and none should be trained here — that fake model is clearly
local to this test file, never imported by application code.
"""
from app.services import vision_service
from tests.conftest import make_textured_jpeg_bytes


class _FakeModel:
    version = "fake-test-model-v1"

    def __init__(self, label="fixed", confidence=0.91, raise_on_predict=False):
        self._label = label
        self._confidence = confidence
        self._raise = raise_on_predict

    def predict(self, image):
        if self._raise:
            raise RuntimeError("simulated inference failure")
        return self._label, self._confidence


def test_model_unavailable_by_default(write_image):
    """Real, unmocked: models/pretrained/ ships empty in this prototype."""
    assert vision_service.is_available() is False
    assert vision_service.get_status() == "unavailable"

    image_path = write_image(make_textured_jpeg_bytes(seed=1), "before.jpg")
    result = vision_service.analyze_image(image_path)
    assert result["available"] is False
    assert result["status"] == "unavailable"
    assert result["label"] is None
    assert result["confidence"] is None


def test_model_loading_failure_is_real_not_simulated(tmp_path, monkeypatch, write_image):
    """Real, unmocked: pointing MODEL_DIR at a directory that has SOME file
    in it (but this prototype implements no real loading backend) genuinely
    raises inside _load_model() and is caught as load_failed - not mocked."""
    fake_model_dir = tmp_path / "pretrained"
    fake_model_dir.mkdir()
    (fake_model_dir / "some_model_file.bin").write_bytes(b"not a real model")

    from app.config import settings
    monkeypatch.setattr(settings, "MODEL_DIR", str(fake_model_dir))

    assert vision_service.is_available() is False
    assert vision_service.get_status() == "load_failed"

    image_path = write_image(make_textured_jpeg_bytes(seed=1), "before.jpg")
    result = vision_service.analyze_image(image_path)
    assert result["status"] == "load_failed"
    assert result["available"] is False
    assert result["label"] is None
    assert "failed to load" in result["reasons"][0].lower()


def test_invalid_image_returns_invalid_status(write_image, monkeypatch):
    """Real, unmocked file-decode failure - but only reachable once a model
    IS available, since 'unavailable' is checked before image validity. Force
    availability via a fake model (monkeypatched, auto-reverted) to reach
    this specific branch."""
    monkeypatch.setattr(vision_service, "_model", _FakeModel())
    monkeypatch.setattr(vision_service, "_load_attempted", True)

    bad_path = write_image(b"definitely not an image", "corrupt.jpg")
    result = vision_service.analyze_image(bad_path)
    assert result["status"] == "invalid_image"
    assert result["available"] is False
    assert result["label"] is None


def test_available_and_successful_inference(write_image, monkeypatch):
    fake = _FakeModel(label="fixed", confidence=0.87)
    monkeypatch.setattr(vision_service, "_model", fake)
    monkeypatch.setattr(vision_service, "_load_attempted", True)

    image_path = write_image(make_textured_jpeg_bytes(seed=3), "after.jpg")
    result = vision_service.analyze_image(image_path)

    assert result["available"] is True
    assert result["status"] == "ok"
    assert result["label"] == "fixed"
    assert result["confidence"] == 0.87
    assert result["modelVersion"] == "fake-test-model-v1"


def test_inference_failure(write_image, monkeypatch):
    fake = _FakeModel(raise_on_predict=True)
    monkeypatch.setattr(vision_service, "_model", fake)
    monkeypatch.setattr(vision_service, "_load_attempted", True)

    image_path = write_image(make_textured_jpeg_bytes(seed=4), "after.jpg")
    result = vision_service.analyze_image(image_path)

    assert result["status"] == "inference_failed"
    assert result["available"] is False
    assert result["label"] is None
    assert result["confidence"] is None
    assert "simulated inference failure" in result["reasons"][0]


def test_never_fabricates_a_result_when_unavailable(write_image):
    """The specific, explicit contract check: unavailable must never carry a
    label or confidence, under any circumstance."""
    image_path = write_image(make_textured_jpeg_bytes(seed=1), "x.jpg")
    result = vision_service.analyze_image(image_path)
    assert result["status"] == "unavailable"
    assert result["label"] is None
    assert result["confidence"] is None


def test_status_is_cached_after_first_check(tmp_path, monkeypatch):
    """_ensure_loaded() should only attempt loading once per process, not
    once per call — this is asserted by changing MODEL_DIR AFTER the first
    check and confirming the (now stale) cached result is what's returned."""
    assert vision_service.get_status() == "unavailable"

    fake_model_dir = tmp_path / "pretrained_late"
    fake_model_dir.mkdir()
    (fake_model_dir / "file.bin").write_bytes(b"x")
    from app.config import settings
    monkeypatch.setattr(settings, "MODEL_DIR", str(fake_model_dir))

    # Still "unavailable" - the load attempt was already cached before MODEL_DIR changed.
    assert vision_service.get_status() == "unavailable"

    vision_service.reset_cache()
    assert vision_service.get_status() == "load_failed"
