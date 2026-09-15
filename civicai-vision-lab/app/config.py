"""
Configuration for CivicAI Vision Lab.

STANDALONE — this module reads its own .env only, defines its own defaults,
and does not import or reference anything from the production CivicAI
project's app/config.py. No MongoDB URI, no SECRET_KEY, no production
credential of any kind exists here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# All path defaults are anchored to THIS project's own root (the directory
# containing this file's parent), never the current working directory - so
# `python run.py` from anywhere, or `pytest` from anywhere, resolves the same
# models/pretrained and data/outputs directories.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings:
    APP_NAME: str = "CivicAI Vision Lab"
    APP_DESCRIPTION: str = (
        "Standalone prototype of a future Vision AI + Evidence Verification "
        "module. NOT connected to the production CivicAI application."
    )

    HOST: str = os.getenv("HOST", "127.0.0.1")
    # Deliberately NOT 8000 - the production CivicAI backend already runs
    # there. This prototype has its own separate port.
    PORT: int = int(os.getenv("PORT", "8001"))

    MODEL_DIR: str = os.getenv("MODEL_DIR", str(PROJECT_ROOT / "models" / "pretrained"))
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "data" / "outputs"))
    SAMPLES_DIR: str = os.getenv("SAMPLES_DIR", str(PROJECT_ROOT / "data" / "samples"))

    # Image quality thresholds
    MIN_RESOLUTION_WIDTH: int = int(os.getenv("MIN_RESOLUTION_WIDTH", "300"))
    MIN_RESOLUTION_HEIGHT: int = int(os.getenv("MIN_RESOLUTION_HEIGHT", "300"))
    BLUR_VARIANCE_THRESHOLD: float = float(os.getenv("BLUR_VARIANCE_THRESHOLD", "100.0"))
    MIN_BRIGHTNESS: float = float(os.getenv("MIN_BRIGHTNESS", "25.0"))
    MAX_BRIGHTNESS: float = float(os.getenv("MAX_BRIGHTNESS", "230.0"))

    # Upload limits (this prototype's own — independent of production's)
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "8"))

    # Scene comparison (ORB + RANSAC)
    ORB_MAX_FEATURES: int = int(os.getenv("ORB_MAX_FEATURES", "1000"))
    ORB_MIN_KEYPOINTS: int = int(os.getenv("ORB_MIN_KEYPOINTS", "8"))
    ORB_MIN_GOOD_MATCHES: int = int(os.getenv("ORB_MIN_GOOD_MATCHES", "10"))
    ORB_RATIO_THRESHOLD: float = float(os.getenv("ORB_RATIO_THRESHOLD", "0.75"))
    ORB_SAME_SCENE_MATCH_SCORE: float = float(os.getenv("ORB_SAME_SCENE_MATCH_SCORE", "0.3"))

    # Evidence scoring weights (points, not percentages — see evidence_score_service.py)
    POINTS_SAME_LOCATION: int = 40
    POINTS_DAMAGE_REDUCED: int = 30
    POINTS_REPAIR_EVIDENCE: int = 20
    POINTS_IMAGE_QUALITY: int = 10

    ASSESSMENT_LIKELY_FIXED_MIN: int = 80
    ASSESSMENT_INCONCLUSIVE_MIN: int = 50


settings = Settings()
