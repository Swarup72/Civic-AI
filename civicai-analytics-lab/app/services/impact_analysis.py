"""
Impact, department, and category analytics. All deterministic pandas/numpy
computations over an already-normalized, already-priority-scored DataFrame.

Never fabricates a value: a metric with no valid input (e.g. average
resolution days when zero complaints are resolved) is reported as `None`,
never as 0 and never silently omitted from the response.

Department/category analysis are implemented here (not as separate files) —
they are structurally "impact metrics grouped by one more dimension," reusing
this module's own resolution-day/high-priority-count logic rather than a
second, divergent copy of it.
"""
from typing import Any, Dict, Optional

import pandas as pd

from app.config import settings
from app.schemas.analytics_schema import RESOLVED_STATUSES


def _resolved_mask(df: pd.DataFrame) -> pd.Series:
    return df["status"].isin(RESOLVED_STATUSES) & df["resolvedAt"].notna()


def _resolution_days_series(df: pd.DataFrame) -> pd.Series:
    resolved = df[_resolved_mask(df)]
    if resolved.empty:
        return pd.Series(dtype=float)
    return (resolved["resolvedAt"] - resolved["createdAt"]).dt.total_seconds() / 86400.0


def analyze_impact(df: pd.DataFrame) -> Dict[str, Any]:
    total_complaints = int(len(df))
    total_affected_users = int(df["affectedUsers"].sum()) if total_complaints else 0
    average_affected_users = round(float(df["affectedUsers"].mean()), 2) if total_complaints else 0.0

    high_priority_count = int(df["priorityLabel"].isin(settings.HIGH_PRIORITY_LABELS).sum())
    critical_count = int((df["priorityLabel"] == "Critical").sum())

    resolved_mask = _resolved_mask(df) | df["status"].isin(RESOLVED_STATUSES)
    # Note: resolvedCount counts STATUS (a complaint marked RESOLVED/CONFIRMED),
    # independent of whether resolvedAt happens to be populated — a status can
    # legitimately be RESOLVED with a missing resolvedAt (bad data upstream),
    # which still counts as "resolved" for the rate, but is EXCLUDED from the
    # resolution-DAYS statistics below (which need a real duration to compute).
    resolved_count = int(df["status"].isin(RESOLVED_STATUSES).sum())
    unresolved_count = total_complaints - resolved_count
    resolution_rate = round((resolved_count / total_complaints) * 100.0, 2) if total_complaints else 0.0

    resolution_days = _resolution_days_series(df)
    if resolution_days.empty:
        average_resolution_days = None
        median_resolution_days = None
        fastest_resolution_days = None
        slowest_resolution_days = None
    else:
        average_resolution_days = round(float(resolution_days.mean()), 2)
        median_resolution_days = round(float(resolution_days.median()), 2)
        fastest_resolution_days = round(float(resolution_days.min()), 2)
        slowest_resolution_days = round(float(resolution_days.max()), 2)

    return {
        "totalComplaints": total_complaints,
        "totalAffectedUsers": total_affected_users,
        "averageAffectedUsers": average_affected_users,
        "highPriorityCount": high_priority_count,
        "criticalCount": critical_count,
        "resolvedCount": resolved_count,
        "unresolvedCount": unresolved_count,
        "resolutionRatePercentage": resolution_rate,
        "averageResolutionDays": average_resolution_days,
        "medianResolutionDays": median_resolution_days,
        "fastestResolutionDays": fastest_resolution_days,
        "slowestResolutionDays": slowest_resolution_days,
    }


def analyze_departments(df: pd.DataFrame) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for department, group in df.groupby("department"):
        total = int(len(group))
        resolved_count = int(group["status"].isin(RESOLVED_STATUSES).sum())
        resolution_days = _resolution_days_series(group)
        result[str(department)] = {
            "complaintCount": total,
            "highPriorityCount": int(group["priorityLabel"].isin(settings.HIGH_PRIORITY_LABELS).sum()),
            "resolvedCount": resolved_count,
            "unresolvedCount": total - resolved_count,
            "resolutionRatePercentage": round((resolved_count / total) * 100.0, 2) if total else 0.0,
            "averageResolutionDays": round(float(resolution_days.mean()), 2) if not resolution_days.empty else None,
        }
    return result


def analyze_categories(df: pd.DataFrame, category_trends: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    total = int(len(df))
    category_trends = category_trends or {}
    result: Dict[str, Any] = {}
    for category, group in df.groupby("category"):
        count = int(len(group))
        category_key = str(category)
        result[category_key] = {
            "count": count,
            "percentage": round((count / total) * 100.0, 2) if total else 0.0,
            "highPriorityCount": int(group["priorityLabel"].isin(settings.HIGH_PRIORITY_LABELS).sum()),
            "trend": category_trends.get(
                category_key,
                {"totalCount": count, "trendDirection": "insufficient_data", "percentageChange": None},
            ),
        }
    return result
