"""
Shared pytest fixtures for civicai-text-lab.

IMPORTANT: unlike a from-scratch prototype, this project DOES ship a real
trained model under models/trained/ (training/train.py was actually run —
see README.md). That means classifier_service.get_status() is genuinely
"available" by default here. Tests that need to exercise "unavailable" or
"load_failed" must explicitly redirect settings.MODEL_DIR to a controlled
temp directory — see the `empty_model_dir` / `broken_model_dir` fixtures
below — rather than relying on the shipped default, which is correctly
"available".
"""
import pytest

from app.services import classifier_service


@pytest.fixture(autouse=True)
def _reset_classifier_cache():
    """classifier_service caches its load attempt once per process — reset
    it before AND after every test so one test's monkeypatched MODEL_DIR (or
    forced load result) never leaks into the next."""
    classifier_service.reset_cache()
    yield
    classifier_service.reset_cache()


@pytest.fixture
def empty_model_dir(tmp_path, monkeypatch):
    """Points MODEL_DIR at a real, empty directory — the genuine
    'unavailable' state, exercised for real (not mocked)."""
    empty_dir = tmp_path / "empty_models"
    empty_dir.mkdir()
    from app.config import settings
    monkeypatch.setattr(settings, "MODEL_DIR", str(empty_dir))
    return str(empty_dir)


@pytest.fixture
def broken_model_dir(tmp_path, monkeypatch):
    """Points MODEL_DIR at a directory with all the REQUIRED FILENAMES
    present, but containing garbage bytes instead of real pickled models —
    genuinely triggers a real joblib/json load failure, not a simulated one."""
    broken_dir = tmp_path / "broken_models"
    broken_dir.mkdir()
    (broken_dir / "vectorizer.pkl").write_bytes(b"not a real pickle file")
    (broken_dir / "category_model.pkl").write_bytes(b"not a real pickle file")
    (broken_dir / "severity_model.pkl").write_bytes(b"not a real pickle file")
    (broken_dir / "department_model.pkl").write_bytes(b"not a real pickle file")
    (broken_dir / "metadata.json").write_text("{ this is not valid json")

    from app.config import settings
    monkeypatch.setattr(settings, "MODEL_DIR", str(broken_dir))
    return str(broken_dir)
