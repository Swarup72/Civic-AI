from datetime import datetime, timedelta, timezone

import pandas as pd

from app.services import trend_analysis


def _df_with_daily_counts(counts_per_day):
    """Builds a minimal DataFrame with exactly `counts_per_day[i]` rows on
    day i (0-indexed from a fixed start date), for deterministic trend tests."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for day_index, count in enumerate(counts_per_day):
        for _ in range(count):
            rows.append({"createdAt": start + timedelta(days=day_index), "category": "Road Infrastructure"})
    return pd.DataFrame(rows)


def test_increasing_trend_detected():
    # First half average = 2, second half average = 8 -> clearly increasing.
    df = _df_with_daily_counts([2, 2, 2, 2, 8, 8, 8, 8])
    result = trend_analysis.analyze_period(df, "daily")
    assert result["trendDirection"] == "increasing"
    assert result["percentageChange"] > 0


def test_decreasing_trend_detected():
    df = _df_with_daily_counts([8, 8, 8, 8, 2, 2, 2, 2])
    result = trend_analysis.analyze_period(df, "daily")
    assert result["trendDirection"] == "decreasing"
    assert result["percentageChange"] < 0


def test_stable_trend_detected():
    # Small fluctuation within the +/-10% band around a stable baseline.
    df = _df_with_daily_counts([10, 10, 10, 10, 10, 11, 10, 10])
    result = trend_analysis.analyze_period(df, "daily")
    assert result["trendDirection"] == "stable"


def test_insufficient_data_for_a_single_bucket():
    df = _df_with_daily_counts([5])
    result = trend_analysis.analyze_period(df, "daily")
    assert result["trendDirection"] == "insufficient_data"
    assert result["percentageChange"] is None


def test_zero_to_positive_growth_reports_undefined_percentage_honestly():
    """Growing from a true zero baseline makes a percentage change
    mathematically undefined - this must be reported as None, never a
    fabricated number (e.g. not 'inf%' or some arbitrary large number).

    Tests the underlying _trend_direction() unit directly with a hand-built
    Series, rather than going through analyze_period()'s resample() step:
    pandas' resample cannot materialize LEADING zero-buckets before the
    first actual data point (there's nothing in the raw data to anchor a
    "day 0, count 0" bucket to) - a real, worth-knowing pandas behavior, not
    a bug in this module. _trend_direction() is the actual unit responsible
    for the zero-baseline edge case and is reasonable to test directly."""
    counts = pd.Series([0, 0, 5, 5])
    result = trend_analysis._trend_direction(counts)
    assert result["direction"] == "increasing"
    assert result["percentageChange"] is None


def test_equal_halves_report_stable_with_exactly_zero_percent_change():
    df = _df_with_daily_counts([4, 4, 4, 4, 4, 4, 4, 4])
    result = trend_analysis.analyze_period(df, "daily")
    assert result["trendDirection"] == "stable"
    assert result["percentageChange"] == 0.0


def test_supported_periods_daily_weekly_monthly():
    df = _df_with_daily_counts([1] * 40)
    for period in ("daily", "weekly", "monthly"):
        result = trend_analysis.analyze_period(df, period)
        assert result["period"] == period
        assert result["totalCount"] == 40


def test_unsupported_period_raises_clear_error():
    df = _df_with_daily_counts([1, 2])
    import pytest
    with pytest.raises(ValueError, match="Unsupported period"):
        trend_analysis.analyze_period(df, "yearly")


def test_category_trends_computed_independently_per_category():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    # Road Infrastructure: increasing (2 -> 8 over two months)
    for month_offset, count in enumerate([2, 8]):
        for _ in range(count):
            rows.append({"createdAt": start + pd.DateOffset(months=month_offset), "category": "Road Infrastructure"})
    # Waste Management: decreasing (8 -> 2)
    for month_offset, count in enumerate([8, 2]):
        for _ in range(count):
            rows.append({"createdAt": start + pd.DateOffset(months=month_offset), "category": "Waste Management"})

    df = pd.DataFrame(rows)
    result = trend_analysis.analyze_category_trends(df, period="monthly")

    assert result["Road Infrastructure"]["trendDirection"] == "increasing"
    assert result["Waste Management"]["trendDirection"] == "decreasing"


def test_analyze_trends_returns_full_expected_shape():
    df = _df_with_daily_counts([3] * 10)
    result = trend_analysis.analyze_trends(df)
    assert set(result.keys()) == {"daily", "weekly", "monthly", "categoryTrends"}
