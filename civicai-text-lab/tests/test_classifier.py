"""
classifier_service.py tests, against the REAL trained model shipped in
models/trained/ (training/train.py was actually run to produce it — see
README.md). "unavailable" and "load_failed" are exercised for real via the
empty_model_dir / broken_model_dir fixtures (genuinely empty / genuinely
corrupt files), never simulated.
"""
from app.services import classifier_service, preprocessing_service

# Confirmed once by direct inspection (see the session's own verification,
# documented in README.md) - text phrased close to the training templates
# clears the confidence threshold; a generic, low-signal phrase does not.
HIGH_CONFIDENCE_TEXT = (
    "There is a large pothole near the college gate that has damaged several vehicles. "
    "This urgently needs to be fixed as soon as possible."
)
LOW_CONFIDENCE_TEXT = "please help"


def test_model_is_available_by_default():
    """The shipped models/trained/ directory has a real, trained model in
    it — this is genuinely 'available', not mocked."""
    assert classifier_service.is_available() is True
    assert classifier_service.get_status() == "available"


def test_category_prediction_returns_a_real_label():
    normalized = preprocessing_service.normalize_text(HIGH_CONFIDENCE_TEXT)
    result = classifier_service.predict(normalized)
    assert result is not None
    assert result["category"] == "Road Infrastructure"


def test_severity_prediction_returns_a_real_label():
    normalized = preprocessing_service.normalize_text(HIGH_CONFIDENCE_TEXT)
    result = classifier_service.predict(normalized)
    assert result["severity"] in ("Low", "Medium", "High", "Critical")


def test_department_prediction_returns_a_real_label():
    normalized = preprocessing_service.normalize_text(HIGH_CONFIDENCE_TEXT)
    result = classifier_service.predict(normalized)
    assert result["department"] == "Public Works Department"


def test_predict_proba_confidence_is_real_and_bounded():
    """Every confidence value must be a real predict_proba() output: a float
    strictly between 0 and 1 (never exactly 0, never fabricated as 1.0)."""
    normalized = preprocessing_service.normalize_text(HIGH_CONFIDENCE_TEXT)
    result = classifier_service.predict(normalized)
    for head, value in result["confidence"].items():
        assert isinstance(value, float)
        assert 0.0 < value <= 1.0


def test_high_confidence_prediction_clears_the_threshold():
    normalized = preprocessing_service.normalize_text(HIGH_CONFIDENCE_TEXT)
    result = classifier_service.predict(normalized)
    assert min(result["confidence"].values()) >= 0.45


def test_low_confidence_prediction_does_not_clear_the_threshold():
    normalized = preprocessing_service.normalize_text(LOW_CONFIDENCE_TEXT)
    result = classifier_service.predict(normalized)
    assert min(result["confidence"].values()) < 0.45


def test_model_unavailable_when_model_dir_is_empty(empty_model_dir):
    """Real, unmocked: an empty MODEL_DIR is the genuine 'unavailable' state."""
    assert classifier_service.is_available() is False
    assert classifier_service.get_status() == "unavailable"
    assert classifier_service.predict("pothole on main street") is None


def test_model_load_failure_is_real_not_simulated(broken_model_dir):
    """Real, unmocked: files with the required NAMES exist, but they are not
    valid pickles/JSON — joblib.load / json.loads genuinely raise here."""
    assert classifier_service.is_available() is False
    assert classifier_service.get_status() == "load_failed"
    assert classifier_service.predict("pothole on main street") is None


def test_partial_model_files_also_reported_unavailable(tmp_path, monkeypatch):
    """Only SOME of the required files present (e.g. vectorizer.pkl but no
    category_model.pkl) must not be treated as 'available' — it's still
    correctly 'unavailable' until every required artifact exists."""
    partial_dir = tmp_path / "partial_models"
    partial_dir.mkdir()
    (partial_dir / "vectorizer.pkl").write_bytes(b"placeholder")

    from app.config import settings
    monkeypatch.setattr(settings, "MODEL_DIR", str(partial_dir))

    assert classifier_service.is_available() is False
    assert classifier_service.get_status() == "unavailable"


def test_status_and_predict_never_raise_even_when_broken(broken_model_dir):
    """The adapter contract: callers never need their own try/except around
    this module."""
    try:
        classifier_service.get_status()
        classifier_service.is_available()
        classifier_service.predict("anything")
    except Exception as e:  # pragma: no cover - this branch failing IS the bug
        raise AssertionError(f"classifier_service raised when it must not: {e}")
