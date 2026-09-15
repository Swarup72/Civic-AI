"""
Standalone, deterministic priority scoring for ANALYTICS purposes only.

IMPORTANT — compatibility disclaimer (read before assuming anything): this
formula is INDEPENDENTLY DESIGNED for this analytics prototype. Its signals
(severity, affectedUsers, supportCount, locationSensitivity, duration) and
its weight split are a reasonable, common-sense default for this domain —
they are NOT copied from, and have NOT been verified against, the
production project's own priority_service.py (which this project never
imports, reads at runtime, or calls). **No compatibility with the
production formula is claimed anywhere in this codebase.** If exact
numeric compatibility is ever required, it must be established by a
deliberate, direct comparison against production's real output — not
assumed from a similar-looking weight split.

This is ANALYTICS ONLY: calculate_priority() is a pure function that reads
fields already present in a record. It NEVER changes a complaint's status,
NEVER writes to any database or file, and has no side effects at all.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd

from app.config import settings
from app.schemas.analytics_schema import RESOLVED_STATUSES

_SEVERITY_SCORES = {"Low": 25.0, "Medium": 50.0, "High": 75.0, "Critical": 100.0}
_LOCATION_SENSITIVITY_SCORES = {"Low": 25.0, "Medium": 50.0, "High": 100.0}

# A complaint open (or that took) 7 days (168h) reaches the maximum duration
# score — an independently chosen saturation point for this prototype, not
# a verified match to any production constant.
DURATION_FULL_SCORE_HOURS = 168.0

_DOMINANT_FACTOR_LABELS = {
    "severity": "its reported severity",
    "affectedUsers": "the number of affected users",
    "supportCount": "community support",
    "locationSensitivity": "location sensitivity",
    "duration": "how long it has been open (or took to resolve)",
}


def _severity_score(severity: Any) -> float:
    return _SEVERITY_SCORES.get(severity, 50.0)


def _affected_users_score(affected_users: Any) -> float:
    try:
        value = float(affected_users) if affected_users is not None else 0.0
    except (TypeError, ValueError):
        value = 0.0
    return min(100.0, max(0.0, value * 1.5))


def _support_score(support_count: Any) -> float:
    try:
        value = float(support_count) if support_count is not None else 0.0
    except (TypeError, ValueError):
        value = 0.0
    return min(100.0, max(0.0, value * 5.0))


def _location_sensitivity_score(location_sensitivity: Any) -> float:
    return _LOCATION_SENSITIVITY_SCORES.get(location_sensitivity, 50.0)


def _duration_hours(created_at, resolved_at, status: str, reference_now: Optional[datetime]) -> float:
    """A RESOLVED complaint's duration is how long it stayed open
    (resolvedAt - createdAt) — the historically meaningful number when
    analyzing a batch of past records. A still-open complaint's duration is
    how long it has been open as of `reference_now` (real now, by default)."""
    reference_now = reference_now or datetime.now(timezone.utc)
    if status in RESOLVED_STATUSES and resolved_at is not None and pd.notna(resolved_at):
        delta = resolved_at - created_at
    else:
        delta = reference_now - created_at
    seconds = delta.total_seconds()
    return max(0.0, seconds / 3600.0)


def _duration_score(hours: float) -> float:
    return min(100.0, max(0.0, (hours / DURATION_FULL_SCORE_HOURS) * 100.0))


def _label_for_score(score: float) -> str:
    if score >= settings.PRIORITY_CRITICAL_MIN:
        return "Critical"
    if score >= settings.PRIORITY_HIGH_MIN:
        return "High"
    if score >= settings.PRIORITY_MEDIUM_MIN:
        return "Medium"
    return "Low"


def calculate_priority(record: Dict[str, Any], reference_now: Optional[datetime] = None) -> Dict[str, Any]:
    """Returns {"priorityScore": int, "priorityLabel": str,
    "factorBreakdown": {...}, "explanation": [...]}. Pure — no side effects."""
    severity = record.get("severity", "Medium")
    affected_users = record.get("affectedUsers", settings.DEFAULT_AFFECTED_USERS)
    support_count = record.get("supportCount", settings.DEFAULT_SUPPORT_COUNT)
    location_sensitivity = record.get("locationSensitivity", settings.DEFAULT_LOCATION_SENSITIVITY)
    status = record.get("status", "SUBMITTED")
    created_at = record.get("createdAt")
    resolved_at = record.get("resolvedAt")

    severity_raw = _severity_score(severity)
    affected_raw = _affected_users_score(affected_users)
    support_raw = _support_score(support_count)
    location_raw = _location_sensitivity_score(location_sensitivity)

    if created_at is None or (hasattr(pd, "isna") and pd.isna(created_at)):
        duration_hours = 0.0
    else:
        duration_hours = _duration_hours(created_at, resolved_at, status, reference_now)
    duration_raw = _duration_score(duration_hours)

    contrib_severity = round(settings.WEIGHT_SEVERITY * severity_raw, 2)
    contrib_affected = round(settings.WEIGHT_AFFECTED_USERS * affected_raw, 2)
    contrib_support = round(settings.WEIGHT_SUPPORT_COUNT * support_raw, 2)
    contrib_location = round(settings.WEIGHT_LOCATION_SENSITIVITY * location_raw, 2)
    contrib_duration = round(settings.WEIGHT_DURATION * duration_raw, 2)

    total = contrib_severity + contrib_affected + contrib_support + contrib_location + contrib_duration
    total = min(100.0, max(0.0, total))
    score = int(round(total))
    label = _label_for_score(total)

    breakdown = {
        "severity": contrib_severity,
        "affectedUsers": contrib_affected,
        "supportCount": contrib_support,
        "locationSensitivity": contrib_location,
        "duration": contrib_duration,
    }
    dominant_factor = max(breakdown.items(), key=lambda kv: kv[1])[0]

    try:
        affected_users_int = int(float(affected_users)) if affected_users is not None else 0
    except (TypeError, ValueError):
        affected_users_int = 0
    try:
        support_count_int = int(float(support_count)) if support_count is not None else 0
    except (TypeError, ValueError):
        support_count_int = 0

    explanation = [
        f"Overall priority is {label} ({score}/100), driven mainly by {_DOMINANT_FACTOR_LABELS[dominant_factor]}.",
        f"Severity '{severity}' contributed {contrib_severity} point(s).",
        f"An estimated {affected_users_int} affected user(s) contributed {contrib_affected} point(s).",
        f"{support_count_int} community support signal(s) contributed {contrib_support} point(s).",
        f"Location sensitivity '{location_sensitivity}' contributed {contrib_location} point(s).",
        f"{'Resolved' if status in RESOLVED_STATUSES else 'Open'} for {round(duration_hours, 1)} hour(s), "
        f"contributing {contrib_duration} point(s).",
        "This is an independently-designed analytics score for this prototype — "
        "it is NOT verified to match the production priority formula's output.",
    ]

    return {
        "priorityScore": score,
        "priorityLabel": label,
        "factorBreakdown": breakdown,
        "explanation": explanation,
    }


def calculate_priority_for_dataframe(df: pd.DataFrame, reference_now: Optional[datetime] = None) -> pd.DataFrame:
    """Adds priorityScore/priorityLabel columns to a copy of `df` — the
    shared building block trend/hotspot/impact/department/category analysis
    all use, so "what counts as high priority" is computed exactly once."""
    df = df.copy()
    scores = []
    labels = []
    for record in df.to_dict("records"):
        result = calculate_priority(record, reference_now=reference_now)
        scores.append(result["priorityScore"])
        labels.append(result["priorityLabel"])
    df["priorityScore"] = scores
    df["priorityLabel"] = labels
    return df
