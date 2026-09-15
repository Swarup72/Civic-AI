"""
Deterministic keyword/rule-based classifier — the one part of this pipeline
that is ALWAYS available, never depends on a trained model, and never fails.
Used whenever the ML classifier is unavailable, fails, or produces
insufficient confidence (see analysis_service.py).

Independently written for this prototype. Conceptually covers the same
civic-complaint domain as the production project's own rule-based fallback,
but shares no code, no keyword list, and no data file with it.
"""
from typing import Any, Dict, Tuple

from app.schemas.analysis_schema import CATEGORY_DEPARTMENT_MAP, ComplaintCategory, LocationSensitivity, SeverityLevel

# Each rule: (keywords, category, default_severity, affected_users_estimate, reason)
# Order matters — first match wins, most specific/safety-critical rules first.
_KEYWORD_RULES: Tuple[Tuple[Tuple[str, ...], ComplaintCategory, SeverityLevel, int, str], ...] = (
    (
        ("pothole", "road", "asphalt", "crater", "pavement", "tar", "cracked road"),
        ComplaintCategory.ROAD_INFRASTRUCTURE, SeverityLevel.HIGH, 60,
        "Road surface defect detected — likely to affect vehicle and pedestrian safety.",
    ),
    (
        ("garbage", "waste", "trash", "dump", "bin overflow", "litter", "stink", "rotting"),
        ComplaintCategory.WASTE_MANAGEMENT, SeverityLevel.MEDIUM, 35,
        "Sanitation/waste accumulation reported near a residential or public area.",
    ),
    (
        ("water leak", "pipe burst", "no water supply", "water shortage", "leaking tap", "water pipeline"),
        ComplaintCategory.WATER_SUPPLY, SeverityLevel.HIGH, 80,
        "Water supply interruption or pipeline leakage reported.",
    ),
    (
        ("drain", "sewer", "overflow", "gutter", "drainage", "sewage", "manhole"),
        ComplaintCategory.DRAINAGE_AND_SEWAGE, SeverityLevel.HIGH, 65,
        "Drainage/sewage blockage or overflow — a potential environmental/health hazard.",
    ),
    (
        ("street light", "streetlight", "lamp post", "dark street", "no light at night", "bulb fused"),
        ComplaintCategory.STREET_LIGHTING, SeverityLevel.MEDIUM, 30,
        "Public lighting failure — increases nighttime safety risk.",
    ),
    (
        ("unsafe", "crime", "harassment", "assault", "danger", "threat", "eve teasing", "stalking"),
        ComplaintCategory.PUBLIC_SAFETY, SeverityLevel.CRITICAL, 100,
        "Public-safety hazard reported — requires urgent attention.",
    ),
    (
        ("park", "garden", "playground", "bench broken", "tree fallen", "grass overgrown"),
        ComplaintCategory.PARKS_AND_PUBLIC_SPACES, SeverityLevel.LOW, 20,
        "Maintenance issue in a public park or green space.",
    ),
    (
        ("traffic jam", "signal not working", "illegal parking", "traffic light", "congestion", "no parking"),
        ComplaintCategory.TRAFFIC_AND_PARKING, SeverityLevel.MEDIUM, 45,
        "Traffic flow or parking obstruction reported.",
    ),
    (
        ("power outage", "transformer", "electric shock", "sparking wire", "power cut", "live wire"),
        ComplaintCategory.ELECTRICITY, SeverityLevel.HIGH, 90,
        "Electrical hazard or power-infrastructure failure reported.",
    ),
)

_SENSITIVE_LOCATION_KEYWORDS = ("school", "hospital", "college", "clinic", "station", "market", "kindergarten")

DEFAULT_AFFECTED_USERS = 15


def _location_sensitivity(text: str) -> LocationSensitivity:
    if any(keyword in text for keyword in _SENSITIVE_LOCATION_KEYWORDS):
        return LocationSensitivity.HIGH
    return LocationSensitivity.MEDIUM


def analyze(normalized_text: str) -> Dict[str, Any]:
    """Always returns a complete, plausible result — never raises, never
    returns a partial dict. `matched` (internal only, not part of the public
    API response) tells the caller whether a real keyword rule fired or this
    is the generic no-match default."""
    for keywords, category, severity, affected_users, reason in _KEYWORD_RULES:
        if any(keyword in normalized_text for keyword in keywords):
            department = CATEGORY_DEPARTMENT_MAP[category]
            sensitivity = _location_sensitivity(normalized_text)
            if sensitivity == LocationSensitivity.HIGH and severity == SeverityLevel.MEDIUM:
                severity = SeverityLevel.HIGH  # a medium issue near a school/hospital is not "medium" anymore
                reason += " Elevated due to proximity to a sensitive location (school/hospital/market)."
            return {
                "category": category.value,
                "severity": severity.value,
                "department": department.value,
                "affectedUsersEstimate": affected_users,
                "locationSensitivity": sensitivity.value,
                "reason": reason,
                "matched": True,
            }

    category = ComplaintCategory.OTHER
    department = CATEGORY_DEPARTMENT_MAP[category]
    return {
        "category": category.value,
        "severity": SeverityLevel.MEDIUM.value,
        "department": department.value,
        "affectedUsersEstimate": DEFAULT_AFFECTED_USERS,
        "locationSensitivity": _location_sensitivity(normalized_text).value,
        "reason": "No specific keyword pattern matched — generic civic complaint, needs manual review.",
        "matched": False,
    }
