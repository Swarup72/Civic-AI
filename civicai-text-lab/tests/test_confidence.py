from app.services import confidence_service


def test_overall_confidence_is_the_weakest_head():
    confidence = {"category": 0.95, "severity": 0.30, "department": 0.90}
    assert confidence_service.overall_confidence(confidence) == 0.30


def test_overall_confidence_empty_dict_is_zero():
    assert confidence_service.overall_confidence({}) == 0.0


def test_meets_threshold_true_when_all_heads_high():
    confidence = {"category": 0.9, "severity": 0.8, "department": 0.95}
    assert confidence_service.meets_threshold(confidence, threshold=0.45) is True


def test_meets_threshold_false_when_any_head_low():
    confidence = {"category": 0.9, "severity": 0.2, "department": 0.95}
    assert confidence_service.meets_threshold(confidence, threshold=0.45) is False


def test_needs_review_is_the_inverse_of_meets_threshold():
    confidence = {"category": 0.9, "severity": 0.2, "department": 0.95}
    assert confidence_service.needs_review(confidence, threshold=0.45) is True
    assert confidence_service.meets_threshold(confidence, threshold=0.45) is False


def test_uses_configured_default_threshold_when_not_specified():
    from app.config import settings
    exactly_at_default = {"category": settings.CONFIDENCE_THRESHOLD, "severity": settings.CONFIDENCE_THRESHOLD}
    assert confidence_service.meets_threshold(exactly_at_default) is True

    just_below_default = {"category": settings.CONFIDENCE_THRESHOLD - 0.01}
    assert confidence_service.meets_threshold(just_below_default) is False


def test_never_fabricates_or_adjusts_the_input_values():
    """This module must be a pure read of what it's given - it must never
    round, boost, or otherwise alter the confidence values themselves."""
    confidence = {"category": 0.123456}
    assert confidence_service.overall_confidence(confidence) == 0.123456
