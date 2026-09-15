"""
Shared pytest fixtures for civicai-analytics-lab.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.fixture
def valid_records(now):
    """A small, hand-built, valid record set spanning several areas,
    categories, departments, and both resolved/unresolved statuses —
    reused across most test files as the 'known good' baseline."""
    return [
        {
            "id": "R1", "category": "Road Infrastructure", "severity": "Critical",
            "department": "Public Works", "area": "Kothrud",
            "createdAt": _iso(now - timedelta(days=10)),
            "resolvedAt": _iso(now - timedelta(days=8)),
            "status": "RESOLVED", "supportCount": 20, "affectedUsers": 100,
            "locationSensitivity": "High",
        },
        {
            "id": "R2", "category": "Waste Management", "severity": "Low",
            "department": "Sanitation", "area": "Aundh",
            "createdAt": _iso(now - timedelta(days=5)),
            "resolvedAt": "",
            "status": "SUBMITTED", "supportCount": 2, "affectedUsers": 15,
            "locationSensitivity": "Low",
        },
        {
            "id": "R3", "category": "Road Infrastructure", "severity": "High",
            "department": "Public Works", "area": "Kothrud",
            "createdAt": _iso(now - timedelta(days=3)),
            "resolvedAt": _iso(now - timedelta(days=1)),
            "status": "CONFIRMED", "supportCount": 10, "affectedUsers": 50,
            "locationSensitivity": "Medium",
        },
        {
            "id": "R4", "category": "Public Safety", "severity": "Critical",
            "department": "Police Liaison", "area": "Viman Nagar",
            "createdAt": _iso(now - timedelta(days=1)),
            "resolvedAt": "",
            "status": "ESCALATED", "supportCount": 30, "affectedUsers": 200,
            "locationSensitivity": "High",
        },
    ]


@pytest.fixture
def valid_dataframe(valid_records):
    return pd.DataFrame.from_records(valid_records)
