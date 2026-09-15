"""
End-to-end pipeline tests: analytics_pipeline.analyze_dataset() plus the API
layer (GET /api/health, POST /api/analyze, POST /api/analyze/upload) via
FastAPI's TestClient — no real network call, no running server needed.
"""
import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import analytics_pipeline, data_service

client = TestClient(app)


# --- Pipeline-level tests ---------------------------------------------------

def test_complete_pipeline_returns_every_required_top_level_key(valid_dataframe):
    result = analytics_pipeline.analyze_dataset(valid_dataframe)
    assert result["status"] == "success"
    for key in ("dataset", "impact", "priority", "trends", "hotspots", "departments", "categories"):
        assert key in result


def test_pipeline_priority_summary_shape(valid_dataframe):
    result = analytics_pipeline.analyze_dataset(valid_dataframe)
    priority = result["priority"]
    assert "averageScore" in priority
    assert "labelDistribution" in priority
    assert "topPriorityRecords" in priority
    assert len(priority["topPriorityRecords"]) <= 10


def test_pipeline_rejects_invalid_dataset_with_clear_error(valid_records):
    valid_records[0]["category"] = ""
    df = pd.DataFrame.from_records(valid_records)
    with pytest.raises(data_service.DatasetValidationError):
        analytics_pipeline.analyze_dataset(df)


def test_pipeline_accepts_list_of_dicts_directly(valid_records):
    result = analytics_pipeline.analyze_dataset(valid_records)
    assert result["status"] == "success"
    assert result["dataset"]["totalRowsBeforeFilters"] == len(valid_records)


def test_pipeline_never_writes_or_mutates_input(valid_dataframe):
    """Analytics-only guarantee: the pipeline must never change a
    complaint's status or mutate the caller's original DataFrame."""
    original_statuses = valid_dataframe["status"].copy()
    analytics_pipeline.analyze_dataset(valid_dataframe)
    pd.testing.assert_series_equal(valid_dataframe["status"], original_statuses)


# --- Filters -----------------------------------------------------------------

def test_category_filter(valid_dataframe):
    result = analytics_pipeline.analyze_dataset(valid_dataframe, filters={"category": "Road Infrastructure"})
    assert result["dataset"]["totalRowsAfterFilters"] == 2  # R1 and R3 in the fixture
    assert list(result["categories"].keys()) == ["Road Infrastructure"]


def test_department_filter(valid_dataframe):
    result = analytics_pipeline.analyze_dataset(valid_dataframe, filters={"department": "Public Works"})
    assert result["dataset"]["totalRowsAfterFilters"] == 2
    assert list(result["departments"].keys()) == ["Public Works"]


def test_area_filter(valid_dataframe):
    result = analytics_pipeline.analyze_dataset(valid_dataframe, filters={"area": "Viman Nagar"})
    assert result["dataset"]["totalRowsAfterFilters"] == 1


def test_date_range_filter(valid_dataframe, now):
    from datetime import timedelta
    start = (now - timedelta(days=4)).isoformat()
    result = analytics_pipeline.analyze_dataset(valid_dataframe, filters={"startDate": start})
    # Fixture records R2 (5 days ago), R3 (3 days ago), R4 (1 day ago) -> R3, R4 qualify (>= 4 days ago cutoff)
    assert result["dataset"]["totalRowsAfterFilters"] == 2


def test_invalid_filter_date_raises_clear_error(valid_dataframe):
    with pytest.raises(analytics_pipeline.AnalyticsError, match="startDate"):
        analytics_pipeline.analyze_dataset(valid_dataframe, filters={"startDate": "not-a-date"})


def test_filter_matching_nothing_returns_empty_but_valid_result(valid_dataframe):
    result = analytics_pipeline.analyze_dataset(valid_dataframe, filters={"category": "Does Not Exist"})
    assert result["status"] == "success"
    assert result["dataset"]["totalRowsAfterFilters"] == 0
    assert result["impact"]["totalComplaints"] == 0
    assert result["impact"]["averageResolutionDays"] is None
    assert result["departments"] == {}
    assert result["categories"] == {}


def test_combined_filters(valid_dataframe):
    result = analytics_pipeline.analyze_dataset(
        valid_dataframe, filters={"category": "Road Infrastructure", "area": "Kothrud"}
    )
    assert result["dataset"]["totalRowsAfterFilters"] == 2


# --- API layer ---------------------------------------------------------------

def test_api_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "civicai-analytics-lab"
    assert isinstance(body["sampleDatasetAvailable"], bool)


def test_api_analyze_sample_dataset():
    response = client.post("/api/analyze", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["dataset"]["totalRowsBeforeFilters"] > 0


def test_api_analyze_with_filters():
    response = client.post("/api/analyze", json={"filters": {"category": "Road Infrastructure"}})
    assert response.status_code == 200
    body = response.json()
    assert list(body["categories"].keys()) == ["Road Infrastructure"]


def _csv_bytes(records):
    df = pd.DataFrame.from_records(records)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def test_api_upload_endpoint_analyzes_a_valid_csv(valid_records):
    csv_bytes = _csv_bytes(valid_records)
    response = client.post(
        "/api/analyze/upload",
        files={"file": ("complaints.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["dataset"]["totalRowsBeforeFilters"] == len(valid_records)


def test_api_upload_endpoint_with_filters(valid_records):
    csv_bytes = _csv_bytes(valid_records)
    response = client.post(
        "/api/analyze/upload",
        files={"file": ("complaints.csv", csv_bytes, "text/csv")},
        data={"filters": json.dumps({"category": "Road Infrastructure"})},
    )
    assert response.status_code == 200
    assert response.json()["dataset"]["totalRowsAfterFilters"] == 2


def test_api_upload_rejects_malformed_csv_with_400():
    response = client.post(
        "/api/analyze/upload",
        files={"file": ("bad.csv", b"category,severity\nOnlyTwoColumns,High", "text/csv")},
    )
    assert response.status_code == 400
    assert "detail" in response.json()


def test_api_upload_rejects_empty_file():
    response = client.post(
        "/api/analyze/upload",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400


def test_api_upload_rejects_invalid_filters_json(valid_records):
    csv_bytes = _csv_bytes(valid_records)
    response = client.post(
        "/api/analyze/upload",
        files={"file": ("complaints.csv", csv_bytes, "text/csv")},
        data={"filters": "{ not valid json"},
    )
    assert response.status_code == 400


def test_api_upload_rejects_csv_with_invalid_data(valid_records):
    valid_records[0]["severity"] = "NotARealSeverity"
    csv_bytes = _csv_bytes(valid_records)
    response = client.post(
        "/api/analyze/upload",
        files={"file": ("complaints.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 400
    assert "severity" in response.json()["detail"]
