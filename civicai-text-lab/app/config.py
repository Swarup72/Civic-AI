"""
Configuration for CivicAI Text Intelligence Lab.

STANDALONE — reads its own .env only. No import of, or reference to, the
production CivicAI project's app/config.py. No MongoDB URI, no SECRET_KEY,
no production credential of any kind exists here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Anchored to THIS project's own root, never the current working directory -
# so `python run.py` or `pytest` from anywhere resolves the same paths.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings:
    APP_NAME: str = "CivicAI Text Intelligence Lab"
    APP_DESCRIPTION: str = (
        "Standalone prototype of a complaint-text classification module "
        "(TF-IDF + Logistic Regression, with a deterministic rule-based "
        "fallback). NOT connected to the production CivicAI application."
    )

    HOST: str = os.getenv("HOST", "127.0.0.1")
    # Deliberately NOT 8000 (production backend) or 8001 (civicai-vision-lab).
    PORT: int = int(os.getenv("PORT", "8002"))

    MODEL_DIR: str = os.getenv("MODEL_DIR", str(PROJECT_ROOT / "models" / "trained"))
    RAW_DATA_DIR: str = os.getenv("RAW_DATA_DIR", str(PROJECT_ROOT / "data" / "raw"))
    PROCESSED_DATA_DIR: str = os.getenv("PROCESSED_DATA_DIR", str(PROJECT_ROOT / "data" / "processed"))
    SAMPLE_CASES_DIR: str = os.getenv("SAMPLE_CASES_DIR", str(PROJECT_ROOT / "data" / "sample_cases"))

    # Confidence gating: the WEAKEST of the three heads' own confidence must
    # meet this bar, or the pipeline flags needsReview and offers the caller
    # a rule-fallback result instead (see analysis_service.py).
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.45"))

    # Training / evaluation split ratios (must sum to 1.0 - validated in
    # training/split_dataset.py, not assumed).
    TRAIN_RATIO: float = float(os.getenv("TRAIN_RATIO", "0.70"))
    VAL_RATIO: float = float(os.getenv("VAL_RATIO", "0.15"))
    TEST_RATIO: float = float(os.getenv("TEST_RATIO", "0.15"))
    SPLIT_RANDOM_SEED: int = int(os.getenv("SPLIT_RANDOM_SEED", "42"))

    MAX_TEXT_LENGTH: int = int(os.getenv("MAX_TEXT_LENGTH", "5000"))
    MAX_BATCH_SIZE: int = int(os.getenv("MAX_BATCH_SIZE", "100"))


settings = Settings()
