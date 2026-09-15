# CivicAI Text Intelligence Lab

> **⚠️ This is an ISOLATED PROTOTYPE. It is NOT connected to, NOT mounted
> inside, and NOT a dependency of the running production CivicAI application
> (`YOUR_PROJECT/`). It does not import any production code, does not
> connect to MongoDB, does not use production authentication, and does not
> touch production users, complaints, or media storage. It is a standalone
> sandbox for prototyping a future complaint-text classification module,
> built to run entirely on its own.**

## What this is

A standalone FastAPI service that takes complaint text and produces a
structured classification: category, severity, department, an affected-users
estimate, location sensitivity, a plain-English reason, and — critically — an
honest confidence signal that tells the caller whether to trust the result.

- **TF-IDF + Logistic Regression** — three independently trained classifier
  heads (category, severity, department), no deep learning.
- **Real `predict_proba()` confidence** — never fabricated. When the weakest
  head's confidence is below a threshold, the pipeline discards the ML
  result entirely and uses a **deterministic rule-based fallback** instead.
- **Trained on an honestly-labelled synthetic dataset** (see
  `training/generate_synthetic_dataset.py`) — no real-world data was
  available, and this is stated plainly rather than implied otherwise.

## What this explicitly is NOT

- **Not** deep learning. TF-IDF + Logistic Regression only, per the brief.
- **Not** fabricating confidence, ever. `confidence` is `null` on every
  rule-fallback response, by contract, checked by its own test
  (`test_no_fabricated_confidence_anywhere_on_the_fallback_path`).
- **Not** connected to MongoDB, production auth, or any production data.
- **Not** claiming a performance number that wasn't actually measured — see
  "Honest evaluation" below.

## Architecture

```
civicai-text-lab/
├── app/
│   ├── main.py                      # Standalone FastAPI app
│   ├── config.py                    # This project's OWN settings — no shared config
│   ├── api/routes.py                 # POST /api/analyze, /api/analyze/batch, GET /api/status
│   ├── services/
│   │   ├── preprocessing_service.py   # Safe text normalization
│   │   ├── classifier_service.py      # ML adapter (lazy-loaded, honest states)
│   │   ├── confidence_service.py      # Confidence gating (reads, never invents, predict_proba values)
│   │   ├── rule_fallback_service.py   # Deterministic keyword classifier — always available
│   │   └── analysis_service.py        # Orchestrates all of the above into one result
│   └── schemas/analysis_schema.py    # Taxonomy + request/response schemas
├── data/
│   ├── raw/complaints.csv            # Synthetic labelled dataset (generated, not hand-collected)
│   ├── processed/{train,val,test}.csv
│   └── sample_cases/                 # A few example requests for manual testing
├── models/trained/                   # vectorizer.pkl, {category,severity,department}_model.pkl, metadata.json
├── training/
│   ├── generate_synthetic_dataset.py # Produces data/raw/complaints.csv
│   ├── split_dataset.py              # Validates + stratified train/val/test split, leak-checked
│   ├── train.py                      # Trains and saves the model artifacts
│   └── evaluate.py                   # Reports REAL metrics from the held-out test split
├── tests/                            # 51 pytest tests
├── requirements.txt / .env.example / .gitignore
└── run.py
```

## Running it

```bash
cd civicai-text-lab
python3 -m venv .venv
source .venv/bin/activate      # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env           # optional — sensible defaults work out of the box

python run.py                  # starts on http://127.0.0.1:8002 (NOT 8000 or 8001)
```

Swagger UI: **http://localhost:8002/docs**

### Re-running the training pipeline yourself

```bash
python training/generate_synthetic_dataset.py   # -> data/raw/complaints.csv
python training/split_dataset.py                # -> data/processed/{train,val,test}.csv (leak-checked)
python training/train.py                        # -> models/trained/*.pkl + metadata.json
python training/evaluate.py                     # -> real metrics from the test split (never trained on)
```

### Trying the API

```bash
curl -X POST http://127.0.0.1:8002/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "There is a large pothole near the college gate."}'
```

```bash
curl -X POST http://127.0.0.1:8002/api/analyze/batch \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Garbage overflow near the market.", "please help"]}'
```

### Running the tests

```bash
python -m pytest tests/ -v
```

## Response shape

```json
{
  "category": "Road Infrastructure",
  "severity": "High",
  "department": "Public Works Department",
  "affectedUsersEstimate": 60,
  "locationSensitivity": "High",
  "reason": "Trained ML classifier prediction (confidence: category=0.625, severity=0.7921, department=0.625).",
  "confidence": 0.625,
  "source": "ml",
  "needsReview": false,
  "modelVersion": "textlab-tfidf-logreg-20260915141210"
}
```

When the ML tier isn't used (unavailable, failed, or low confidence):

```json
{
  "category": "Road Infrastructure",
  "severity": "High",
  "department": "Public Works Department",
  "affectedUsersEstimate": 60,
  "locationSensitivity": "High",
  "reason": "Road surface defect detected — likely to affect vehicle and pedestrian safety.",
  "confidence": null,
  "source": "rule_fallback",
  "needsReview": true,
  "modelVersion": "rule-fallback-v1"
}
```

