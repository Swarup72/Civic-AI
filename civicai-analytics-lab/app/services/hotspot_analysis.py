"""
Area-level ("hotspot") analytics.

No geospatial clustering is implemented here, deliberately: this data model
(app/schemas/analytics_schema.py) has no latitude/longitude fields at all —
only a free-text `area` name — so per the task's own conditional instruction
("do NOT implement complex geospatial clustering unless the dataset
actually contains coordinates"), this module only ever does area-NAME-based
aggregation. If coordinates are added to the data model in the future,
geospatial clustering would be a natural, separate follow-up — not
attempted here.
"""
from typing import Any, Dict

import pandas as pd

from app.config import settings


def analyze_hotspots(df: pd.DataFrame) -> Dict[str, Any]:
    """`df` must already have priorityScore/priorityLabel columns (see
    priority_analysis.calculate_priority_for_dataframe) — hotspot analysis
    never computes priority itself, so there is exactly one place priority
    is ever calculated."""
    by_area = []
    for area, group in df.groupby("area"):
        high_priority_count = int(group["priorityLabel"].isin(settings.HIGH_PRIORITY_LABELS).sum())
        mode_result = group["category"].mode()
        dominant_category = str(mode_result.iloc[0]) if not mode_result.empty else None
        by_area.append({
            "area": str(area),
            "complaintCount": int(len(group)),
            "highPriorityCount": high_priority_count,
            "dominantCategory": dominant_category,
            "averagePriorityScore": round(float(group["priorityScore"].mean()), 2),
        })

    by_area.sort(key=lambda entry: entry["complaintCount"], reverse=True)
    top_areas_by_count = [entry["area"] for entry in by_area[:5]]

    by_high_priority = sorted(by_area, key=lambda entry: entry["highPriorityCount"], reverse=True)
    top_areas_by_high_priority = [entry["area"] for entry in by_high_priority[:5]]

    return {
        "byArea": by_area,
        "topAreasByCount": top_areas_by_count,
        "topAreasByHighPriority": top_areas_by_high_priority,
        "geospatialClusteringNote": (
            "Not implemented — this data model has no latitude/longitude fields; "
            "only area-name-based aggregation is performed (per the task's own "
            "conditional instruction)."
        ),
    }
