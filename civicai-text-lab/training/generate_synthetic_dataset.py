"""
Generates a SYNTHETIC, TEMPLATE-BASED labelled dataset for training/evaluating
this project's category/severity/department classifiers.

HONESTY NOTE (read before trusting any accuracy number this produces): this
is not real-world complaint data — no such dataset was available to this
project. category/department are template-driven and will be easy for a
model to separate near-perfectly; that reflects the dataset's own design, not
a real-world claim about how well any model classifies genuine free-text
complaints. severity is deliberately given LESS clean textual signal (shared
vocabulary across categories, plus intentional label noise — see
_maybe_mismatch_severity_phrase below) so its measured accuracy is an honest,
non-trivial number, not an artifact of trivial separability. This mirrors
the same honest-evaluation discipline used elsewhere in this project's
sibling repositories, reasoned independently for this one.

Run:
    python training/generate_synthetic_dataset.py
Writes data/raw/complaints.csv.
"""
import csv
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.schemas.analysis_schema import CATEGORY_DEPARTMENT_MAP, ComplaintCategory, SeverityLevel

RANDOM_SEED = 7
SAMPLES_PER_CATEGORY = 160
LABEL_NOISE_RATE = 0.20  # fraction of samples whose severity PHRASE deliberately doesn't match its label

_LOCATIONS = [
    "near the college gate", "on Main Street", "in front of the hospital", "outside the market",
    "near the railway station", "in the residential colony", "close to the school",
    "at the highway junction", "in front of the community hall", "near the bus stop",
    "behind the shopping complex", "on the ring road", "next to the temple", "in sector 12",
]

_ISSUE_TEMPLATES: Dict[str, List[str]] = {
    ComplaintCategory.ROAD_INFRASTRUCTURE.value: [
        "There is a large pothole {loc} that has damaged several vehicles.",
        "The road surface {loc} is completely broken and full of cracks.",
        "A deep crater has formed in the asphalt {loc}.",
        "The pavement {loc} has caved in and is unsafe to walk on.",
        "Loose gravel and broken tar cover the road {loc}.",
    ],
    ComplaintCategory.WASTE_MANAGEMENT.value: [
        "Garbage has been piling up {loc} for days without collection.",
        "The waste bin {loc} is overflowing and attracting stray animals.",
        "Trash is scattered all over the street {loc}.",
        "There is a foul smell of rotting waste {loc}.",
        "Household garbage is dumped illegally {loc}.",
    ],
    ComplaintCategory.WATER_SUPPLY.value: [
        "There has been no water supply {loc} for several days.",
        "A water pipeline has burst {loc}, flooding the street.",
        "Residents {loc} are getting extremely low water pressure.",
        "Clean drinking water is leaking continuously from a broken pipe {loc}.",
        "The water tank {loc} has not been refilled in a week.",
    ],
    ComplaintCategory.DRAINAGE_AND_SEWAGE.value: [
        "The drainage {loc} is completely blocked and overflowing.",
        "Sewage water is flowing openly onto the street {loc}.",
        "A manhole {loc} has been left open and uncovered.",
        "Stagnant drain water {loc} is breeding mosquitoes.",
        "The gutter {loc} has not been cleaned in months.",
    ],
    ComplaintCategory.STREET_LIGHTING.value: [
        "The street light {loc} has not worked for over two weeks.",
        "It is completely dark {loc} at night due to a fused bulb.",
        "Several lamp posts {loc} are non-functional.",
        "The area {loc} has no street lighting after sunset.",
        "A street light pole {loc} is flickering and about to fail.",
    ],
    ComplaintCategory.PUBLIC_SAFETY.value: [
        "There have been incidents of harassment reported {loc}.",
        "An exposed live wire {loc} is posing a serious danger to pedestrians.",
        "A group of people loitering {loc} is making residents feel unsafe.",
        "There was an attempted theft reported {loc} last night.",
        "A dangerous open construction pit {loc} has no barricade.",
    ],
    ComplaintCategory.PARKS_AND_PUBLIC_SPACES.value: [
        "The park bench {loc} is broken and needs replacement.",
        "Overgrown grass in the garden {loc} needs to be trimmed.",
        "A tree has fallen inside the park {loc}.",
        "The playground equipment {loc} is rusted and unsafe for children.",
        "The public garden {loc} has not been maintained in a long time.",
    ],
    ComplaintCategory.TRAFFIC_AND_PARKING.value: [
        "The traffic signal {loc} has not been working for days.",
        "Illegal parking {loc} is blocking the road for other vehicles.",
        "There is heavy traffic congestion {loc} every morning.",
        "Vehicles are parked haphazardly {loc}, blocking pedestrian paths.",
        "The traffic light {loc} is stuck on red for an unusually long time.",
    ],
    ComplaintCategory.ELECTRICITY.value: [
        "There has been a power outage {loc} since yesterday.",
        "A transformer {loc} is making loud sparking noises.",
        "Residents {loc} experienced an electric shock from a faulty pole.",
        "Frequent power cuts are affecting the whole area {loc}.",
        "An exposed electrical wire is hanging dangerously {loc}.",
    ],
    ComplaintCategory.OTHER.value: [
        "There is a general maintenance issue {loc} that needs attention.",
        "Residents {loc} have raised a concern about civic upkeep.",
        "An unspecified public infrastructure problem exists {loc}.",
        "A minor civic issue was noticed {loc}.",
        "Something needs to be looked at {loc} by the concerned department.",
    ],
}

