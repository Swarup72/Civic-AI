"""
Standalone image-quality assessment: minimum resolution, blur (sharpness),
brightness/exposure, and corrupted-image detection. Pure OpenCV/numpy — no
ML model, no network, no dependency on the production CivicAI project.
"""
from typing import Any, Dict

import cv2
import numpy as np

from app.config import settings
from app.utils import image_utils


def _blur_score(gray: np.ndarray) -> float:
    """Variance of the Laplacian — a standard, well-understood sharpness
    proxy: a blurry image has fewer sharp edges, hence lower variance."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def assess_quality(image_bytes: bytes) -> Dict[str, Any]:
    """Returns a normalized quality result:
    {
      "passed": bool, "corrupted": bool, "resolutionOk": bool,
      "width": int|None, "height": int|None,
      "blurScore": float|None, "blurOk": bool|None,
      "brightness": float|None, "brightnessOk": bool|None,
      "qualityScore": int (0-100), "reasons": [...]
    }
    Never raises — a corrupted/undecodable image is a valid, expected input,
    reported honestly rather than crashing the caller."""
    color = image_utils.to_cv2_color(image_bytes)
    if color is None:
        return {
            "passed": False,
            "corrupted": True,
            "resolutionOk": False,
            "qualityScore": 0,
            "reasons": ["Image is corrupted, empty, or not a readable image format."],
        }

    height, width = color.shape[:2]
    resolution_ok = width >= settings.MIN_RESOLUTION_WIDTH and height >= settings.MIN_RESOLUTION_HEIGHT

    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    blur_score = _blur_score(gray)
    blur_ok = blur_score >= settings.BLUR_VARIANCE_THRESHOLD

    brightness = float(np.mean(gray))
    brightness_ok = settings.MIN_BRIGHTNESS <= brightness <= settings.MAX_BRIGHTNESS

    reasons = []
    if not resolution_ok:
        reasons.append(
            f"Resolution {width}x{height} is below the minimum "
            f"{settings.MIN_RESOLUTION_WIDTH}x{settings.MIN_RESOLUTION_HEIGHT}."
        )
    if not blur_ok:
        reasons.append(
            f"Image appears blurry (sharpness score {blur_score:.1f}, "
            f"need >= {settings.BLUR_VARIANCE_THRESHOLD})."
        )
    if not brightness_ok:
        direction = "too dark" if brightness < settings.MIN_BRIGHTNESS else "over-exposed"
        reasons.append(f"Image is {direction} (mean brightness {brightness:.1f}).")
    if not reasons:
        reasons.append("Image passed all quality checks.")

    passed = resolution_ok and blur_ok and brightness_ok

    # A weighted, explainable 0-100 quality score - partial credit for "close
    # but not quite" sharpness rather than an all-or-nothing cliff, matching
    # this prototype's general "explainable, not a black box" scoring style.
    resolution_component = 40.0 if resolution_ok else 0.0
    blur_component = 40.0 if blur_ok else min(40.0, 40.0 * (blur_score / settings.BLUR_VARIANCE_THRESHOLD))
    brightness_component = 20.0 if brightness_ok else 0.0
    quality_score = int(round(min(100.0, max(0.0, resolution_component + blur_component + brightness_component))))

    return {
        "passed": passed,
        "corrupted": False,
        "resolutionOk": resolution_ok,
        "width": width,
        "height": height,
        "blurScore": round(blur_score, 2),
        "blurOk": blur_ok,
        "brightness": round(brightness, 2),
        "brightnessOk": brightness_ok,
        "qualityScore": quality_score,
        "reasons": reasons,
    }
