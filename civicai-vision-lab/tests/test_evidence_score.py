"""
evidence_score_service.py tests. Every test constructs the four upstream
results directly (as if scene_service/vision_service/image_quality_service had
already run) — assess_evidence() is a pure function over those, so its
correctness is fully testable in isolation from whether a real vision model
happens to be available.
"""
from app.services import evidence_score_service

SAME_SCENE = {"sameScene": True, "matchScore": 0.9, "explanation": ["same"]}
DIFFERENT_SCENE = {"sameScene": False, "matchScore": 0.05, "explanation": ["different"]}
UNKNOWN_SCENE = {"sameScene": None, "matchScore": 0.0, "explanation": ["inconclusive"]}

VISION_UNAVAILABLE = {"available": False, "status": "unavailable", "label": None, "confidence": None, "reasons": []}


def _vision_ok(label, confidence):
    return {"available": True, "status": "ok", "label": label, "confidence": confidence, "reasons": []}


def test_score_100_when_everything_maximal():
    result = evidence_score_service.assess_evidence(
        scene_result=SAME_SCENE,
        before_result=_vision_ok("damaged", 0.95),
        after_result=_vision_ok("fixed", 1.0),
        quality_result={"qualityScore": 100},
    )
    assert result["evidenceScore"] == 100
    assert result["assessment"] == "likely_fixed"
    assert sum(result["breakdown"].values()) == 100


def test_score_0_when_everything_fails():
    result = evidence_score_service.assess_evidence(
        scene_result=DIFFERENT_SCENE,
        before_result=VISION_UNAVAILABLE,
        after_result=VISION_UNAVAILABLE,
        quality_result={"qualityScore": 0},
    )
    assert result["evidenceScore"] == 0
    assert result["assessment"] == "likely_not_fixed"
    assert result["breakdown"] == {"sameLocation": 0, "damageReduced": 0, "repairEvidence": 0, "imageQuality": 0}


def test_likely_fixed_at_exactly_80_boundary():
    """80 is the lower boundary of likely_fixed - hand-computed to land on it
    exactly: sameLocation=40 (same scene) + damageReduced=20
    (round(30*0.667)) + repairEvidence=13 (round(20*0.667)) + imageQuality=7
    (round(10*0.70)) = 80."""
    result = evidence_score_service.assess_evidence(
        scene_result=SAME_SCENE,
        before_result=_vision_ok("damaged", 0.9),
        after_result=_vision_ok("fixed", 0.667),
        quality_result={"qualityScore": 70},
    )
    assert result["breakdown"] == {"sameLocation": 40, "damageReduced": 20, "repairEvidence": 13, "imageQuality": 7}
    assert result["evidenceScore"] == 80
    assert result["assessment"] == "likely_fixed"


def test_likely_fixed_with_maximal_signals():
    result = evidence_score_service.assess_evidence(
        scene_result=SAME_SCENE,
        before_result=_vision_ok("damaged", 0.9),
        after_result=_vision_ok("fixed", 1.0),
        quality_result={"qualityScore": 0},
    )
    # sameLocation=40, damageReduced=30 (fixed@1.0), repairEvidence=20 (fixed@1.0), imageQuality=0 -> 90
    assert result["evidenceScore"] == 90
    assert result["assessment"] == "likely_fixed"


def test_inconclusive_band():
    result = evidence_score_service.assess_evidence(
        scene_result=SAME_SCENE,  # +40
        before_result=VISION_UNAVAILABLE,  # damageReduced -> 0 (unavailable)
        after_result=VISION_UNAVAILABLE,  # repairEvidence -> 0 (unavailable)
        quality_result={"qualityScore": 100},  # +10
    )
    assert result["evidenceScore"] == 50
    assert result["assessment"] == "inconclusive"


def test_likely_not_fixed_band():
    result = evidence_score_service.assess_evidence(
        scene_result=DIFFERENT_SCENE,  # +0
        before_result=_vision_ok("damaged", 0.9),
        after_result=_vision_ok("damaged", 0.9),  # still damaged -> 0 + 0
        quality_result={"qualityScore": 50},  # +5
    )
    assert result["evidenceScore"] < 50
    assert result["assessment"] == "likely_not_fixed"


def test_unknown_scene_never_awards_same_location_points():
    """An inconclusive scene comparison (None, not False) must still score 0
    points for sameLocation - 'unknown' is not 'confirmed', but it is also
    not silently upgraded to a positive score."""
    result = evidence_score_service.assess_evidence(
        scene_result=UNKNOWN_SCENE,
        before_result=_vision_ok("damaged", 0.9),
        after_result=_vision_ok("fixed", 1.0),
        quality_result={"qualityScore": 100},
    )
    assert result["breakdown"]["sameLocation"] == 0


def test_breakdown_never_exceeds_its_own_weight_cap():
    result = evidence_score_service.assess_evidence(
        scene_result=SAME_SCENE,
        before_result=_vision_ok("damaged", 0.99),
        after_result=_vision_ok("fixed", 0.99),
        quality_result={"qualityScore": 100},
    )
    assert result["breakdown"]["sameLocation"] <= 40
    assert result["breakdown"]["damageReduced"] <= 30
    assert result["breakdown"]["repairEvidence"] <= 20
    assert result["breakdown"]["imageQuality"] <= 10


def test_breakdown_sums_to_evidence_score():
    for quality in (0, 25, 50, 75, 100):
        result = evidence_score_service.assess_evidence(
            scene_result=SAME_SCENE,
            before_result=_vision_ok("damaged", 0.8),
            after_result=_vision_ok("fixed", 0.8),
            quality_result={"qualityScore": quality},
        )
        assert sum(result["breakdown"].values()) == result["evidenceScore"]


def test_explanation_is_a_nonempty_list_of_strings():
    result = evidence_score_service.assess_evidence(SAME_SCENE, VISION_UNAVAILABLE, VISION_UNAVAILABLE, {"qualityScore": 50})
    assert isinstance(result["explanation"], list)
    assert len(result["explanation"]) >= 4  # one per scoring signal
    assert all(isinstance(e, str) for e in result["explanation"])


def test_score_is_never_labeled_as_ai_confidence():
    """Explicit contract check from the task brief: the score must never be
    presented as AI/ML confidence, anywhere in its own response shape."""
    result = evidence_score_service.assess_evidence(SAME_SCENE, VISION_UNAVAILABLE, VISION_UNAVAILABLE, {"qualityScore": 50})
    assert "confidence" not in result
    assert "aiConfidence" not in result
    joined_explanation = " ".join(result["explanation"]).lower()
    assert "ai confidence" not in joined_explanation
