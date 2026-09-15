# CivicAI Analytics Lab

> **⚠️ This is an ISOLATED PROTOTYPE. It is NOT connected to, NOT mounted
> inside, and NOT a dependency of the running production CivicAI application
> (`YOUR_PROJECT/`). It does not import any production code, does not
> connect to MongoDB, does not use production authentication, and does not
> touch production users or complaints. It operates ONLY on local CSV/JSON
> data (a bundled synthetic sample dataset, or a file you upload) and is
> read-only analytics — it never writes to a database and never changes a
> complaint's status.**

## What this is

A standalone FastAPI service that takes a batch of complaint records (CSV or
JSON) and produces deterministic analytics: priority scoring, time-based
trends, area-level hotspots, and impact/department/category breakdowns. No
machine learning — every number here is a documented, reproducible
Python/pandas/numpy calculation.

## What this explicitly is NOT

- **Not** ML. No model, no training, no `predict()` anywhere in this project.
- **Not** claiming compatibility with the production priority formula. The
  priority scoring here is independently designed for this prototype — see
  "Priority formula" below for the explicit disclaimer, repeated in the code
  itself and in every API response's `explanation` field.
- **Not** a database. Every run reads a CSV, computes in memory, and returns
  JSON. Nothing persists between requests except the files you explicitly
  point it at.
- **Not** connected to MongoDB, production auth, or any production data.
- **Not** fabricating a value it can't compute — a metric with no valid
  input (e.g. average resolution days when nothing is resolved) is reported
  as `null`, never as `0` and never silently omitted.

## Architecture

```
civicai-analytics-lab/
├── app/
│   ├── main.py                    # Standalone FastAPI app
│   ├── config.py                  # This project's OWN settings — no shared config
│   ├── api/routes.py                # GET /api/health, POST /api/analyze, POST /api/analyze/upload
│   ├── services/
│   │   ├── data_service.py          # CSV loading, validation, normalization, documented defaults
│   │   ├── priority_analysis.py      # calculate_priority() — deterministic, explainable scoring
│   │   ├── trend_analysis.py         # daily/weekly/monthly counts, trend direction, category trends
│   │   ├── hotspot_analysis.py       # area-level rollups (no geospatial clustering — see below)
│   │   ├── impact_analysis.py        # impact + department + category analysis
│   │   └── analytics_pipeline.py     # analyze_dataset() — the one orchestrator every route calls
│   └── schemas/analytics_schema.py  # Data model + request/response schemas
├── data/
│   ├── raw/, processed/             # Scratch space for your own datasets
│   ├── sample/sample_complaints.csv # Bundled synthetic dataset (600 rows, ~6 months)
│   └── outputs/
├── scripts/
│   ├── generate_dataset.py          # Regenerates data/sample/sample_complaints.csv
│   └── run_demo.py                  # CLI pipeline run, no server needed
├── notebooks/analytics_exploration.ipynb
├── tests/                           # 72 pytest tests
└── requirements.txt / .env.example / .gitignore / run.py
```

## Running it

```bash
cd civicai-analytics-lab
python3 -m venv .venv
source .venv/bin/activate      # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env           # optional — sensible defaults work out of the box
python scripts/generate_dataset.py   # regenerates the bundled sample dataset (already included)

python run.py                  # starts on http://127.0.0.1:8003 (NOT 8000/8001/8002)
```

Swagger UI: **http://localhost:8003/docs**

### Trying it

```bash
# Health check
curl http://127.0.0.1:8003/api/health

# Analyze the bundled sample dataset
curl -X POST http://127.0.0.1:8003/api/analyze -H "Content-Type: application/json" -d '{}'

# ...with filters
curl -X POST http://127.0.0.1:8003/api/analyze -H "Content-Type: application/json" \
  -d '{"filters": {"category": "Road Infrastructure", "area": "Kothrud"}}'

# Upload your own CSV
curl -X POST http://127.0.0.1:8003/api/analyze/upload -F "file=@my_complaints.csv"
```

### Running the tests

```bash
python -m pytest tests/ -v
```

## Data model

