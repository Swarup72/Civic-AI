"""
Standalone vision-model ADAPTER for image-CONTENT understanding (does this
photo show damaged / repaired infrastructure). Independently written for
civicai-vision-lab — does NOT import, call, or share any state with the
production CivicAI project's app/services/vision_service.py.

Contract (all five required states, each returned as a distinct, honestly-
labeled response — never fabricated):

  1. "unavailable"       — no model directory/files exist under
                            settings.MODEL_DIR. This is the EXPECTED,
                            default state in this prototype: no model is
                            shipped, none is trained here, and none is ever
                            downloaded automatically.
  2. "load_failed"       — a model directory/files DO exist, but attempting
                            to load them raised an exception (this
                            prototype's real loading backend is not yet
                            implemented — see README's "what remains before
                            production integration" — so any real model
                            files placed under models/pretrained/ today will
                            genuinely, honestly hit this path rather than
                            silently succeed).
  3. "invalid_image"     — the input file isn't a valid, decodable image.
  4. "inference_failed"  — the model loaded fine, but running it on a validly
                            decoded image raised an exception.
  5. "ok"                — the model loaded and produced a real prediction.
                            label/confidence are populated ONLY here.

Loading is LAZY: nothing under this module imports a heavy ML framework
(torch/transformers/onnxruntime/...) at import time, and none is imported
even lazily unless a model file genuinely exists to load. No model is
trained or downloaded by this module, ever.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings
from app.utils import image_utils

MODEL_VERSION_UNAVAILABLE = "vision-lab-v0-unavailable"

# Process-local lazy-singleton state, same pattern used throughout this
# prototype's design docs and intentionally mirroring (never importing) the
# broader CivicAI product line's own established "lazy load once, cache
# the result, never re-attempt mid-process" convention for optional AI
# backends.
_model: Optional[Any] = None
_load_attempted: bool = False
_load_error: Optional[str] = None


def _model_dir_has_content() -> bool:
    """True only if MODEL_DIR contains a real file — dotfiles (like the
    .gitkeep placeholder that keeps this empty directory trackable in git)
    are repo-structure metadata, never a model artifact, and must not be
    mistaken for one (a real bug this prototype's own test suite caught)."""
    model_dir = Path(settings.MODEL_DIR)
    if not model_dir.exists():
        return False
    return any(not p.name.startswith(".") for p in model_dir.iterdir())


def _load_model() -> Optional[Any]:
    """Isolated on its own so tests can exercise (or force) each outcome
    deterministically. Returns None (not an exception) when no model is
    present at all — that is the "unavailable" case, not a failure.

    If a model directory WITH content is found, this prototype does not yet
    implement a real loading backend (no framework choice has been made, and
    none should be added speculatively) — it raises, which the caller turns
    into an honest "load_failed" response. This is deliberate, not a bug:
    placing files under models/pretrained/ before a real backend exists here
    must never be silently treated as "the model works now."
    """
    if not _model_dir_has_content():
        return None

    raise NotImplementedError(
        "A file was found under models/pretrained/, but civicai-vision-lab "
        "does not yet implement a real model-loading backend (by design — "
        "no model was trained or bundled with this prototype). See "
        "README.md's 'What remains before production integration'."
    )


def _ensure_loaded() -> None:
    global _model, _load_attempted, _load_error
    if _load_attempted:
        return
    _load_attempted = True
    try:
        _model = _load_model()
    except Exception as e:
        _load_error = str(e)
        _model = None


def reset_cache() -> None:
    """Testing/ops hook: forces the next call to re-attempt loading from
    scratch. Not used by the request path itself."""
    global _model, _load_attempted, _load_error
    _model = None
    _load_attempted = False
    _load_error = None


def is_available() -> bool:
    _ensure_loaded()
    return _model is not None


def get_status() -> str:
    """One of: 'available', 'unavailable', 'load_failed'. Does not reflect
    per-call outcomes like 'invalid_image'/'inference_failed' — those are
    per-image, returned only by analyze_image()."""
    _ensure_loaded()
    if _load_error:
        return "load_failed"
    if _model is None:
        return "unavailable"
    return "available"


def analyze_image(image_path: str) -> Dict[str, Any]:
    """Returns:
    {"available": bool, "status": str, "label": str|None, "confidence": float|None,
     "reasons": [...], "modelVersion": str|None}

    NEVER raises. label/confidence are populated ONLY when status == "ok" —
    every other status leaves them None; nothing here is ever fabricated."""
    _ensure_loaded()

    if _load_error:
        return {
            "available": False,
            "status": "load_failed",
            "label": None,
            "confidence": None,
            "reasons": [f"Vision model failed to load: {_load_error}"],
            "modelVersion": None,
        }

    if _model is None:
        return {
            "available": False,
            "status": "unavailable",
            "label": None,
            "confidence": None,
            "reasons": [
                "No pretrained vision model is present under models/pretrained/. "
                "This is the expected state in this prototype — see README.md."
            ],
            "modelVersion": MODEL_VERSION_UNAVAILABLE,
        }

    img = image_utils.safe_open_image(image_path)
    if img is None:
        return {
            "available": False,
            "status": "invalid_image",
            "label": None,
            "confidence": None,
            "reasons": [f"'{image_path}' could not be read as a valid image."],
            "modelVersion": None,
        }

    try:
        label, confidence = _model.predict(img)
        return {
            "available": True,
            "status": "ok",
            "label": label,
            "confidence": round(float(confidence), 4),
            "reasons": [f"Model predicted '{label}' with confidence {float(confidence):.2f}."],
            "modelVersion": getattr(_model, "version", "unknown"),
        }
    except Exception as e:
        return {
            "available": False,
            "status": "inference_failed",
            "label": None,
            "confidence": None,
            "reasons": [f"Inference failed: {e}"],
            "modelVersion": getattr(_model, "version", None),
        }
