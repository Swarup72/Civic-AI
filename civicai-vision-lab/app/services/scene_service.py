"""
Standalone classical-CV scene comparison (ORB keypoint matching + RANSAC
geometric verification). Answers ONE narrow question: do these two photos
show the same physical location? It says nothing about what's IN the photo
(that's vision_service.py's job).

STANDALONE: this is an independent reimplementation written for
civicai-vision-lab. It does not import, call, or otherwise depend on the
production CivicAI project's app/services/scene_match_service.py in any way —
no shared code, no shared state.

No ML model, no training, no network call — pure OpenCV geometry, real and
deterministic.
"""
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.config import settings
from app.utils import image_utils


def _detect_and_describe(gray: np.ndarray) -> Tuple[Optional[List[cv2.KeyPoint]], Optional[np.ndarray]]:
    orb = cv2.ORB_create(nfeatures=settings.ORB_MAX_FEATURES)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    return keypoints, descriptors


def _good_matches_by_ratio_test(des1: np.ndarray, des2: np.ndarray) -> List[cv2.DMatch]:
    """Lowe's ratio test — keeps a match only when it's meaningfully better
    than the second-best candidate, filtering out ambiguous matches."""
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw_matches = bf.knnMatch(des1, des2, k=2)
    good = []
    for pair in raw_matches:
        if len(pair) != 2:
            continue  # a query with fewer than 2 candidates can't pass a ratio test
        m, n = pair
        if m.distance < settings.ORB_RATIO_THRESHOLD * n.distance:
            good.append(m)
    return good


def compare_scenes(before_bytes: bytes, after_bytes: bytes) -> Dict[str, Any]:
    """Returns {"sameScene": bool | None, "matchScore": float, "explanation": [...]}.

    sameScene is:
      - True  -> enough geometrically-consistent matches found (same location)
      - False -> both images decoded fine and were compared, but too few/no
                 geometrically-consistent matches were found (different location)
      - None  -> the comparison genuinely could not be attempted (undecodable
                 image, or too few keypoints in one/both images to compare at
                 all) - an unknown result is never reported as a False one.
    """
    explanation: List[str] = []

    gray1 = image_utils.to_cv2_gray(before_bytes)
    gray2 = image_utils.to_cv2_gray(after_bytes)
    if gray1 is None or gray2 is None:
        explanation.append("One or both images could not be decoded — scene comparison not attempted.")
        return {"sameScene": None, "matchScore": 0.0, "explanation": explanation}

    kp1, des1 = _detect_and_describe(gray1)
    kp2, des2 = _detect_and_describe(gray2)

    if des1 is None or des2 is None or len(kp1) < settings.ORB_MIN_KEYPOINTS or len(kp2) < settings.ORB_MIN_KEYPOINTS:
        explanation.append(
            f"Not enough distinctive keypoints found (before={len(kp1) if kp1 else 0}, "
            f"after={len(kp2) if kp2 else 0}, need >= {settings.ORB_MIN_KEYPOINTS} each) — "
            "the comparison is inconclusive, not a confirmed mismatch."
        )
        return {"sameScene": None, "matchScore": 0.0, "explanation": explanation}

    good_matches = _good_matches_by_ratio_test(des1, des2)

    if len(good_matches) < settings.ORB_MIN_GOOD_MATCHES:
        explanation.append(
            f"Only {len(good_matches)} good keypoint match(es) found "
            f"(need >= {settings.ORB_MIN_GOOD_MATCHES}) — different location."
        )
        match_score = round(len(good_matches) / max(len(kp1), len(kp2), 1), 3)
        return {"sameScene": False, "matchScore": match_score, "explanation": explanation}

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    homography, inlier_mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

    inlier_count = int(inlier_mask.sum()) if inlier_mask is not None else 0
    match_score = round(inlier_count / max(len(good_matches), 1), 3)

    same_scene = homography is not None and inlier_count >= settings.ORB_MIN_GOOD_MATCHES and match_score >= settings.ORB_SAME_SCENE_MATCH_SCORE
    explanation.append(
        f"{len(good_matches)} good keypoint match(es), {inlier_count} geometrically "
        f"consistent after RANSAC (match score {match_score})."
    )
    if same_scene:
        explanation.append("Geometric evidence supports the same physical location.")
    else:
        explanation.append("Geometric evidence does not support the same physical location.")

    return {"sameScene": same_scene, "matchScore": match_score, "explanation": explanation}