| Column | Required? | Type | Notes |
|---|---|---|---|
| `id` | **Required** | string | Must be non-empty and unique across the dataset |
| `category` | **Required** | string | Free text |
| `severity` | **Required** | enum | `Low` \| `Medium` \| `High` \| `Critical` |
| `department` | **Required** | string | Free text |
| `area` | **Required** | string | Free text — the only geographic field (see "Hotspot analysis" below) |
| `createdAt` | **Required** | date/datetime | Any format `pandas.to_datetime` can parse (mixed formats within one column are handled — see "A real bug we found" below) |
| `status` | **Required** | enum | `SUBMITTED` \| `ACKNOWLEDGED` \| `IN_PROGRESS` \| `RESOLVED` \| `CONFIRMED` \| `REJECTED` \| `ESCALATED` |
| `resolvedAt` | Optional | date/datetime | **Default if missing/blank: `null`** (not yet resolved) |
| `supportCount` | Optional | integer ≥ 0 | **Default if missing: `0`** |
| `affectedUsers` | Optional | integer ≥ 0 | **Default if missing: `10`** |
| `locationSensitivity` | Optional | enum | `Low` \| `Medium` \| `High` — **default if missing: `Medium`** |

**Validation discipline:** a REQUIRED field that's missing/invalid on even
one row rejects the WHOLE dataset with a specific error naming the column
and the exact row index/indices — it is never silently dropped. An OPTIONAL
field that's genuinely missing gets the default above; an optional field
that's PRESENT but garbled (e.g. `supportCount: "abc"`, a negative
`affectedUsers`, an unparseable non-blank `resolvedAt`, or a `resolvedAt`
before its own `createdAt`) is also rejected with a specific error — a
garbled value is a real data-quality problem, not something to silently
paper over with a default.

## Analytical formulas & assumptions

### Priority formula — ⚠️ NOT verified against production

```
priorityScore = 0.40 × severityScore
              + 0.20 × affectedUsersScore
              + 0.15 × supportCountScore
              + 0.15 × locationSensitivityScore
              + 0.10 × durationScore
```

- `severityScore`: Low=25, Medium=50, High=75, Critical=100
- `affectedUsersScore`: `min(100, affectedUsers × 1.5)`
- `supportCountScore`: `min(100, supportCount × 5)`
- `locationSensitivityScore`: Low=25, Medium=50, High=100
- `durationScore`: `min(100, hours / 168 × 100)` (168h = 7 days reaches the max) — **for an already-resolved
  complaint, "hours" is how long it stayed open (`resolvedAt − createdAt`)**, the historically meaningful
  number when analyzing a batch of past records; for a still-open complaint, it's time since `createdAt`
  as of now.

Thresholds: **≥75 → Critical, ≥50 → High, ≥25 → Medium, <25 → Low.**

**This formula's signals and weights are independently designed for this
analytics prototype.** They were chosen as a reasonable, common-sense
default for this domain — they are **not copied from, and have not been
verified against**, the production project's `priority_service.py` (which
this project never imports, reads at runtime, or calls). Every single
`calculate_priority()` response repeats this disclaimer in its own
`explanation` field, so it can never be mistaken for a verified match even
by someone who only sees the API output and never reads this README.

### Trend analysis

Buckets complaint counts by `createdAt` into daily / weekly / monthly
periods (`pandas.resample`). Trend direction is deterministic:

1. Split the period-bucket series into a first half and second half (by
   bucket count).
2. Compare each half's average count.
3. `percentageChange >= +10%` → `"increasing"`; `<= -10%` → `"decreasing"`;
   otherwise → `"stable"`.
4. Fewer than 2 buckets → `"insufficient_data"`.
5. A first-half average of exactly zero makes a percentage undefined
   (division by zero) — reported as `percentageChange: null`, never a
   fabricated number, even when a direction (`"increasing"` from zero) can
   still be reasoned about.

Category trends use the exact same rule, applied to each category's own
count series independently (monthly granularity, the least noisy for a
per-category breakdown at typical dataset sizes).

### Hotspot (area) analysis

Per area: complaint count, high-priority count (`priorityLabel` in `High`/`Critical`),
dominant category (statistical mode), and average priority score. Top areas
are reported two ways — by raw count and by high-priority count — since
these can genuinely differ (a high-volume area of minor issues vs. a
lower-volume area of serious ones).

