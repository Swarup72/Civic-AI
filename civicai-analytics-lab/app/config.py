"""
Configuration for CivicAI Analytics Lab.

STANDALONE — reads its own .env only. No import of, or reference to, the
production CivicAI project's app/config.py. No MongoDB URI, no SECRET_KEY,
no production credential of any kind exists here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings:
    APP_NAME: str = "CivicAI Analytics Lab"
    APP_DESCRIPTION: str = (
        "Standalone, deterministic (non-ML) analytics prototype for civic "
        "complaint records: priority, trend, hotspot, impact, department, "
        "and category analysis. NOT connected to the production CivicAI "
        "application. Operates only on local CSV/JSON data."
    )

    HOST: str = os.getenv("HOST", "127.0.0.1")
    # Deliberately NOT 8000 (production), 8001 (civicai-vision-lab), or 8002
    # (civicai-text-lab).
    PORT: int = int(os.getenv("PORT", "8003"))

    RAW_DATA_DIR: str = os.getenv("RAW_DATA_DIR", str(PROJECT_ROOT / "data" / "raw"))
    PROCESSED_DATA_DIR: str = os.getenv("PROCESSED_DATA_DIR", str(PROJECT_ROOT / "data" / "processed"))
    SAMPLE_DATA_DIR: str = os.getenv("SAMPLE_DATA_DIR", str(PROJECT_ROOT / "data" / "sample"))
    OUTPUTS_DIR: str = os.getenv("OUTPUTS_DIR", str(PROJECT_ROOT / "data" / "outputs"))
    SAMPLE_DATASET_FILENAME: str = os.getenv("SAMPLE_DATASET_FILENAME", "sample_complaints.csv")

    # Priority formula weights (see app/services/priority_analysis.py's own
    # docstring: independently designed for THIS analytics prototype, NOT
    # verified to match the production priority_service.py's output).
    WEIGHT_SEVERITY: float = float(os.getenv("WEIGHT_SEVERITY", "0.40"))
    WEIGHT_AFFECTED_USERS: float = float(os.getenv("WEIGHT_AFFECTED_USERS", "0.20"))
    WEIGHT_SUPPORT_COUNT: float = float(os.getenv("WEIGHT_SUPPORT_COUNT", "0.15"))
    WEIGHT_LOCATION_SENSITIVITY: float = float(os.getenv("WEIGHT_LOCATION_SENSITIVITY", "0.15"))
    WEIGHT_DURATION: float = float(os.getenv("WEIGHT_DURATION", "0.10"))

    PRIORITY_CRITICAL_MIN: int = int(os.getenv("PRIORITY_CRITICAL_MIN", "75"))
    PRIORITY_HIGH_MIN: int = int(os.getenv("PRIORITY_HIGH_MIN", "50"))
    PRIORITY_MEDIUM_MIN: int = int(os.getenv("PRIORITY_MEDIUM_MIN", "25"))

    # A record counts as "high priority" for hotspot/department/category
    # rollups when its priorityLabel is High or Critical.
    HIGH_PRIORITY_LABELS = ("High", "Critical")

    # Trend classification threshold — deterministic, documented (see
    # app/services/trend_analysis.py).
    TREND_STABLE_BAND_PERCENT: float = float(os.getenv("TREND_STABLE_BAND_PERCENT", "10.0"))

    # Optional-field defaults (see app/services/data_service.py) — documented
    # here AND in README.md so nothing is a silent, undiscoverable default.
    DEFAULT_SUPPORT_COUNT: int = int(os.getenv("DEFAULT_SUPPORT_COUNT", "0"))
    DEFAULT_AFFECTED_USERS: int = int(os.getenv("DEFAULT_AFFECTED_USERS", "10"))
    DEFAULT_LOCATION_SENSITIVITY: str = os.getenv("DEFAULT_LOCATION_SENSITIVITY", "Medium")

    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))


settings = Settings()