_SEVERITY_PHRASES: Dict[str, List[str]] = {
    SeverityLevel.CRITICAL.value: [
        "This is extremely dangerous and needs immediate action.",
        "Someone could get seriously hurt if this is not fixed right away.",
        "This is an emergency situation that cannot wait.",
    ],
    SeverityLevel.HIGH.value: [
        "This has been a serious problem for over a week now.",
        "Many residents are affected and are getting frustrated.",
        "This urgently needs to be fixed as soon as possible.",
    ],
    SeverityLevel.MEDIUM.value: [
        "This has been going on for a few days.",
        "It is causing some inconvenience to people passing by.",
        "Please look into this soon.",
    ],
    SeverityLevel.LOW.value: [
        "This is a minor issue but should still be noted.",
        "Not urgent, but worth fixing eventually.",
        "A small inconvenience for residents in the area.",
    ],
}

# A per-category tendency (not a guarantee) toward certain severities - real
# civic complaint categories do skew this way in practice (a public-safety
# report skews more severe than a park-bench report), while still allowing
# every severity to appear in every category.
_CATEGORY_SEVERITY_WEIGHTS: Dict[str, Dict[str, float]] = {
    ComplaintCategory.PUBLIC_SAFETY.value: {"Critical": 0.45, "High": 0.35, "Medium": 0.15, "Low": 0.05},
    ComplaintCategory.ELECTRICITY.value: {"Critical": 0.25, "High": 0.40, "Medium": 0.25, "Low": 0.10},
    ComplaintCategory.WATER_SUPPLY.value: {"Critical": 0.10, "High": 0.40, "Medium": 0.35, "Low": 0.15},
    ComplaintCategory.DRAINAGE_AND_SEWAGE.value: {"Critical": 0.10, "High": 0.35, "Medium": 0.35, "Low": 0.20},
    ComplaintCategory.ROAD_INFRASTRUCTURE.value: {"Critical": 0.10, "High": 0.35, "Medium": 0.35, "Low": 0.20},
    ComplaintCategory.STREET_LIGHTING.value: {"Critical": 0.05, "High": 0.25, "Medium": 0.40, "Low": 0.30},
    ComplaintCategory.TRAFFIC_AND_PARKING.value: {"Critical": 0.05, "High": 0.25, "Medium": 0.40, "Low": 0.30},
    ComplaintCategory.WASTE_MANAGEMENT.value: {"Critical": 0.05, "High": 0.20, "Medium": 0.40, "Low": 0.35},
    ComplaintCategory.PARKS_AND_PUBLIC_SPACES.value: {"Critical": 0.02, "High": 0.13, "Medium": 0.35, "Low": 0.50},
    ComplaintCategory.OTHER.value: {"Critical": 0.05, "High": 0.20, "Medium": 0.40, "Low": 0.35},
}


def _weighted_choice(rng: random.Random, weights: Dict[str, float]) -> str:
    labels = list(weights.keys())
    cumulative = []
    total = 0.0
    for label in labels:
        total += weights[label]
        cumulative.append(total)
    r = rng.random() * total
    for label, threshold in zip(labels, cumulative):
        if r <= threshold:
            return label
    return labels[-1]


def _maybe_mismatch_severity_phrase(rng: random.Random, true_severity: str) -> str:
    """With LABEL_NOISE_RATE probability, use a phrase from a DIFFERENT
    severity than the true label — this is what keeps severity genuinely
    non-trivial to learn (real complaints are like this too: a "minor"
    complaint sometimes uses urgent-sounding language, and vice versa)."""
    if rng.random() < LABEL_NOISE_RATE:
        other = [s for s in _SEVERITY_PHRASES if s != true_severity]
        chosen_severity_for_phrase = rng.choice(other)
    else:
        chosen_severity_for_phrase = true_severity
    return rng.choice(_SEVERITY_PHRASES[chosen_severity_for_phrase])


def generate_rows(rng: random.Random) -> List[Tuple[str, str, str, str]]:
    """Returns rows of (text, category, severity, department)."""
    rows = []
    for category, templates in _ISSUE_TEMPLATES.items():
        department = CATEGORY_DEPARTMENT_MAP[ComplaintCategory(category)].value
        weights = _CATEGORY_SEVERITY_WEIGHTS[category]
        for _ in range(SAMPLES_PER_CATEGORY):
            template = rng.choice(templates)
            location = rng.choice(_LOCATIONS)
            issue_sentence = template.format(loc=location)

            severity = _weighted_choice(rng, weights)
            severity_sentence = _maybe_mismatch_severity_phrase(rng, severity)

            text = f"{issue_sentence} {severity_sentence}"
            rows.append((text, category, severity, department))
    rng.shuffle(rows)
    return rows


def main():
    rng = random.Random(RANDOM_SEED)
    rows = generate_rows(rng)

    raw_dir = Path(settings.RAW_DATA_DIR)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / "complaints.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "category", "severity", "department"])
        writer.writerows(rows)

    print(f"Generated {len(rows)} synthetic rows -> {out_path}")


if __name__ == "__main__":
    main()
