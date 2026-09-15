from datetime import datetime, timedelta, timezone

from app.config import settings
from app.services import priority_analysis


def _record(**overrides):
    now = datetime.now(timezone.utc)
    base = {
        "severity": "Medium",
        "affectedUsers": 10,
        "supportCount": 0,
        "locationSensitivity": "Medium",
        "status": "SUBMITTED",
        "createdAt": now - timedelta(hours=1),
        "resolvedAt": None,
    }
    base.update(overrides)
    return base


def test_priority_calculation_returns_required_shape():
    result = priority_analysis.calculate_priority(_record())
    assert set(result.keys()) == {"priorityScore", "priorityLabel", "factorBreakdown", "explanation"}
    assert isinstance(result["priorityScore"], int)
    assert isinstance(result["explanation"], list) and result["explanation"]


def test_priority_factor_breakdown_sums_to_score():
    result = priority_analysis.calculate_priority(_record(severity="High", affectedUsers=80, supportCount=15))
    assert round(sum(result["factorBreakdown"].values())) == result["priorityScore"]
    assert set(result["factorBreakdown"].keys()) == {
        "severity", "affectedUsers", "supportCount", "locationSensitivity", "duration"
    }


def test_high_priority_detection_critical_severity_maximal_signals():
    now = datetime.now(timezone.utc)
    result = priority_analysis.calculate_priority(_record(
        severity="Critical", affectedUsers=200, supportCount=30,
        locationSensitivity="High", createdAt=now - timedelta(days=10),
    ))
    assert result["priorityLabel"] == "Critical"
    assert result["priorityScore"] >= settings.PRIORITY_CRITICAL_MIN


def test_low_priority_detection_minimal_signals():
    now = datetime.now(timezone.utc)
    result = priority_analysis.calculate_priority(_record(
        severity="Low", affectedUsers=0, supportCount=0,
        locationSensitivity="Low", createdAt=now - timedelta(minutes=5),
    ))
    assert result["priorityLabel"] == "Low"
    assert result["priorityScore"] < settings.PRIORITY_MEDIUM_MIN


def test_resolved_complaint_uses_resolution_duration_not_time_since_creation():
    """A complaint resolved quickly long ago must score its DURATION factor
    based on how long it stayed open (short), not how long ago it was
    created (which could look like a very long time by 'now')."""
    now = datetime.now(timezone.utc)
    created = now - timedelta(days=365)  # created a year ago
    resolved = created + timedelta(hours=2)  # but resolved within 2 hours

    result = priority_analysis.calculate_priority(_record(
        status="RESOLVED", createdAt=created, resolvedAt=resolved,
    ), reference_now=now)
    # Duration score should be near-zero (resolved fast), not maxed out
    # (which it would be if "time since creation" were used instead).
    max_duration_contribution = settings.WEIGHT_DURATION * 100
    assert result["factorBreakdown"]["duration"] < max_duration_contribution * 0.1


def test_still_open_complaint_uses_time_since_creation():
    now = datetime.now(timezone.utc)
    created = now - timedelta(days=30)  # still open, created a month ago
    result = priority_analysis.calculate_priority(_record(
        status="SUBMITTED", createdAt=created, resolvedAt=None,
    ), reference_now=now)
    max_duration_contribution = settings.WEIGHT_DURATION * 100
    assert result["factorBreakdown"]["duration"] >= max_duration_contribution * 0.9  # near max — long open duration


def test_never_claims_verified_production_compatibility():
    """Explicit contract check from the task brief."""
    result = priority_analysis.calculate_priority(_record())
    joined = " ".join(result["explanation"]).lower()
    assert "not verified" in joined


def test_severity_ordering_is_monotonic():
    scores = {}
    for severity in ("Low", "Medium", "High", "Critical"):
        result = priority_analysis.calculate_priority(_record(severity=severity))
        scores[severity] = result["priorityScore"]
    assert scores["Low"] < scores["Medium"] < scores["High"] < scores["Critical"]


def test_priority_never_exceeds_100_or_goes_negative():
    result = priority_analysis.calculate_priority(_record(
        severity="Critical", affectedUsers=100000, supportCount=100000, locationSensitivity="High",
    ))
    assert 0 <= result["priorityScore"] <= 100


def test_missing_optional_fields_use_config_defaults_not_crash():
    """A record dict missing affectedUsers/supportCount/locationSensitivity
    entirely (e.g. hand-built, not from data_service) must not crash —
    calculate_priority() falls back to the same defaults data_service
    documents."""
    result = priority_analysis.calculate_priority({
        "severity": "Medium", "status": "SUBMITTED", "createdAt": datetime.now(timezone.utc),
    })
    assert isinstance(result["priorityScore"], int)
