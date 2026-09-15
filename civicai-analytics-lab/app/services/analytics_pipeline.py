"""
The single orchestrator: normalize -> filter -> priority-score -> run every
analysis module -> one structured result, exactly the shape the API
contract promises. Both API endpoints (sample-dataset analysis and CSV
upload analysis) call this same function — there is exactly one analysis
code path, never two divergent ones.
"""
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from app.config import settings
from app.schemas.analytics_schema import REQUIRED_COLUMNS
from app.services import data_service, hotspot_analysis, impact_analysis, priority_analysis, trend_analysis


class AnalyticsError(ValueError):
    """Raised for a bad filter value or any other pipeline-level problem
    that isn't a raw dataset-validation issue (those raise
    data_service.DatasetValidationError directly, and are allowed to
    propagate unchanged — the API layer handles both the same way)."""


def _apply_filters(df: pd.DataFrame, filters: Optional[Dict[str, Any]]) -> pd.DataFrame:
    if not filters:
        return df
    df = df.copy()

    start_date = filters.get("startDate")
    if start_date:
        parsed = pd.to_datetime(start_date, errors="coerce", utc=True)
        if pd.isna(parsed):
            raise AnalyticsError(f"filters.startDate '{start_date}' is not a valid date.")
        df = df[df["createdAt"] >= parsed]

    end_date = filters.get("endDate")
    if end_date:
        parsed = pd.to_datetime(end_date, errors="coerce", utc=True)
        if pd.isna(parsed):
            raise AnalyticsError(f"filters.endDate '{end_date}' is not a valid date.")
        df = df[df["createdAt"] <= parsed]

    for field in ("category", "department", "area"):
        value = filters.get(field)
        if value:
            df = df[df[field] == value]

    return df


def _empty_period_result(period: str) -> Dict[str, Any]:
    return {"period": period, "buckets": [], "totalCount": 0, "trendDirection": "insufficient_data", "percentageChange": None}


def _dataset_meta(df_before_filters: pd.DataFrame, df_after_filters: pd.DataFrame, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    has_rows = len(df_after_filters) > 0
    return {
        "totalRowsBeforeFilters": int(len(df_before_filters)),
        "totalRowsAfterFilters": int(len(df_after_filters)),
        "filtersApplied": filters or {},
        "dateRange": {
            "earliest": df_after_filters["createdAt"].min().isoformat() if has_rows else None,
            "latest": df_after_filters["createdAt"].max().isoformat() if has_rows else None,
        },
        "requiredColumns": list(REQUIRED_COLUMNS),
        # Documented defaults (also in README.md) — repeated here so a caller
        # inspecting one API response, without reading source, still learns
        # exactly what was assumed for any missing optional field.
        "optionalFieldDefaults": {
            "resolvedAt": "missing/blank -> not yet resolved (null)",
            "supportCount": f"missing -> {settings.DEFAULT_SUPPORT_COUNT}",
            "affectedUsers": f"missing -> {settings.DEFAULT_AFFECTED_USERS}",
            "locationSensitivity": f"missing -> '{settings.DEFAULT_LOCATION_SENSITIVITY}'",
        },
    }


def analyze_dataset(
    records: Union[List[Dict[str, Any]], pd.DataFrame],
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """The one function every API route calls. Raises
    data_service.DatasetValidationError or AnalyticsError on bad input — the
    API layer translates those into a clear 400, never an unhandled 500.
    Returns the full `{"status": "success", ...}` envelope on success."""
    if isinstance(records, pd.DataFrame):
        normalized = data_service.normalize_records(records)
    else:
        normalized = data_service.load_and_normalize_records(records)

    filtered = _apply_filters(normalized, filters)
    dataset_meta = _dataset_meta(normalized, filtered, filters)

    scored = priority_analysis.calculate_priority_for_dataframe(filtered)

    if len(scored) == 0:
        trends = {
            "daily": _empty_period_result("daily"),
            "weekly": _empty_period_result("weekly"),
            "monthly": _empty_period_result("monthly"),
            "categoryTrends": {},
        }
        impact = impact_analysis.analyze_impact(scored)
        hotspots = {"byArea": [], "topAreasByCount": [], "topAreasByHighPriority": [],
                    "geospatialClusteringNote": hotspot_analysis.analyze_hotspots(scored)["geospatialClusteringNote"]}
        departments: Dict[str, Any] = {}
        categories: Dict[str, Any] = {}
        priority_summary = {"averageScore": None, "labelDistribution": {}, "topPriorityRecords": []}
    else:
        trends = trend_analysis.analyze_trends(scored)
        impact = impact_analysis.analyze_impact(scored)
        hotspots = hotspot_analysis.analyze_hotspots(scored)
        departments = impact_analysis.analyze_departments(scored)
        categories = impact_analysis.analyze_categories(scored, category_trends=trends["categoryTrends"])

        label_distribution = scored["priorityLabel"].value_counts().to_dict()
        top_priority = (
            scored.sort_values("priorityScore", ascending=False)
            .head(10)[["id", "category", "area", "department", "priorityScore", "priorityLabel"]]
            .to_dict("records")
        )
        priority_summary = {
            "averageScore": round(float(scored["priorityScore"].mean()), 2),
            "labelDistribution": {str(k): int(v) for k, v in label_distribution.items()},
            "topPriorityRecords": top_priority,
        }

    return {
        "status": "success",
        "dataset": dataset_meta,
        "impact": impact,
        "priority": priority_summary,
        "trends": trends,
        "hotspots": hotspots,
        "departments": departments,
        "categories": categories,
    }
