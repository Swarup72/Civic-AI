"""
Deterministic trend analysis: complaint counts by time period (daily/weekly/
monthly), an overall trend direction + percentage change, and per-category
trends. No ML, no forecasting — pure, reproducible arithmetic on the same
input every time.
"""
from typing import Any, Dict

import pandas as pd

from app.config import settings

# pandas 2.2+/3.x frequency aliases — 'M' is deprecated in favor of 'ME'
# (month-END); 'D'/'W' are unaffected.
_PERIOD_FREQ = {"daily": "D", "weekly": "W", "monthly": "ME"}

SUPPORTED_PERIODS = tuple(_PERIOD_FREQ.keys())


def _period_counts(df: pd.DataFrame, period: str) -> pd.Series:
    freq = _PERIOD_FREQ[period]
    return df.set_index("createdAt").resample(freq).size()


def _trend_direction(counts: pd.Series) -> Dict[str, Any]:
    """Deterministic rule: split the period-bucket series into a first half
    and second half (by bucket count, not by calendar range), compare each
    half's average count.
        percentageChange >= +TREND_STABLE_BAND_PERCENT  -> "increasing"
        percentageChange <= -TREND_STABLE_BAND_PERCENT  -> "decreasing"
        otherwise                                        -> "stable"
    Fewer than 2 buckets means there's nothing to compare -> "insufficient_data".
    A first-half average of exactly zero makes a percentage change
    mathematically undefined (division by zero) — reported honestly as
    `percentageChange: None` rather than as a fabricated number, even though
    a direction can still be reasoned about (any growth from zero is
    "increasing")."""
    n = len(counts)
    if n < 2:
        return {"direction": "insufficient_data", "percentageChange": None}

    half = max(1, n // 2)
    first_half = counts.iloc[:half]
    second_half = counts.iloc[half:]

    first_avg = float(first_half.mean())
    second_avg = float(second_half.mean())

    if first_avg == 0 and second_avg == 0:
        return {"direction": "stable", "percentageChange": 0.0}
    if first_avg == 0:
        return {"direction": "increasing", "percentageChange": None}

    percentage_change = round(((second_avg - first_avg) / first_avg) * 100.0, 2)
    if percentage_change >= settings.TREND_STABLE_BAND_PERCENT:
        direction = "increasing"
    elif percentage_change <= -settings.TREND_STABLE_BAND_PERCENT:
        direction = "decreasing"
    else:
        direction = "stable"
    return {"direction": direction, "percentageChange": percentage_change}


def _bucket_label(timestamp: pd.Timestamp, period: str) -> str:
    if period == "monthly":
        return timestamp.strftime("%Y-%m")
    return timestamp.date().isoformat()


def analyze_period(df: pd.DataFrame, period: str) -> Dict[str, Any]:
    if period not in _PERIOD_FREQ:
        raise ValueError(f"Unsupported period '{period}' — must be one of {SUPPORTED_PERIODS}")

    counts = _period_counts(df, period)
    trend = _trend_direction(counts)

    buckets = [
        {"period": _bucket_label(idx, period), "count": int(count)}
        for idx, count in counts.items()
    ]

    return {
        "period": period,
        "buckets": buckets,
        "totalCount": int(counts.sum()),
        "trendDirection": trend["direction"],
        "percentageChange": trend["percentageChange"],
    }


def analyze_category_trends(df: pd.DataFrame, period: str = "monthly") -> Dict[str, Any]:
    """Per-category trend direction, using the SAME deterministic rule as
    the overall trend, applied to each category's own count series."""
    result = {}
    for category, group in df.groupby("category"):
        counts = _period_counts(group, period)
        trend = _trend_direction(counts)
        result[str(category)] = {
            "totalCount": int(counts.sum()),
            "trendDirection": trend["direction"],
            "percentageChange": trend["percentageChange"],
        }
    return result


def analyze_trends(df: pd.DataFrame) -> Dict[str, Any]:
    """The full trends section of the pipeline output."""
    return {
        "daily": analyze_period(df, "daily"),
        "weekly": analyze_period(df, "weekly"),
        "monthly": analyze_period(df, "monthly"),
        # Monthly is the least noisy granularity for a per-category rollup —
        # daily/weekly per-category series in a modest dataset are usually
        # too sparse for "increasing/decreasing" to mean anything.
        "categoryTrends": analyze_category_trends(df, period="monthly"),
    }
