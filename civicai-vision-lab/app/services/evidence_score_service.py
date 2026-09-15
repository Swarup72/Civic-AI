"""
The core evidence-assessment function.

IMPORTANT — read before touching this file: `evidenceScore` is a
deterministic, RULE-BASED EXPLAINABILITY / BUSINESS SCORE built from four
weighted, independently-explained signals. It is NOT a machine-learning
confidence value, must never be computed from a raw model logit/softmax
value directly, and must never be labeled "AI confidence" anywhere — in a
response, a log line, a docstring, or a comment. Every point awarded traces
back to one of the four named signals in `breakdown`, and every signal has
a plain-English reason in `explanation`.

Weights (points, not percentages):
    Same location   = 40
    Damage reduced  = 30
    Repair evidence = 20
    Image quality   = 10
                    -----
                      100

Thresholds:
    80-100  -> "likely_fixed"
    50-79   -> "inconclusive"
     0-49   -> "likely_not_fixed"
"""
from typing import Any, Dict, List, Tuple

from app.config import settings

_FIXED_LABELS = {"fixed", "repaired", "no_damage", "clear", "resolved"}
_DAMAGE_LABELS = {"damaged", "pothole", "broken", "not_fixed", "unrepaired"}


def _score_same_location(scene_result: Dict[str, Any]) -> Tuple[int, str]:
    max_points = settings.POINTS_SAME_LOCATION
    same_scene = scene_result.get("sameScene")
    if same_scene is True:
        return max_points, "Same location confirmed (scene comparison matched)."
    if same_scene is False:
        return 0, "Evidence photo does NOT appear to match the original location."
    return 0, "Location match could not be determined (scene comparison was inconclusive)."


def _score_damage_reduced(before_result: Dict[str, Any], after_result: Dict[str, Any]) -> Tuple[int, str]:
    max_points = settings.POINTS_DAMAGE_REDUCED

    if not before_result.get("available") or not after_result.get("available"):
        return 0, "Damage-reduction assessment unavailable (vision model not available for the before/after comparison)."

    after_label = (after_result.get("label") or "").lower()
    after_confidence = after_result.get("confidence") or 0.0
    before_label = (before_result.get("label") or "").lower()

    if after_label in _FIXED_LABELS and after_confidence >= 0.6:
        points = round(max_points * min(1.0, after_confidence))
        return points, (
            f"After-image vision analysis indicates the issue is resolved "
            f"(label='{after_result.get('label')}', confidence={after_confidence:.2f})."
        )

    if before_label in _DAMAGE_LABELS and after_label not in _FIXED_LABELS:
        return 0, "After-image vision analysis does not indicate the damage was resolved."

    partial = round(max_points * 0.4)
    return partial, "Vision analysis result is ambiguous about whether damage was reduced — partial credit only."


def _score_repair_evidence(after_result: Dict[str, Any]) -> Tuple[int, str]:
    max_points = settings.POINTS_REPAIR_EVIDENCE

    if not after_result.get("available"):
        return 0, "Repair-evidence assessment unavailable (vision model not available)."

    label = (after_result.get("label") or "").lower()
    confidence = after_result.get("confidence") or 0.0

    if label in _FIXED_LABELS and confidence >= 0.5:
        points = round(max_points * min(1.0, confidence))
        return points, f"After-image shows visible repair evidence (label='{after_result.get('label')}')."

    return 0, "No clear repair evidence detected in the after-image."


def _score_image_quality(quality_result: Dict[str, Any]) -> Tuple[int, str]:
    max_points = settings.POINTS_IMAGE_QUALITY
    quality_score = quality_result.get("qualityScore", 0)
    points = round(max_points * (quality_score / 100.0))
    return points, f"Combined image quality score: {quality_score}/100."


def _assessment_for(total: int) -> str:
    if total >= settings.ASSESSMENT_LIKELY_FIXED_MIN:
        return "likely_fixed"
    if total >= settings.ASSESSMENT_INCONCLUSIVE_MIN:
        return "inconclusive"
    return "likely_not_fixed"


def assess_evidence(
    scene_result: Dict[str, Any],
    before_result: Dict[str, Any],
    after_result: Dict[str, Any],
    quality_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Args:
        scene_result:   output of scene_service.compare_scenes()
        before_result:  output of vision_service.analyze_image() for the "before" photo
        after_result:   output of vision_service.analyze_image() for the "after" photo
        quality_result: a combined quality indicator, e.g. {"qualityScore": 87}
                        (analysis_service.py averages before/after quality scores)

    Returns:
        {
          "evidenceScore": int (0-100),
          "assessment": "likely_fixed" | "inconclusive" | "likely_not_fixed",
          "breakdown": {"sameLocation": int, "damageReduced": int,
                        "repairEvidence": int, "imageQuality": int},
          "explanation": [str, ...]
        }
    """
    explanation: List[str] = []

    same_location_points, same_location_note = _score_same_location(scene_result)
    explanation.append(same_location_note)

    damage_points, damage_note = _score_damage_reduced(before_result, after_result)
    explanation.append(damage_note)

    repair_points, repair_note = _score_repair_evidence(after_result)
    explanation.append(repair_note)

    quality_points, quality_note = _score_image_quality(quality_result)
    explanation.append(quality_note)

    breakdown = {
        "sameLocation": same_location_points,
        "damageReduced": damage_points,
        "repairEvidence": repair_points,
        "imageQuality": quality_points,
    }

    total = sum(breakdown.values())
    total = min(100, max(0, total))

    return {
        "evidenceScore": total,
        "assessment": _assessment_for(total),
        "breakdown": breakdown,
        "explanation": explanation,
    }
