import pandas as pd
import pytest

from app.services import data_service


def test_valid_dataset_normalizes_without_error(valid_dataframe):
    normalized = data_service.normalize_records(valid_dataframe)
    assert len(normalized) == len(valid_dataframe)
    assert pd.api.types.is_datetime64_any_dtype(normalized["createdAt"])


def test_missing_required_column_is_rejected(valid_records):
    for record in valid_records:
        record.pop("category", None)
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError, match="missing required column"):
        data_service.normalize_records(df)


def test_invalid_dates_are_rejected_with_row_indices(valid_records):
    valid_records[1]["createdAt"] = "not-a-real-date"
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError, match="createdAt"):
        data_service.normalize_records(df)


def test_missing_created_at_is_rejected_not_silently_dropped(valid_records):
    valid_records[0]["createdAt"] = ""
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError):
        data_service.normalize_records(df)


def test_resolved_at_before_created_at_is_rejected(valid_records):
    valid_records[0]["createdAt"] = "2026-09-10T00:00:00Z"
    valid_records[0]["resolvedAt"] = "2026-09-01T00:00:00Z"  # before createdAt - impossible
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError, match="BEFORE"):
        data_service.normalize_records(df)


def test_invalid_numeric_data_is_rejected(valid_records):
    valid_records[0]["supportCount"] = "not-a-number"
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError, match="supportCount"):
        data_service.normalize_records(df)


def test_negative_numeric_data_is_rejected(valid_records):
    valid_records[0]["affectedUsers"] = -5
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError, match="affectedUsers"):
        data_service.normalize_records(df)


def test_empty_dataset_is_rejected():
    df = pd.DataFrame(columns=["id", "category", "severity", "department", "area", "createdAt", "status"])
    with pytest.raises(data_service.DatasetValidationError, match="empty"):
        data_service.normalize_records(df)


def test_invalid_severity_value_is_rejected(valid_records):
    valid_records[0]["severity"] = "SuperExtreme"
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError, match="severity"):
        data_service.normalize_records(df)


def test_invalid_status_value_is_rejected(valid_records):
    valid_records[0]["status"] = "NOT_A_REAL_STATUS"
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError, match="status"):
        data_service.normalize_records(df)


def test_duplicate_ids_are_rejected(valid_records):
    valid_records[1]["id"] = valid_records[0]["id"]
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError, match="unique"):
        data_service.normalize_records(df)


def test_missing_optional_fields_get_documented_defaults():
    """Optional columns entirely absent from the dataset must not be
    rejected — they get the documented safe defaults (see app/config.py)."""
    minimal_records = [
        {
            "id": "M1", "category": "Other", "severity": "Medium",
            "department": "General", "area": "Somewhere",
            "createdAt": "2026-09-01T00:00:00Z", "status": "SUBMITTED",
        }
    ]
    df = pd.DataFrame.from_records(minimal_records)
    normalized = data_service.normalize_records(df)
    row = normalized.iloc[0]
    assert row["supportCount"] == 0
    assert row["affectedUsers"] == 10
    assert row["locationSensitivity"] == "Medium"
    assert pd.isna(row["resolvedAt"])


def test_malformed_csv_bytes_produce_a_clear_error():
    with pytest.raises(data_service.DatasetValidationError):
        data_service.load_csv(b"\x00\x01\x02 this is not a csv file at all \xff\xfe")


def test_rejects_all_records_not_just_the_bad_one(valid_records):
    """A dataset-level rejection must not silently drop the offending row
    and proceed with the rest — the whole dataset is rejected, with the
    problem clearly identified, so the caller can fix their source data."""
    valid_records[1]["category"] = ""
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError) as exc_info:
        data_service.normalize_records(df)
    assert "1" in str(exc_info.value)  # row index 1 named in the error
