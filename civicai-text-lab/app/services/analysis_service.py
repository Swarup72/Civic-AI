"""
The single orchestrator: preprocess -> try ML -> confidence-gate -> rule
fallback when needed -> one structured, complete result.

Decision rule (deliberately binary, matching the task's own explicit
contract — never a half-measure that reports a low-confidence ML result as
if it were trustworthy):
  - ML unavailable, ML failed, OR ML confidence below threshold
        -> use the rule fallback ENTIRELY (confidence=null, source="rule_fallback",
           needsReview=True)
  - ML available AND confidence meets the threshold
        -> use the ML result (confidence=real value, source="ml",
           needsReview=False)
"""
from typing import Any, Dict

from app.schemas.analysis_schema import CATEGORY_DEPARTMENT_MAP, ComplaintCategory, LocationSensitivity
from app.services import classifier_service, confidence_service, preprocessing_service, rule_fallback_service

RULE_FALLBACK_MODEL_VERSION = "rule-fallback-v1"

# Operational defaults consulted ONLY on the ML-success path — the ML heads
# predict category/severity/department; affectedUsersEstimate and
# locationSensitivity are policy numbers layered on top of the predicted
# category, not classification targets themselves. The rule-fallback path
# computes its own equivalents directly (see rule_fallback_service.py) since
# it also has the raw text available to reason about sensitive locations.
_CATEGORY_AFFECTED_USERS_DEFAULT: Dict[str, int] = {
    ComplaintCategory.ROAD_INFRASTRUCTURE.value: 60,
    ComplaintCategory.WASTE_MANAGEMENT.value: 35,
    ComplaintCategory.WATER_SUPPLY.value: 80,
    ComplaintCategory.DRAINAGE_AND_SEWAGE.value: 65,
    ComplaintCategory.STREET_LIGHTING.value: 30,
    ComplaintCategory.PUBLIC_SAFETY.value: 100,
    ComplaintCategory.PARKS_AND_PUBLIC_SPACES.value: 20,
    ComplaintCategory.TRAFFIC_AND_PARKING.value: 45,
    ComplaintCategory.ELECTRICITY.value: 90,
    ComplaintCategory.OTHER.value: 15,
}

_SENSITIVE_LOCATION_KEYWORDS = ("school", "hospital", "college", "clinic", "station", "market", "kindergarten")


def _location_sensitivity_for(normalized_text: str) -> str:
    if any(keyword in normalized_text for keyword in _SENSITIVE_LOCATION_KEYWORDS):
        return LocationSensitivity.HIGH.value
    return LocationSensitivity.MEDIUM.value


def _empty_input_result() -> Dict[str, Any]:
    """Empty/whitespace-only input has no text to classify at all — this is
    NOT a low-confidence ML result and not a keyword-fallback miss; it's its
    own honest, explicit case."""
    return {
        "category": ComplaintCategory.OTHER.value,
        "severity": "Low",
        "department": CATEGORY_DEPARTMENT_MAP[ComplaintCategory.OTHER].value,
        "affectedUsersEstimate": 0,
        "locationSensitivity": LocationSensitivity.LOW.value,
        "reason": "No usable text was provided — nothing to classify.",
        "confidence": None,
        "source": "rule_fallback",
        "needsReview": True,
        "modelVersion": RULE_FALLBACK_MODEL_VERSION,
    }


def _ml_result_to_analysis(ml_result: Dict[str, Any], normalized_text: str) -> Dict[str, Any]:
    confidence_by_head = ml_result["confidence"]
    category = ml_result["category"]
    return {
        "category": category,
        "severity": ml_result["severity"],
        "department": ml_result["department"],
        "affectedUsersEstimate": _CATEGORY_AFFECTED_USERS_DEFAULT.get(category, 15),
        "locationSensitivity": _location_sensitivity_for(normalized_text),
        "reason": (
            f"Trained ML classifier prediction (confidence: category={confidence_by_head['category']}, "
            f"severity={confidence_by_head['severity']}, department={confidence_by_head['department']})."
        ),
        "confidence": confidence_service.overall_confidence(confidence_by_head),
        "source": "ml",
        "needsReview": False,
        "modelVersion": ml_result["modelVersion"],
    }


def _fallback_result(normalized_text: str) -> Dict[str, Any]:
    fallback = rule_fallback_service.analyze(normalized_text)
    return {
        "category": fallback["category"],
        "severity": fallback["severity"],
        "department": fallback["department"],
        "affectedUsersEstimate": fallback["affectedUsersEstimate"],
        "locationSensitivity": fallback["locationSensitivity"],
        "reason": fallback["reason"],
        "confidence": None,  # NEVER populated on the fallback path — see README's "no fabricated confidence" rule
        "source": "rule_fallback",
        "needsReview": True,
        "modelVersion": RULE_FALLBACK_MODEL_VERSION,
    }


def analyze_text(raw_text: str) -> Dict[str, Any]:
    """The one function the API layer calls. Always returns a complete,
    schema-shaped dict — never raises."""
    normalized = preprocessing_service.normalize_text(raw_text)

    if preprocessing_service.is_effectively_empty(normalized):
        return _empty_input_result()

    ml_result = classifier_service.predict(normalized)

    if ml_result is not None and confidence_service.meets_threshold(ml_result["confidence"]):
        return _ml_result_to_analysis(ml_result, normalized)

    return _fallback_result(normalized)
