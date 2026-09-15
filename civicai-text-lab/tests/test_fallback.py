from app.services import preprocessing_service, rule_fallback_service


def _norm(text: str) -> str:
    return preprocessing_service.normalize_text(text)


def test_pothole_keyword_maps_to_road_infrastructure():
    result = rule_fallback_service.analyze(_norm("There is a huge pothole on the main road."))
    assert result["category"] == "Road Infrastructure"
    assert result["department"] == "Public Works Department"
    assert result["matched"] is True


def test_garbage_keyword_maps_to_waste_management():
    result = rule_fallback_service.analyze(_norm("Garbage has been dumped illegally near the park."))
    assert result["category"] == "Waste Management"


def test_public_safety_keyword_yields_critical_severity():
    result = rule_fallback_service.analyze(_norm("There was an assault reported near the station, very unsafe."))
    assert result["category"] == "Public Safety"
    assert result["severity"] == "Critical"


def test_sensitive_location_elevates_medium_to_high_severity():
    """A street-lighting complaint (default Medium) near a school must be
    elevated to High - matching the documented location-sensitivity rule."""
    result = rule_fallback_service.analyze(_norm("The street light near the school has been off for a week."))
    assert result["category"] == "Street Lighting"
    assert result["severity"] == "High"
    assert "sensitive location" in result["reason"].lower()


def test_no_keyword_match_falls_to_other_category():
    result = rule_fallback_service.analyze(_norm("xyz abc random text with no civic meaning"))
    assert result["category"] == "Other"
    assert result["matched"] is False


def test_fallback_always_returns_every_required_field():
    result = rule_fallback_service.analyze(_norm("some text"))
    for key in ("category", "severity", "department", "affectedUsersEstimate", "locationSensitivity", "reason"):
        assert key in result


def test_fallback_never_raises_on_empty_normalized_text():
    result = rule_fallback_service.analyze("")
    assert result["category"] == "Other"


def test_first_matching_rule_wins_for_multi_keyword_text():
    """Text mentioning both a pothole (road) and garbage (waste) should
    deterministically pick one rule, not error or blend two categories -
    road infrastructure rules are checked first (see _KEYWORD_RULES order)."""
    result = rule_fallback_service.analyze(_norm("There is a pothole and also some garbage nearby."))
    assert result["category"] == "Road Infrastructure"
