"""
Standalone TF-IDF + Logistic Regression classifier ADAPTER — loads
vectorizer.pkl + {category,severity,department}_model.pkl + metadata.json
lazily from settings.MODEL_DIR. Never trains here (see training/train.py for
that), never fabricates a result, never raises to its caller.

Independently written for this prototype. Structurally similar in spirit to
the production project's own ml_service.py (same well-established "lazy
singleton, load once, degrade honestly" pattern for an optional trained-
model dependency) but shares no code, no saved model file, and no import
with it.

States:
  - unavailable  -> required model files are not all present under MODEL_DIR
  - load_failed  -> files exist, but loading one of them raised an exception
  - (per-call)   -> predict() itself never raises; an inference-time
                    exception is caught and reported as None, the same
                    contract as "unavailable" from the caller's point of view
                    (analysis_service.py falls back to rule_fallback_service
                    either way).
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger("textlab.classifier")

HEADS = ("category", "severity", "department")
REQUIRED_FILES = ("vectorizer.pkl", "metadata.json") + tuple(f"{h}_model.pkl" for h in HEADS)

_vectorizer: Optional[Any] = None
_heads: Optional[Dict[str, Any]] = None
_metadata: Optional[Dict[str, Any]] = None
_load_attempted: bool = False
_load_error: Optional[str] = None


def _model_files_present() -> bool:
    model_dir = Path(settings.MODEL_DIR)
    if not model_dir.exists():
        return False
    return all((model_dir / name).exists() for name in REQUIRED_FILES)


def _load_models():
    """Raises on any failure — the caller (_ensure_loaded) catches it and
    reports load_failed. Imports joblib lazily so a missing/incompatible
    scikit-learn install never breaks this module's own import."""
    import joblib

    model_dir = Path(settings.MODEL_DIR)
    metadata = json.loads((model_dir / "metadata.json").read_text())
    vectorizer = joblib.load(model_dir / "vectorizer.pkl")
    heads = {name: joblib.load(model_dir / f"{name}_model.pkl") for name in HEADS}
    return vectorizer, heads, metadata


def reset_cache() -> None:
    """Testing/ops hook — forces the next call to re-attempt loading."""
    global _vectorizer, _heads, _metadata, _load_attempted, _load_error
    _vectorizer = None
    _heads = None
    _metadata = None
    _load_attempted = False
    _load_error = None


def _ensure_loaded() -> None:
    global _vectorizer, _heads, _metadata, _load_attempted, _load_error
    if _load_attempted:
        return
    _load_attempted = True

    if not _model_files_present():
        return  # unavailable — not an error, the expected state until training/train.py has run

    try:
        _vectorizer, _heads, _metadata = _load_models()
    except Exception as e:
        _load_error = str(e)
        _vectorizer, _heads, _metadata = None, None, None


def is_available() -> bool:
    _ensure_loaded()
    return _heads is not None


def get_status() -> str:
    """One of: 'available', 'unavailable', 'load_failed'."""
    _ensure_loaded()
    if _load_error:
        return "load_failed"
    if _heads is None:
        return "unavailable"
    return "available"


def get_model_version() -> Optional[str]:
    _ensure_loaded()
    return _metadata.get("modelVersion") if _metadata else None


def predict(normalized_text: str) -> Optional[Dict[str, Any]]:
    """Returns:
        {"category": str, "severity": str, "department": str,
         "confidence": {"category": float, "severity": float, "department": float},
         "modelVersion": str}
    or None if the model is unavailable, failed to load, or inference itself
    raised. label values are real predict() outputs; confidence values are
    real predict_proba() outputs — nothing here is ever invented."""
    _ensure_loaded()
    if _heads is None or _vectorizer is None:
        return None

    try:
        vector = _vectorizer.transform([normalized_text])
        result: Dict[str, str] = {}
        confidence: Dict[str, float] = {}
        for head_name, classifier in _heads.items():
            probabilities = classifier.predict_proba(vector)[0]
            best_index = probabilities.argmax()
            result[head_name] = classifier.classes_[best_index]
            confidence[head_name] = round(float(probabilities[best_index]), 4)

        return {
            **result,
            "confidence": confidence,
            "modelVersion": _metadata.get("modelVersion", "unknown") if _metadata else "unknown",
        }
    except Exception as e:
        logger.warning(f"classifier_service: inference failed ({e}) — caller should fall back to rule_fallback_service.")
        return None
