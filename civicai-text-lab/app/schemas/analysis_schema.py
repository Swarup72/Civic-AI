"""
Standalone taxonomy + request/response schemas for CivicAI Text Intelligence
Lab. Independently defined for this prototype — not imported from, and not
shared with, the production project's app/schemas/enums.py or
app/schemas/complaint.py. The category/department vocabulary below reflects
the same general civic-complaint domain (a pothole is "Road Infrastructure"
in any sane taxonomy), but every value, mapping, and line of code here was
written fresh for this repository.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.config import settings


class ComplaintCategory(str, Enum):
    ROAD_INFRASTRUCTURE = "Road Infrastructure"
    WASTE_MANAGEMENT = "Waste Management"
    WATER_SUPPLY = "Water Supply"
    DRAINAGE_AND_SEWAGE = "Drainage and Sewage"
    STREET_LIGHTING = "Street Lighting"
    PUBLIC_SAFETY = "Public Safety"
    PARKS_AND_PUBLIC_SPACES = "Parks and Public Spaces"
    TRAFFIC_AND_PARKING = "Traffic and Parking"
    ELECTRICITY = "Electricity"
    OTHER = "Other"


class SeverityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class Department(str, Enum):
    PUBLIC_WORKS = "Public Works Department"
    SANITATION = "Municipal Sanitation"
    WATER = "Water Department"
    DRAINAGE = "Sewerage/Drainage Department"
    ELECTRICAL = "Electrical Department"
    PUBLIC_SAFETY = "Public Safety/Police Liaison"
    PARKS = "Parks Department"
    TRAFFIC = "Traffic Department"
    ELECTRICITY_UTILITY = "Electrical Utility"
    GENERAL = "General Municipal Helpdesk"


class LocationSensitivity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# Default category -> department mapping, used by the rule fallback and as a
# sanity cross-check (never a silent override) elsewhere. A trained
# department classifier is independent of this map (see training/train.py) —
# this is a deterministic default, not a substitute for it.
CATEGORY_DEPARTMENT_MAP = {
    ComplaintCategory.ROAD_INFRASTRUCTURE: Department.PUBLIC_WORKS,
    ComplaintCategory.WASTE_MANAGEMENT: Department.SANITATION,
    ComplaintCategory.WATER_SUPPLY: Department.WATER,
    ComplaintCategory.DRAINAGE_AND_SEWAGE: Department.DRAINAGE,
    ComplaintCategory.STREET_LIGHTING: Department.ELECTRICAL,
    ComplaintCategory.PUBLIC_SAFETY: Department.PUBLIC_SAFETY,
    ComplaintCategory.PARKS_AND_PUBLIC_SPACES: Department.PARKS,
    ComplaintCategory.TRAFFIC_AND_PARKING: Department.TRAFFIC,
    ComplaintCategory.ELECTRICITY: Department.ELECTRICITY_UTILITY,
    ComplaintCategory.OTHER: Department.GENERAL,
}


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class BatchAnalyzeRequest(BaseModel):
    # max_length reads settings.MAX_BATCH_SIZE directly rather than a second
    # hardcoded number, so the schema-level cap and the route-level cap
    # (api/routes.py) can never silently drift apart.
    texts: List[str] = Field(..., min_length=1, max_length=settings.MAX_BATCH_SIZE)


class AnalysisResult(BaseModel):
    """The one response shape every caller of this project gets, whether the
    result came from the trained ML pipeline or the rule fallback."""
    category: str
    severity: str
    department: str
    affectedUsersEstimate: int
    locationSensitivity: str
    reason: str
    confidence: Optional[float] = None  # null when source == "rule_fallback" - NEVER fabricated
    source: str  # "ml" | "rule_fallback"
    needsReview: bool
    modelVersion: str


class BatchAnalysisResult(BaseModel):
    results: List[AnalysisResult]
    count: int
