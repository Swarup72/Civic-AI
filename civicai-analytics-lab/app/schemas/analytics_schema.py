"""
Standalone data model + API schemas for CivicAI Analytics Lab. Independently
defined for this prototype — no import of, or dependency on, the production
project's schemas.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class LocationSensitivity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ComplaintStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


REQUIRED_COLUMNS = ("id", "category", "severity", "department", "area", "createdAt", "status")
OPTIONAL_COLUMNS = ("resolvedAt", "supportCount", "affectedUsers", "locationSensitivity")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

RESOLVED_STATUSES = ("RESOLVED", "CONFIRMED")

# --- Filters ---------------------------------------------------------------


class AnalyzeFilters(BaseModel):
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    category: Optional[str] = None
    department: Optional[str] = None
    area: Optional[str] = None


class AnalyzeRequest(BaseModel):
    filters: Optional[AnalyzeFilters] = None


# --- Priority ----------------------------------------------------------------


class PriorityResult(BaseModel):
    priorityScore: int
    priorityLabel: str
    factorBreakdown: Dict[str, float]
    explanation: List[str]


# --- Response envelope -------------------------------------------------------


class AnalysisResponse(BaseModel):
    status: str
    dataset: Dict[str, Any]
    impact: Dict[str, Any]
    priority: Dict[str, Any]
    trends: Dict[str, Any]
    hotspots: Dict[str, Any]
    departments: Dict[str, Any]
    categories: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    service: str
    sampleDatasetAvailable: bool
