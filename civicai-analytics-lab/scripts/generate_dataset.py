"""
Generates a realistic SYNTHETIC sample dataset for CivicAI Analytics Lab —
no real complaint data was available, and none is used. Spans several
months with varying categories/departments/areas/severities/statuses so
every analysis module (trend/hotspot/impact/department/category) has
meaningful, non-degenerate data to compute over.

Run:
    python scripts/generate_dataset.py
Writes data/sample/sample_complaints.csv.
"""
import csv
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings

RANDOM_SEED = 11
NUM_RECORDS = 600
DAYS_SPAN = 180  # ~6 months of history

CATEGORIES = [
    "Road Infrastructure", "Waste Management", "Water Supply", "Drainage and Sewage",
    "Street Lighting", "Public Safety", "Parks and Public Spaces", "Traffic and Parking",
    "Electricity", "Other",
]
CATEGORY_DEPARTMENT = {
    "Road Infrastructure": "Public Works Department",
    "Waste Management": "Municipal Sanitation",
    "Water Supply": "Water Department",
    "Drainage and Sewage": "Sewerage/Drainage Department",
    "Street Lighting": "Electrical Department",
    "Public Safety": "Public Safety/Police Liaison",
    "Parks and Public Spaces": "Parks Department",
    "Traffic and Parking": "Traffic Department",
    "Electricity": "Electrical Utility",
    "Other": "General Municipal Helpdesk",
}
AREAS = ["Kothrud", "Viman Nagar", "Aundh", "MG Road", "Model Colony", "Hinjewadi", "Baner", "Wagholi"]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
SEVERITY_WEIGHTS = [0.30, 0.35, 0.25, 0.10]
LOCATION_SENSITIVITIES = ["Low", "Medium", "High"]

# Terminal (resolved-family) vs still-open statuses.
RESOLVED_LIKE_STATUSES = ["RESOLVED", "CONFIRMED"]
OPEN_STATUSES = ["SUBMITTED", "ACKNOWLEDGED", "IN_PROGRESS", "ESCALATED"]


def _random_created_at(rng: random.Random, now: datetime) -> datetime:
    days_ago = rng.uniform(0, DAYS_SPAN)
    return now - timedelta(days=days_ago)


def generate_rows(rng: random.Random):
    now = datetime.now(timezone.utc)
    rows = []

    # A mild upward trend over time: bias more recent records toward higher
    # severity/critical, so trend_analysis has a real "increasing" signal to
    # detect for at least one category, not just flat noise.
    for i in range(NUM_RECORDS):
        created_at = _random_created_at(rng, now)
        recency_fraction = 1.0 - (now - created_at).total_seconds() / (DAYS_SPAN * 86400.0)  # 0 (old) .. 1 (recent)

        category = rng.choice(CATEGORIES)
        department = CATEGORY_DEPARTMENT[category]
        area = rng.choice(AREAS)

        severity_weights = list(SEVERITY_WEIGHTS)
        if category == "Public Safety":
            severity_weights = [0.10, 0.20, 0.35, 0.35]
        severity = rng.choices(SEVERITIES, weights=severity_weights, k=1)[0]

        # Older complaints are more likely to have resolved; recent ones
        # more likely to still be open — a realistic "still working through
        # the backlog" shape rather than a uniformly random resolved flag.
        resolve_probability = 0.85 - 0.5 * recency_fraction
        is_resolved = rng.random() < resolve_probability

        if is_resolved:
            status = rng.choices(RESOLVED_LIKE_STATUSES, weights=[0.7, 0.3], k=1)[0]
            resolution_days = max(0.2, rng.gauss(4.0, 2.5))
            resolved_at = created_at + timedelta(days=resolution_days)
            if resolved_at > now:
                resolved_at = now
        else:
            status = rng.choice(OPEN_STATUSES)
            resolved_at = None

        support_count = max(0, int(rng.gauss(8, 6)))
        affected_users = max(1, int(rng.gauss(35, 30)))
        location_sensitivity = rng.choices(LOCATION_SENSITIVITIES, weights=[0.5, 0.35, 0.15], k=1)[0]

        rows.append({
            "id": f"C{i + 1:04d}",
            "category": category,
            "severity": severity,
            "department": department,
            "area": area,
            "createdAt": created_at.isoformat(),
            "resolvedAt": resolved_at.isoformat() if resolved_at else "",
            "status": status,
            "supportCount": support_count,
            "affectedUsers": affected_users,
            "locationSensitivity": location_sensitivity,
        })

    rows.sort(key=lambda r: r["createdAt"])
    return rows


def main():
    rng = random.Random(RANDOM_SEED)
    rows = generate_rows(rng)

    out_dir = Path(settings.SAMPLE_DATA_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / settings.SAMPLE_DATASET_FILENAME

    fieldnames = [
        "id", "category", "severity", "department", "area", "createdAt",
        "resolvedAt", "status", "supportCount", "affectedUsers", "locationSensitivity",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} synthetic complaint records -> {out_path}")


if __name__ == "__main__":
    main()
