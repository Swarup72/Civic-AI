"""
End-to-end pipeline tests: analysis_service.analyze_text() (the function the
API layer calls) plus the API layer itself (POST /api/analyze,
POST /api/analyze/batch) via FastAPI's TestClient — no real network call, no
running server process needed.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services import analysis_service

client = TestClient(app)

HIGH_CONFIDENCE_TEXT = (
    "There is a large pothole near the college gate that has damaged several vehicles. "
    "This urgently needs to be fixed as soon as possible."
)


def test_complete_analysis_pipeline_returns_every_required_field():
    result = analysis_service.analyze_text("There is a huge pothole near the market causing accidents.")
    for key in (
        "category", "severity", "department", "affectedUsersEstimate", "locationSensitivity",
        "reason", "confidence", "source", "needsReview", "modelVersion",
    ):
        assert key in result


def test_pipeline_uses_ml_source_for_high_confidence_text():
    result = analysis_service.analyze_text(HIGH_CONFIDENCE_TEXT)
    assert result["source"] == "ml"
    assert result["confidence"] is not None
    assert isinstance(result["confidence"], float)
    assert result["needsReview"] is False


def test_pipeline_uses_rule_fallback_for_low_confidence_text():
    result = analysis_service.analyze_text("please help")
    assert result["source"] == "rule_fallback"
    assert result["confidence"] is None
    assert result["needsReview"] is True


def test_pipeline_handles_empty_text_without_crashing():
    result = analysis_service.analyze_text("")
    assert result["source"] == "rule_fallback"
    assert result["confidence"] is None
    assert result["needsReview"] is True
    assert "no usable text" in result["reason"].lower()


def test_pipeline_handles_whitespace_only_text():
    result = analysis_service.analyze_text("     \n\t   ")
    assert result["confidence"] is None
    assert result["source"] == "rule_fallback"


def test_pipeline_falls_back_when_model_unavailable(empty_model_dir):
    result = analysis_service.analyze_text(HIGH_CONFIDENCE_TEXT)
    assert result["source"] == "rule_fallback"
    assert result["confidence"] is None
    assert result["category"] == "Road Infrastructure"  # rule fallback still gets this right via keywords


def test_pipeline_falls_back_when_model_load_fails(broken_model_dir):
    result = analysis_service.analyze_text(HIGH_CONFIDENCE_TEXT)
    assert result["source"] == "rule_fallback"
    assert result["confidence"] is None


def test_no_fabricated_confidence_anywhere_on_the_fallback_path():
    """The single most important contract check in this whole project:
    confidence MUST be null whenever source == 'rule_fallback', under every
    circumstance that reaches that path."""
    scenarios = ["please help", "", "   ", "xyz nonsense text"]
    for text in scenarios:
        result = analysis_service.analyze_text(text)
        if result["source"] == "rule_fallback":
            assert result["confidence"] is None, f"Fabricated confidence on fallback path for input: {text!r}"


# --- API layer -----------------------------------------------------------

def test_api_analyze_endpoint_returns_full_shape():
    response = client.post("/api/analyze", json={"text": HIGH_CONFIDENCE_TEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] in ("ml", "rule_fallback")
    assert "category" in body and "severity" in body and "department" in body


def test_api_analyze_rejects_empty_text_at_the_schema_level():
    """min_length=1 on AnalyzeRequest.text - an empty string should be a 422
    schema-validation rejection, not a 200 with a degraded result; a caller
    that WANTS the 'no usable text' behavior sends whitespace, not "" (which
    the schema itself refuses)."""
    response = client.post("/api/analyze", json={"text": ""})
    assert response.status_code == 422


def test_api_analyze_handles_whitespace_only_text_as_effectively_empty():
    response = client.post("/api/analyze", json={"text": "    "})
    assert response.status_code == 200
    assert response.json()["source"] == "rule_fallback"


def test_api_batch_analyze_returns_one_result_per_input():
    texts = [
        "There is a huge pothole near the market.",
        "Garbage has been piling up for a week.",
        "please help",
    ]
    response = client.post("/api/analyze/batch", json={"texts": texts})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert len(body["results"]) == 3
    for result in body["results"]:
        assert "category" in result and "source" in result


def test_api_batch_analyze_rejects_oversized_batch():
    from app.config import settings
    texts = ["some complaint text"] * (settings.MAX_BATCH_SIZE + 1)
    response = client.post("/api/analyze/batch", json={"texts": texts})
    assert response.status_code in (400, 422)


def test_api_status_endpoint_reports_real_classifier_state():
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["classifierStatus"] in ("available", "unavailable", "load_failed")
