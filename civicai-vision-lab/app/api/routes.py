"""
Standalone API routes for CivicAI Vision Lab.

No authentication, no database, no connection to the production CivicAI
application anywhere in this file — by explicit design (see README.md).
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import AnalyzeResponse
from app.services import analysis_service

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _save_upload(raw_bytes: bytes, original_filename: str, tag: str, run_id: str) -> str:
    out_dir = Path(settings.OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_filename or "").suffix or ".jpg"
    out_path = out_dir / f"{run_id}_{tag}{suffix}"
    out_path.write_bytes(raw_bytes)
    return str(out_path)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    before_image: UploadFile = File(...),
    after_image: UploadFile = File(...),
):
    """Accepts two uploaded images (before_image, after_image) and returns
    the complete analysis: image quality, scene comparison, vision analysis
    for each photo, and the combined evidence assessment.

    No auth, no database — this is a standalone prototype endpoint."""
    before_bytes = await before_image.read()
    after_bytes = await after_image.read()

    if len(before_bytes) > _MAX_UPLOAD_BYTES or len(after_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"Each file must be under {settings.MAX_UPLOAD_SIZE_MB}MB.")

    # Content-type is a hint only, never trusted as the sole check — every
    # downstream service independently re-validates by actually decoding the
    # bytes (see image_utils.py) and reports honestly if that fails.
    run_id = uuid.uuid4().hex
    before_path = _save_upload(before_bytes, before_image.filename, "before", run_id)
    after_path = _save_upload(after_bytes, after_image.filename, "after", run_id)

    result = analysis_service.analyze_before_after(before_path, after_path)
    return result


@router.get("/status")
async def status():
    """Reports this prototype's own (standalone) vision-model availability —
    a real, computed signal, never a hardcoded 'all systems nominal'."""
    from app.services import vision_service

    return {
        "service": "civicai-vision-lab",
        "visionModelStatus": vision_service.get_status(),
    }
