import pandas as pd

from app.services import hotspot_analysis, priority_analysis


def _scored_df(rows):
    df = pd.DataFrame(rows)
    return priority_analysis.calculate_priority_for_dataframe(df)


def test_top_hotspot_area_by_complaint_count():
    rows = (
        [{"area": "Kothrud", "category": "Road Infrastructure", "severity": "Medium",
          "status": "SUBMITTED", "createdAt": pd.Timestamp.now(tz="UTC"), "resolvedAt": None,
          "affectedUsers": 10, "supportCount": 0, "locationSensitivity": "Medium"}] * 5
        + [{"area": "Aundh", "category": "Waste Management", "severity": "Low",
            "status": "SUBMITTED", "createdAt": pd.Timestamp.now(tz="UTC"), "resolvedAt": None,
            "affectedUsers": 10, "supportCount": 0, "locationSensitivity": "Medium"}] * 2
    )
    df = _scored_df(rows)
    result = hotspot_analysis.analyze_hotspots(df)
    assert result["topAreasByCount"][0] == "Kothrud"


def test_dominant_category_per_area():
    rows = (
        [{"area": "Kothrud", "category": "Road Infrastructure", "severity": "Medium",
          "status": "SUBMITTED", "createdAt": pd.Timestamp.now(tz="UTC"), "resolvedAt": None,
          "affectedUsers": 10, "supportCount": 0, "locationSensitivity": "Medium"}] * 4
        + [{"area": "Kothrud", "category": "Waste Management", "severity": "Low",
            "status": "SUBMITTED", "createdAt": pd.Timestamp.now(tz="UTC"), "resolvedAt": None,
            "affectedUsers": 10, "supportCount": 0, "locationSensitivity": "Medium"}] * 1
    )
    df = _scored_df(rows)
    result = hotspot_analysis.analyze_hotspots(df)
    kothrud_entry = next(a for a in result["byArea"] if a["area"] == "Kothrud")
    assert kothrud_entry["dominantCategory"] == "Road Infrastructure"


def test_high_priority_count_per_area():
    rows = (
        [{"area": "Viman Nagar", "category": "Public Safety", "severity": "Critical",
          "status": "SUBMITTED", "createdAt": pd.Timestamp.now(tz="UTC"), "resolvedAt": None,
          "affectedUsers": 200, "supportCount": 30, "locationSensitivity": "High"}] * 3
        + [{"area": "Viman Nagar", "category": "Parks and Public Spaces", "severity": "Low",
            "status": "SUBMITTED", "createdAt": pd.Timestamp.now(tz="UTC"), "resolvedAt": None,
            "affectedUsers": 1, "supportCount": 0, "locationSensitivity": "Low"}] * 2
    )
    df = _scored_df(rows)
    result = hotspot_analysis.analyze_hotspots(df)
    entry = next(a for a in result["byArea"] if a["area"] == "Viman Nagar")
    assert entry["highPriorityCount"] == 3
    assert entry["complaintCount"] == 5


def test_top_areas_by_high_priority_can_differ_from_top_by_count():
    rows = (
        # Area A: many complaints, all low priority.
        [{"area": "AreaA", "category": "Parks and Public Spaces", "severity": "Low",
          "status": "SUBMITTED", "createdAt": pd.Timestamp.now(tz="UTC"), "resolvedAt": None,
          "affectedUsers": 1, "supportCount": 0, "locationSensitivity": "Low"}] * 10
        # Area B: fewer complaints, but all critical.
        + [{"area": "AreaB", "category": "Public Safety", "severity": "Critical",
            "status": "SUBMITTED", "createdAt": pd.Timestamp.now(tz="UTC"), "resolvedAt": None,
            "affectedUsers": 200, "supportCount": 30, "locationSensitivity": "High"}] * 3
    )
    df = _scored_df(rows)
    result = hotspot_analysis.analyze_hotspots(df)
    assert result["topAreasByCount"][0] == "AreaA"
    assert result["topAreasByHighPriority"][0] == "AreaB"


def test_no_geospatial_clustering_note_present():
    rows = [{"area": "Kothrud", "category": "Road Infrastructure", "severity": "Medium",
             "status": "SUBMITTED", "createdAt": pd.Timestamp.now(tz="UTC"), "resolvedAt": None,
             "affectedUsers": 10, "supportCount": 0, "locationSensitivity": "Medium"}]
    df = _scored_df(rows)
    result = hotspot_analysis.analyze_hotspots(df)
    assert "geospatialClusteringNote" in result
    assert "not implemented" in result["geospatialClusteringNote"].lower()
