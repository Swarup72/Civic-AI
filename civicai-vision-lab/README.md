# CivicAI Vision Lab

> **⚠️ This is an ISOLATED PROTOTYPE. It is NOT connected to, NOT mounted
> inside, and NOT a dependency of the running production CivicAI application
> (`YOUR_PROJECT/`). It does not import any production code, does not
> connect to MongoDB, does not use production authentication, and does not
> touch production users, complaints, or media storage. It is a standalone
> sandbox for prototyping a future Vision AI + Evidence Verification module,
> built to run entirely on its own.**

## What this is

A standalone FastAPI service that takes a "before" and "after" photo of a
civic complaint (e.g. a pothole) and produces a structured **evidence
assessment**: is this the same location, does it look repaired, and how good
are the photos themselves. It combines:

- **Classical computer vision** (ORB + RANSAC) to check the before/after
  photos show the same physical location.
- **Image-quality checks** (resolution, blur, brightness, corruption).
- **An optional, pluggable vision-model adapter** for image-CONTENT
  understanding ("does this look fixed") — ships with **no model**, and
  honestly reports itself unavailable until a real one is added.
- **A deterministic, explainable scoring function** that combines all of the
  above into one 0–100 `evidenceScore` and a plain-English breakdown.

## What this explicitly is NOT

- **Not** a machine-learning confidence score. `evidenceScore` is a rule-based,
  weighted business score built from four named signals (see below) — it is
  never computed from a raw model probability, and must never be presented,
  logged, or labeled as "AI confidence" anywhere.
- **Not** trained here. No model training code exists in this repository.
- **Not** auto-downloading anything. If `models/pretrained/` is empty (the
  shipped default), the vision adapter honestly reports `unavailable` — it
  never fetches a model over the network on its own.
- **Not** connected to MongoDB, production auth, or any production data.

## Architecture

```
civicai-vision-lab/
├── app/
│   ├── main.py                    # Standalone FastAPI app (own CORS, own routes)
│   ├── config.py                  # This project's OWN settings — no shared config
│   ├── api/routes.py               # POST /api/analyze, GET /api/status
│   ├── services/
│   │   ├── vision_service.py        # Pluggable image-content adapter (see below)
│   │   ├── scene_service.py         # ORB + RANSAC location-match (independent reimplementation)
│   │   ├── image_quality_service.py # Resolution / blur / brightness / corruption checks
│   │   ├── evidence_score_service.py# The core assess_evidence() scoring function
│   │   └── analysis_service.py      # Orchestrates the four services above
│   ├── models/schemas.py           # Pydantic response shapes
│   └── utils/image_utils.py        # Shared decode/read helpers
├── data/
│   ├── samples/{repaired,not_repaired,unclear,wrong_location}/  # Demo before/after pairs
│   └── outputs/                    # Uploaded images land here at request time
├── models/pretrained/              # Empty by default — see "Adding a real model" below
├── tests/                          # 39 pytest tests, one file per service + one pipeline file
├── requirements.txt
├── .env.example
└── run.py
```

## Running it

```bash
cd civicai-vision-lab
python3 -m venv .venv
source .venv/bin/activate      # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env           # optional — sensible defaults work out of the box

python run.py                  # starts on http://127.0.0.1:8001 (NOT 8000 — see .env.example)
```

Open `http://127.0.0.1:8001/docs` for interactive API docs.

### Try it with the bundled sample images

```bash
curl -X POST http://127.0.0.1:8001/api/analyze \
  -F "before_image=@data/samples/repaired/before.jpg" \
  -F "after_image=@data/samples/repaired/after.jpg"
```

The four sample folders (`repaired`, `not_repaired`, `unclear`,
`wrong_location`) each contain a synthetic-but-illustrative before/after
pair. Because no real vision model ships with this prototype, `repaired` and
`not_repaired` currently score identically (`inconclusive`) — this is
**correct, honest behavior**: without real image-content understanding, the
system has no basis to claim the damage was actually fixed, so it says so
rather than guessing. `wrong_location` correctly triggers a location
mismatch, and `unclear` correctly reports an ambiguous scene comparison.

### Running the tests

```bash
python -m pytest tests/ -v
```

## The core function: `assess_evidence()`

```python
from app.services.evidence_score_service import assess_evidence

result = assess_evidence(scene_result, before_result, after_result, quality_result)
```

Scoring (points, not percentages):

| Signal | Points | Source |
|---|---|---|
| Same location | 40 | `scene_service.compare_scenes()` |
| Damage reduced | 30 | `vision_service.analyze_image()` on both photos |
| Repair evidence | 20 | `vision_service.analyze_image()` on the after photo |
| Image quality | 10 | `image_quality_service.assess_quality()` |

Thresholds:

| Score | Assessment |
|---|---|
| 80–100 | `likely_fixed` |
| 50–79 | `inconclusive` |
| 0–49 | `likely_not_fixed` |

```json
{
  "evidenceScore": 82,
  "assessment": "likely_fixed",
  "breakdown": { "sameLocation": 40, "damageReduced": 30, "repairEvidence": 10, "imageQuality": 2 },
  "explanation": ["...", "...", "...", "..."]
}
```

**`evidenceScore` is an explainability/business score. It is not, and must
never be presented as, AI/ML confidence.**

## The vision adapter's 5 states

`vision_service.analyze_image()` always returns one of:

| `status` | Meaning |
|---|---|
| `unavailable` | No model present under `models/pretrained/` — the default, expected state |
| `load_failed` | A model directory has content, but loading it raised an error |
| `invalid_image` | The input file isn't a valid, decodable image |
| `inference_failed` | The model loaded, but running it raised an error |
| `ok` | A real prediction was produced — `label`/`confidence` populated |

`label`/`confidence` are `None` in every state except `ok`. Nothing is ever
fabricated.

## Adding a real model (what remains before production integration)

This prototype deliberately ships **no model-loading backend** —
`vision_service._load_model()` raises `NotImplementedError` for any content
found under `models/pretrained/`, honestly reported as `load_failed`, rather
than pretending to support a format it doesn't. Before this module could be
wired into real inference:

1. **Choose a real backend and format** (a fine-tuned torch classifier? a
   CLIP-style zero-shot model? a hosted vision API?) — this is a product
   decision, not made here.
2. **Implement `_load_model()`** to actually load that chosen format, lazily,
   only when `models/pretrained/` has content.
3. **Get a real labelled before/after dataset** — the `_score_damage_reduced`/
   `_score_repair_evidence` heuristics in `evidence_score_service.py` expect
   specific label strings (`fixed`, `damaged`, etc.); a real model's label
   vocabulary needs to be mapped onto (or replace) that set.
4. **Re-run this project's own test suite** against the real backend, and add
   new tests for its actual behavior — the existing tests use a fake model
   object precisely so this integration work doesn't require rewriting them.
5. **Only then** consider how this standalone service's interfaces
   (`analyze_before_after(before_path, after_path) -> dict`) could be called
   from — or have its logic ported into — the production project's own
   `app/services/vision_service.py`. That integration is out of scope for
   this prototype and has not been started.

## Isolation guarantees

- No file in this directory imports from, or is imported by, the production
  `YOUR_PROJECT/backend/` code.
- No MongoDB client, connection string, or dependency exists anywhere here.
- No authentication, no user model, no session/token handling exists here.
- Runs on port **8001** by default — the production backend's port (8000) is
  never touched.
- `scene_service.py` is an independent reimplementation of ORB+RANSAC scene
  comparison, written from scratch for this prototype — it does not import
  the production project's `scene_match_service.py`.
