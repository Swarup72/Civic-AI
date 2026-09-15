"""
Shared pytest fixtures for civicai-vision-lab. All image fixtures are
synthesized in-process (no external/downloaded test assets, no dependency on
the production CivicAI project's own test fixtures — this is an independent
reimplementation of the same general "synthesize a real, valid image with
controllable texture" technique)."""
import io

import numpy as np
import pytest
from PIL import Image

from app.services import vision_service


@pytest.fixture(autouse=True)
def _reset_vision_service_cache():
    """vision_service caches its load attempt once per process — reset it
    before AND after every test so one test's monkeypatched settings.MODEL_DIR
    (or forced load result) never leaks into the next."""
    vision_service.reset_cache()
    yield
    vision_service.reset_cache()


def make_textured_jpeg_bytes(seed: int = 1, width: int = 500, height: int = 400, shift: int = 0) -> bytes:
    """A random-noise JPEG with real texture (plenty of ORB keypoints).
    Same seed + shift=0 reproduces the exact same image (simulating a second
    photo of the SAME scene); same seed + nonzero shift simulates a slightly
    different framing of the same scene; a different seed simulates a
    genuinely different scene."""
    rng = np.random.RandomState(seed)
    base = (rng.rand(height, width, 3) * 255).astype("uint8")
    if shift:
        base = np.roll(base, shift, axis=1)
    buf = io.BytesIO()
    Image.fromarray(base, "RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def make_flat_jpeg_bytes(width: int = 400, height: int = 300, color=(120, 140, 160)) -> bytes:
    """A flat, textureless JPEG — valid and decodable, but has ~zero ORB
    keypoints (ambiguous scene comparison) and passes quality checks."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def make_blurry_jpeg_bytes(seed: int = 5, width: int = 500, height: int = 400) -> bytes:
    """A textured image, then heavily blurred — low sharpness score."""
    rng = np.random.RandomState(seed)
    base = (rng.rand(height, width, 3) * 255).astype("uint8")
    img = Image.fromarray(base, "RGB")
    # A large box blur radius destroys high-frequency detail, dropping the
    # Laplacian-variance sharpness score well below the default threshold.
    img = img.resize((width // 20, height // 20)).resize((width, height))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def make_low_resolution_jpeg_bytes(width: int = 50, height: int = 40) -> bytes:
    img = Image.new("RGB", (width, height), color=(100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_dark_jpeg_bytes(width: int = 400, height: int = 300) -> bytes:
    img = Image.new("RGB", (width, height), color=(5, 5, 5))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def textured_jpeg_factory():
    return make_textured_jpeg_bytes


@pytest.fixture
def write_image(tmp_path):
    """Factory fixture: write_image(data, name="x.jpg") -> str path."""
    def _write(data: bytes, name: str = "image.jpg") -> str:
        path = tmp_path / name
        path.write_bytes(data)
        return str(path)
    return _write
