"""
Standalone API routes for CivicAI Text Intelligence Lab.

No authentication, no database, no connection to the production CivicAI
application anywhere in this file.
"""
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas.analysis_schema import AnalysisResult, AnalyzeRequest, BatchAnalysisResult, BatchAnalyzeRequest
from app.services import analysis_service, classifier_service

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(payload: AnalyzeRequest):
    result = analysis_service.analyze_text(payload.text)
    return result


@router.post("/analyze/batch", response_model=BatchAnalysisResult)
async def analyze_batch(payload: BatchAnalyzeRequest):
    if len(payload.texts) > settings.MAX_BATCH_SIZE:
        raise HTTPException(status_code=400, detail=f"Batch size must be at most {settings.MAX_BATCH_SIZE}.")
    results = [analysis_service.analyze_text(text) for text in payload.texts]
    return {"results": results, "count": len(results)}


@router.get("/status")
async def status():
    """Reports this prototype's own classifier availability — a real,
    computed signal, never a hardcoded 'all systems nominal'."""
    return {
        "service": "civicai-text-lab",
        "classifierStatus": classifier_service.get_status(),
        "modelVersion": classifier_service.get_model_version(),
        "confidenceThreshold": settings.CONFIDENCE_THRESHOLD,
    }
