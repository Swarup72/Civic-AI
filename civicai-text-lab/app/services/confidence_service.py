"""
Confidence gating — decides whether an ML prediction's real predict_proba()
values are trustworthy enough to use as-is. This module NEVER computes,
adjusts, smooths, or invents a confidence number; it only reads the values
handed to it by classifier_service.py and compares them to a threshold.
"""
from typing import Dict, Optional

from app.config import settings


def overall_confidence(confidence_by_head: Dict[str, float]) -> float:
    """The overall confidence for a multi-head prediction is the WEAKEST
    individual head's confidence — a model that's 99% sure about category
    but only 20% sure about severity must not be reported as high-confidence
    overall. Matches the same principle production ML systems in this
    product line already use, reimplemented independently here."""
    if not confidence_by_head:
        return 0.0
    return min(confidence_by_head.values())


def meets_threshold(confidence_by_head: Dict[str, float], threshold: Optional[float] = None) -> bool:
    threshold = settings.CONFIDENCE_THRESHOLD if threshold is None else threshold
    return overall_confidence(confidence_by_head) >= threshold


def needs_review(confidence_by_head: Dict[str, float], threshold: Optional[float] = None) -> bool:
    return not meets_threshold(confidence_by_head, threshold)
