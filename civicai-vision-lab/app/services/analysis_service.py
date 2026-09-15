"""
The end-to-end analysis pipeline: takes two image file paths (before/after)
and runs every other service in order, combining their outputs into one
structured response. This is the ONLY place that orchestrates the other four
services together — each of them stays independently usable/testable on its
own.
"""
from typing import Any, Dict

from app.services import evidence_score_service, image_quality_service, scene_service, vision_service
from app.utils import image_utils


def analyze_before_after(before_path: str, after_path: str) -> Dict[str, Any]:
    """Runs, in order:
        1. image quality (before AND after)
        2. scene comparison (before vs after)
        3. before-image vision analysis
        4. after-image vision analysis
        5. evidence scoring (combines 1-4)

    Never raises — every stage is independently failure-tolerant (a missing/
    corrupt file degrades that stage's own result honestly; it does not stop
    the pipeline from returning a complete, structured response for every
    other stage)."""
    before_bytes = image_utils.read_bytes(before_path)
    after_bytes = image_utils.read_bytes(after_path)

    # 1. Image quality
    before_quality = image_quality_service.assess_quality(before_bytes or b"")
    after_quality = image_quality_service.assess_quality(after_bytes or b"")
    combined_quality = {
        "qualityScore": round((before_quality["qualityScore"] + after_quality["qualityScore"]) / 2)
    }

    # 2. Scene comparison
    scene_result = scene_service.compare_scenes(before_bytes or b"", after_bytes or b"")

    # 3 & 4. Vision analysis (independently, before and after)
    before_vision = vision_service.analyze_image(before_path)
    after_vision = vision_service.analyze_image(after_path)

    # 5. Evidence scoring
    evidence = evidence_score_service.assess_evidence(
        scene_result=scene_result,
        before_result=before_vision,
        after_result=after_vision,
        quality_result=combined_quality,
    )

    return {
        "beforeQuality": before_quality,
        "afterQuality": after_quality,
        "scene": scene_result,
        "beforeVision": before_vision,
        "afterVision": after_vision,
        "evidence": evidence,
    }