## Honest evaluation (measured, not claimed)

Real numbers from `training/evaluate.py`, run against `data/processed/test.csv`
— a split the model has never been trained or tuned on:

| Head | Accuracy | Macro F1 |
|---|---|---|
| category | 1.0 | 1.0 |
| severity | 0.777 | 0.755 |
| department | 1.0 | 1.0 |

**Why category/department are ~perfect, honestly:** this project's training
data is synthetic and template-generated (`training/generate_synthetic_dataset.py`)
— no real-world complaint dataset was available. category and department are
template-driven and trivially separable by construction. This is **not** a
real-world performance claim.

**Why severity is the more informative number:** the dataset generator
deliberately injects label noise (~20% of samples use a severity-indicating
phrase that does *not* match the row's actual severity label) and reuses the
same phrases across categories, so a model can't just memorize
category↔severity co-occurrence. 0.777 is a real, measured, non-trivial
result — not inflated, not deflated.

**A real, observed model characteristic, disclosed rather than hidden:**
text phrased close to the training templates gets confidently classified
(≥0.6 confidence); a paraphrase using the same real-world vocabulary but
different sentence structure can score notably lower (confirmed directly:
one such rephrasing of a pothole complaint scored 0.17 on `category`). This
is exactly what the confidence-gating + rule-fallback mechanism exists to
catch safely — a genuinely low `predict_proba()` value correctly triggers
`needsReview`/`rule_fallback` rather than a falsely-confident answer.
Expanding the training set's phrasing diversity is the direct fix, and is
listed under "What remains before production integration" below.

## The rule fallback

Always available, never depends on a trained model, never fails. Matches
complaint text against a fixed keyword table (pothole → Road Infrastructure,
garbage → Waste Management, assault/unsafe → Public Safety at Critical
severity, etc.), with one context rule: any Medium-severity match becomes
High if the text mentions a sensitive location (school, hospital, market...).

Used whenever:
- the ML classifier is unavailable (no trained model present), **or**
- the ML classifier's model files fail to load, **or**
- the ML prediction's weakest head confidence is below `CONFIDENCE_THRESHOLD`
  (default 0.45).

In every one of those cases: `confidence` is `null`, `source` is
`"rule_fallback"`, `needsReview` is `true` — never a mix of the two.

## What remains before production integration

1. **A real, non-synthetic labelled dataset.** This is the single highest-
   leverage next step — everything else here (the training pipeline, the
   confidence gating, the fallback, the API) is already real and working;
   only the training *data* is synthetic.
2. **Broader phrasing diversity in training data** — the observed
   in-template-vs-paraphrase confidence gap (see "Honest evaluation" above)
   would shrink significantly with more varied real-world phrasing per
   category.
3. **A decision on how this module's interface gets called from — or has its
   logic ported into — the production project's `ai_service.py`/`ml_service.py`.**
   Not started here. See "Integration path" below for the shape that
   decision would take.
4. **Re-running this project's own test suite and `training/evaluate.py`**
   against that real dataset before trusting any number from it.

## Integration path: a single adapter

This project's public surface is intentionally narrow — one function:

```python
analysis_service.analyze_text(raw_text: str) -> dict
```

returning exactly the schema in `app/schemas/analysis_schema.py`. To
integrate this into the production CivicAI backend *later* (not done here,
not started here), the shape of that work would be:

1. Add one new adapter module to the production backend, e.g.
   `app/services/text_intelligence_adapter.py`, that either:
   - **(a) calls this service over HTTP** (if run as a sidecar process) — a
     thin `httpx` call to `http://localhost:8002/api/analyze`, mapping this
     project's response fields onto the production `AIAnalysisResult` shape
     (they're deliberately similar for exactly this reason), or
   - **(b) vendors this project's trained artifacts** (`vectorizer.pkl` +
     the three `*_model.pkl` files + `metadata.json`) into the production
     `ml_service.py`'s own model directory, if the taxonomy is reconciled
     with production's `app/schemas/enums.py` first (they're independently
     defined and not guaranteed identical, even though they resemble each
     other on purpose).
2. Either way, the production `ai_service.py`'s existing 3-tier cascade
   (hosted LLM → trained ML → rule-based fallback) is the natural place this
   plugs in — as an *additional or replacement* tier 2, never bypassing the
   production project's own confidence-gating and fallback discipline, which
   this prototype was deliberately built to match in spirit.
3. This integration step itself — writing that adapter, reconciling the two
   taxonomies, and deciding (a) vs (b) — is a deliberate, separate piece of
   work, not attempted as part of building this standalone prototype.

## Isolation guarantees

- No file in this directory imports from, or is imported by, the production
  `YOUR_PROJECT/backend/` code.
- No MongoDB client, connection string, or dependency exists anywhere here.
- No authentication, no user model, no session/token handling exists here.
- Runs on port **8002** by default — production's port (8000) and
  `civicai-vision-lab`'s port (8001) are never touched.
- `rule_fallback_service.py` and the taxonomy in `analysis_schema.py` are
  independent reimplementations written from scratch for this
  prototype — they do not import the production project's
  `ai_service.py`/`ml_service.py`/`enums.py`.