**No geospatial clustering is implemented.** This data model has no
latitude/longitude fields at all — only a free-text `area` name — so per
the task's own conditional instruction ("do NOT implement complex
geospatial clustering unless the dataset actually contains coordinates"),
only area-name-based aggregation exists here.

### Impact analysis

`totalComplaints`, `totalAffectedUsers` (real sum), `averageAffectedUsers`,
`highPriorityCount`, `criticalCount`, `resolvedCount`/`unresolvedCount`
(by `status`), `resolutionRatePercentage`. Resolution-day statistics
(`averageResolutionDays`, `medianResolutionDays`, `fastestResolutionDays`,
`slowestResolutionDays`) are computed **only** over rows that are both
status-resolved AND have a real `resolvedAt` — if zero rows qualify, every
one of these four is `null`, never `0` and never omitted.

### Department / category analysis

The same impact-style metrics (count, high-priority count, resolved/
unresolved, resolution rate, average resolution days), grouped by
`department` and by `category` respectively. Category analysis additionally
reports `percentage` (share of the filtered dataset) and `trend` (pulled
from the trend-analysis module's own per-category computation — never a
second, divergent trend calculation).

## A real bug we found and fixed while building this (disclosed, not hidden)

`pandas.to_datetime()` infers **one** format from a column and silently
returns `NaT` for any row in a different — but still perfectly valid —
format (e.g. a column mixing `"...Z"` and `"...+00:00"` timestamps). Our
first implementation hit this directly during test-writing: a dataset with
genuinely mixed-but-valid date formats was incorrectly rejected as
"unparseable." Fixed by using `format="mixed"`, which parses each value
independently. A second, related bug — assigning a bare `pd.NaT` scalar to
create a missing `resolvedAt` column produces a *naive* datetime dtype,
which then raises a real `TypeError` the moment it's compared against the
*timezone-aware* `createdAt` column — was fixed by constructing that default
column through the same `pd.to_datetime(..., utc=True)` path instead. Both
are covered by dedicated regression tests in `tests/test_data_service.py`.

## Future integration: a single production adapter

This project's public surface is intentionally narrow — one function:

```python
analytics_pipeline.analyze_dataset(records, filters=None) -> dict
```

returning exactly the schema documented above. To connect this to the
production CivicAI backend *later* (not done here, not started here), the
shape of that work would be:

1. **Never point this at MongoDB directly.** The correct integration is a
   production-side export step: a new, separate production endpoint or
   scheduled job that dumps complaints to CSV/JSON in this project's exact
   column shape (`id, category, severity, department, area, createdAt,
   resolvedAt, status, supportCount, affectedUsers, locationSensitivity`),
   then hands that file to this service — this project remains database-free
   even when "integrated."
2. Add one new adapter module to the production backend, e.g.
   `app/services/analytics_adapter.py`, that either:
   - **(a) calls this service over HTTP** (if run as a sidecar process) — a
     thin `httpx` call to `http://localhost:8003/api/analyze/upload` with the
     exported file attached, or
   - **(b) vendors this project's pure functions directly** (`data_service.py`,
     `priority_analysis.py`, `trend_analysis.py`, `hotspot_analysis.py`,
     `impact_analysis.py`, `analytics_pipeline.py` have zero web-framework
     dependency in their logic — only `app/api/routes.py` and `app/main.py`
     touch FastAPI at all) as a new internal analytics package.
3. **Before any claim of formula compatibility**, run this project's
   `priority_analysis.calculate_priority()` and production's
   `priority_service.calculate_priority_score()` side-by-side against the
   same real records and compare outputs directly — never assume similarity
   from a similar-looking weight split, which is all that exists today.
4. This integration step itself — building the export job, writing the
   adapter, and verifying (or reconciling) formula compatibility — is a
   deliberate, separate piece of work, not attempted as part of building
   this standalone prototype.

## Isolation guarantees

- No file in this directory imports from, or is imported by, the production
  `YOUR_PROJECT/backend/` code.
- No MongoDB client, connection string, or dependency exists anywhere here.
- No authentication, no user model, no session/token handling exists here.
- No call to any production API, anywhere.
- Runs on port **8003** by default — production's port (8000),
  `civicai-vision-lab`'s (8001), and `civicai-text-lab`'s (8002) are never touched.
- `priority_analysis.py` is an independent reimplementation, explicitly
  disclaimed as unverified against production — see above.
