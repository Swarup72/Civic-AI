"""
Response shapes for CivicAI Vision Lab. Standalone Pydantic models — no
import of, or dependency on, the production project's app/schemas/*.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class SceneResult(BaseModel):
    """Output of scene_service.compare_scenes(). sameScene is None (not
    False) when the comparison itself couldn't be attempted — e.g. too few
    keypoints in a low-texture image — never silently defaulted to a boolean
    that would misrepresent an unknown result as a negative one."""
    sameScene: Optional[bool]
    matchScore: float
    explanation: List[str]


class VisionAnalysisResult(BaseModel):
    """Output of vision_service.analyze_image(). `status` is one of:
    'ok', 'unavailable', 'load_failed', 'invalid_image', 'inference_failed'.
    label/confidence are populated ONLY when status == 'ok' — every other
    status leaves them None, by contract, never fabricated."""
    available: bool
    status: str
    label: Optional[str] = None
    confidence: Optional[float] = None
    reasons: List[str]
    modelVersion: Optional[str] = None


class ImageQualityResult(BaseModel):
    """Output of image_quality_service.assess_quality()."""
    passed: bool
    corrupted: bool
    resolutionOk: bool
    width: Optional[int] = None
    height: Optional[int] = None
    blurScore: Optional[float] = None
    blurOk: Optional[bool] = None
    brightness: Optional[float] = None
    brightnessOk: Optional[bool] = None
    qualityScore: int = Field(ge=0, le=100)
    reasons: List[str]


class EvidenceBreakdown(BaseModel):
    """Point allocation out of the fixed weights: sameLocation<=40,
    damageReduced<=30, repairEvidence<=20, imageQuality<=10. This is an
    explainability/business score breakdown, NOT a model confidence
    breakdown — see EvidenceAssessment's own docstring."""
    sameLocation: int = Field(ge=0, le=40)
    damageReduced: int = Field(ge=0, le=30)
    repairEvidence: int = Field(ge=0, le=20)
    imageQuality: int = Field(ge=0, le=10)


class EvidenceAssessment(BaseModel):
    """Output of evidence_score_service.assess_evidence().

    IMPORTANT: `evidenceScore` is a deterministic, rule-based EXPLAINABILITY
    score built from the four weighted signals in `breakdown` — it is NOT an
    AI/ML confidence value, and must never be presented, logged, or labeled
    as one anywhere in this codebase or any caller of it."""
    evidenceScore: int = Field(ge=0, le=100)
    assessment: str  # "likely_fixed" | "inconclusive" | "likely_not_fixed"
    breakdown: EvidenceBreakdown
    explanation: List[str]


class AnalyzeResponse(BaseModel):
    """The full response shape for POST /api/analyze."""
    beforeQuality: ImageQualityResult
    afterQuality: ImageQualityResult
    scene: SceneResult
    beforeVision: VisionAnalysisResult
    afterVision: VisionAnalysisResult
    evidence: EvidenceAssessment
