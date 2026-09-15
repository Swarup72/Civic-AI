"""
Standalone API routes for CivicAI Analytics Lab.

No authentication, no database, no connection to the production CivicAI
application anywhere in this file. Every endpoint operates only on local
CSV/JSON data (the bundled sample dataset, or an uploaded CSV file).
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.schemas.analytics_schema import AnalyzeRequest
from app.services import analytics_pipeline, data_service

router = APIRouter()


def _sample_dataset_path() -> Path:
    return Path(settings.SAMPLE_DATA_DIR) / settings.SAMPLE_DATASET_FILENAME


def _run_pipeline_or_400(loader):
    """Shared error translation: both endpoints below run the SAME
    analytics_pipeline.analyze_dataset() call and must translate its two
    known error types into a clear 400 the same way — never a raw 500."""
    try:
        return loader()
    except (data_service.DatasetValidationError, analytics_pipeline.AnalyticsError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "civicai-analytics-lab",
        "sampleDatasetAvailable": _sample_dataset_path().exists(),
    }


@router.post("/analyze")
async def analyze(payload: Optional[AnalyzeRequest] = None):
    """Analyzes the bundled sample dataset (data/sample/), optionally
    scoped by filters in the request body."""
    sample_path = _sample_dataset_path()
    if not sample_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Sample dataset not found at {sample_path}. "
                "Run `python scripts/generate_dataset.py` first."
            ),
        )

    filters = payload.filters.model_dump(exclude_none=True) if payload and payload.filters else None

    def _load():
        df = data_service.load_csv(sample_path)
        return analytics_pipeline.analyze_dataset(df, filters=filters)

    return _run_pipeline_or_400(_load)


@router.post("/analyze/upload")
async def analyze_upload(file: UploadFile = File(...), filters: Optional[str] = Form(None)):
    """Accepts a CSV upload and analyzes it. `filters`, if provided, is a
    JSON-encoded string (form field) with the same shape as POST /api/analyze's
    body — kept as a plain string here since multipart form requests can't
    carry a nested JSON object as a typed field the way a JSON body can.

    IMPORTANT: must be declared as Form(...), not a bare default — a
    multipart endpoint's non-file parameters are silently ignored (not
    populated from the submitted form data at all) unless explicitly
    declared this way. A real bug this project's own test suite caught:
    filters were silently no-ops without this."""
    raw_bytes = await file.read()

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise HTTPException(status_code=400, detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit.")
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    parsed_filters = None
    if filters:
        try:
            parsed_filters = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="`filters` must be a valid JSON object if provided.")

    def _load():
        df = data_service.load_csv(raw_bytes)
        return analytics_pipeline.analyze_dataset(df, filters=parsed_filters)

    return _run_pipeline_or_400(_load)
