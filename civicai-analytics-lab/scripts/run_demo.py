"""
Quick CLI demo — runs the full analytics pipeline directly against the
bundled sample dataset (no server needed) and prints a human-readable
summary. Useful for a fast sanity check after regenerating the dataset.

Run:
    python scripts/run_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services import analytics_pipeline, data_service


def main():
    sample_path = Path(settings.SAMPLE_DATA_DIR) / settings.SAMPLE_DATASET_FILENAME
    if not sample_path.exists():
        print(f"Sample dataset not found at {sample_path}.")
        print("Run `python scripts/generate_dataset.py` first.")
        return

    df = data_service.load_csv(sample_path)
    result = analytics_pipeline.analyze_dataset(df)

    print(f"=== CivicAI Analytics Lab — demo run against {sample_path.name} ===\n")

    ds = result["dataset"]
    print(f"Records: {ds['totalRowsAfterFilters']} (of {ds['totalRowsBeforeFilters']} before filters)")
    print(f"Date range: {ds['dateRange']['earliest']} .. {ds['dateRange']['latest']}\n")

    impact = result["impact"]
    print("Impact:")
    for key, value in impact.items():
        print(f"  {key}: {value}")

    print("\nPriority:")
    print(f"  Average score: {result['priority']['averageScore']}")
    print(f"  Label distribution: {result['priority']['labelDistribution']}")

    print("\nMonthly trend:")
    monthly = result["trends"]["monthly"]
    print(f"  Direction: {monthly['trendDirection']} (change: {monthly['percentageChange']}%)")
    for bucket in monthly["buckets"]:
        print(f"    {bucket['period']}: {bucket['count']}")

    print("\nTop 5 hotspot areas (by complaint count):")
    for area in result["hotspots"]["topAreasByCount"]:
        entry = next(a for a in result["hotspots"]["byArea"] if a["area"] == area)
        print(f"  {area}: {entry['complaintCount']} complaints, dominant category = {entry['dominantCategory']}")

    print("\nDepartments (first 3):")
    for name, metrics in list(result["departments"].items())[:3]:
        print(f"  {name}: {metrics}")

    print("\nDone. Full JSON is available via POST /api/analyze once `python run.py` is running.")


if __name__ == "__main__":
    main()
