from datetime import timedelta

import pandas as pd

from app.services import impact_analysis, priority_analysis


def _row(**overrides):
    now = pd.Timestamp.now(tz="UTC")
    base = {
        "id": "X", "area": "Kothrud", "department": "Public Works", "category": "Road Infrastructure",
        "severity": "Medium", "status": "SUBMITTED", "createdAt": now, "resolvedAt": None,
        "affectedUsers": 10, "supportCount": 0, "locationSensitivity": "Medium",
    }
    base.update(overrides)
    return base


def _scored_df(rows):
    return priority_analysis.calculate_priority_for_dataframe(pd.DataFrame(rows))


def test_total_affected_users_is_a_real_sum():
    df = _scored_df([_row(affectedUsers=10), _row(affectedUsers=25), _row(affectedUsers=5)])
    result = impact_analysis.analyze_impact(df)
    assert result["totalAffectedUsers"] == 40
    assert result["averageAffectedUsers"] == round(40 / 3, 2)


def test_resolution_rate_computed_correctly():
    now = pd.Timestamp.now(tz="UTC")
    df = _scored_df([
        _row(status="RESOLVED", resolvedAt=now),
        _row(status="CONFIRMED", resolvedAt=now),
        _row(status="SUBMITTED", resolvedAt=None),
        _row(status="IN_PROGRESS", resolvedAt=None),
    ])
    result = impact_analysis.analyze_impact(df)
    assert result["resolvedCount"] == 2
    assert result["unresolvedCount"] == 2
    assert result["resolutionRatePercentage"] == 50.0


def test_average_and_median_resolution_days():
    created = pd.Timestamp.now(tz="UTC") - timedelta(days=20)
    df = _scored_df([
        _row(status="RESOLVED", createdAt=created, resolvedAt=created + timedelta(days=2)),
        _row(status="RESOLVED", createdAt=created, resolvedAt=created + timedelta(days=4)),
        _row(status="RESOLVED", createdAt=created, resolvedAt=created + timedelta(days=6)),
    ])
    result = impact_analysis.analyze_impact(df)
    assert result["averageResolutionDays"] == 4.0
    assert result["medianResolutionDays"] == 4.0
    assert result["fastestResolutionDays"] == 2.0
    assert result["slowestResolutionDays"] == 6.0


def test_resolution_stats_are_none_not_fabricated_when_nothing_resolved():
    df = _scored_df([_row(status="SUBMITTED"), _row(status="IN_PROGRESS")])
    result = impact_analysis.analyze_impact(df)
    assert result["averageResolutionDays"] is None
    assert result["medianResolutionDays"] is None
    assert result["fastestResolutionDays"] is None
    assert result["slowestResolutionDays"] is None
    assert result["resolutionRatePercentage"] == 0.0


def test_high_priority_and_critical_counts():
    df = _scored_df([
        _row(severity="Critical", affectedUsers=200, supportCount=30, locationSensitivity="High"),
        _row(severity="High", affectedUsers=80, supportCount=10, locationSensitivity="High"),
        _row(severity="Low", affectedUsers=1, supportCount=0, locationSensitivity="Low"),
    ])
    result = impact_analysis.analyze_impact(df)
    assert result["criticalCount"] >= 1
    assert result["highPriorityCount"] >= 2


def test_impact_totals_on_a_larger_realistic_batch():
    rows = [_row(id=f"R{i}") for i in range(50)]
    df = _scored_df(rows)
    result = impact_analysis.analyze_impact(df)
    assert result["totalComplaints"] == 50


# --- Department analysis --------------------------------------------------

def test_department_metrics_grouped_correctly():
    now = pd.Timestamp.now(tz="UTC")
    df = _scored_df([
        _row(department="Public Works", status="RESOLVED", createdAt=now - timedelta(days=3), resolvedAt=now),
        _row(department="Public Works", status="SUBMITTED"),
        _row(department="Sanitation", status="RESOLVED", createdAt=now - timedelta(days=1), resolvedAt=now),
    ])
    result = impact_analysis.analyze_departments(df)
    assert result["Public Works"]["complaintCount"] == 2
    assert result["Public Works"]["resolvedCount"] == 1
    assert result["Public Works"]["unresolvedCount"] == 1
    assert result["Sanitation"]["complaintCount"] == 1
    assert result["Sanitation"]["resolvedCount"] == 1


def test_department_average_resolution_time_is_none_when_unresolved():
    df = _scored_df([_row(department="Traffic", status="SUBMITTED")])
    result = impact_analysis.analyze_departments(df)
    assert result["Traffic"]["averageResolutionDays"] is None


# --- Category analysis ------------------------------------------------------

def test_category_count_and_percentage():
    df = _scored_df([
        _row(category="Road Infrastructure"),
        _row(category="Road Infrastructure"),
        _row(category="Waste Management"),
    ])
    result = impact_analysis.analyze_categories(df)
    assert result["Road Infrastructure"]["count"] == 2
    assert result["Road Infrastructure"]["percentage"] == round(2 / 3 * 100, 2)
    assert result["Waste Management"]["count"] == 1


def test_category_high_priority_count():
    df = _scored_df([
        _row(category="Public Safety", severity="Critical", affectedUsers=200, supportCount=30, locationSensitivity="High"),
        _row(category="Public Safety", severity="Low", affectedUsers=1, supportCount=0, locationSensitivity="Low"),
    ])
    result = impact_analysis.analyze_categories(df)
    assert result["Public Safety"]["highPriorityCount"] == 1


def test_category_trend_defaults_when_not_provided():
    df = _scored_df([_row(category="Road Infrastructure")])
    result = impact_analysis.analyze_categories(df, category_trends=None)
    assert result["Road Infrastructure"]["trend"]["trendDirection"] == "insufficient_data"


def test_category_trend_uses_provided_trend_data():
    df = _scored_df([_row(category="Road Infrastructure")])
    trends = {"Road Infrastructure": {"totalCount": 1, "trendDirection": "increasing", "percentageChange": 25.0}}
    result = impact_analysis.analyze_categories(df, category_trends=trends)
    assert result["Road Infrastructure"]["trend"]["trendDirection"] == "increasing"
