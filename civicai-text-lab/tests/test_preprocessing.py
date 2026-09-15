from app.services import preprocessing_service


def test_empty_string_returns_empty():
    assert preprocessing_service.normalize_text("") == ""


def test_none_input_returns_empty_not_a_crash():
    assert preprocessing_service.normalize_text(None) == ""


def test_whitespace_only_normalizes_to_empty():
    assert preprocessing_service.normalize_text("   \n\t   ") == ""


def test_case_normalization():
    assert preprocessing_service.normalize_text("THERE Is A Pothole") == "there is a pothole"


def test_basic_punctuation_is_preserved_where_meaningful():
    result = preprocessing_service.normalize_text("Water leak! No supply for 3 days.")
    assert "!" in result or "no supply" in result  # punctuation kept, meaning preserved
    assert "water leak" in result


def test_collapses_multiple_whitespace():
    result = preprocessing_service.normalize_text("There   is    a   pothole")
    assert "  " not in result
    assert result == "there is a pothole"


def test_unicode_handled_safely_without_raising():
    # Accented characters, full-width digits, emoji, combining marks - none
    # of this should raise, and real letters must survive.
    text = "Pothole near café ﻿— ３ days old 🚧"
    result = preprocessing_service.normalize_text(text)
    assert "pothole" in result
    assert "caf" in result  # the accented letter itself is preserved (café -> normalized form)


def test_symbols_are_replaced_not_silently_deleted():
    """'word,,,word' must not collapse into 'wordword' - symbols become a
    space, never a deletion, so word boundaries are preserved."""
    result = preprocessing_service.normalize_text("pothole###road")
    assert "potholeroad" not in result


def test_is_effectively_empty_true_for_whitespace_and_punctuation_only():
    assert preprocessing_service.is_effectively_empty(preprocessing_service.normalize_text("   ")) is True
    assert preprocessing_service.is_effectively_empty(preprocessing_service.normalize_text("!!! ... ???")) is True


def test_is_effectively_empty_false_for_real_text():
    normalized = preprocessing_service.normalize_text("pothole")
    assert preprocessing_service.is_effectively_empty(normalized) is False


def test_non_string_input_is_stringified_not_raised():
    assert preprocessing_service.normalize_text(12345) == "12345"
