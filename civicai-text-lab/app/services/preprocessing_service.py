"""
Safe text normalization. Every function here is total (never raises) and
handles empty/whitespace-only/None input explicitly rather than letting a
downstream vectorizer or classifier choke on it.
"""
import re
import unicodedata
from typing import Optional

# Collapses any run of whitespace (space, tab, newline, non-breaking space,
# ...) to a single ASCII space.
_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)

# Keeps letters/digits/basic sentence punctuation; drops control characters
# and stray symbols that add noise to a TF-IDF vocabulary without adding
# meaning (currency symbols, emoji, etc.) — never drops accented/non-Latin
# letters, only true punctuation/symbol/control categories.
_KEEP_CATEGORIES = {"L", "N", "Z"}  # Letter, Number, Separator(whitespace)
_KEEP_PUNCTUATION = set(".,!?-'\"")


def normalize_unicode(text: str) -> str:
    """NFKC normalization — folds visually-identical unicode variants (full-
    width digits, combining accents, etc.) to one canonical form, so the
    vectorizer's vocabulary isn't fragmented by encoding differences."""
    return unicodedata.normalize("NFKC", text)


def strip_control_characters(text: str) -> str:
    """Drops non-printable control characters (categories starting 'C') while
    keeping everything else, including punctuation the tokenizer needs."""
    return "".join(ch for ch in text if not unicodedata.category(ch).startswith("C") or ch in "\n\t ")


def normalize_punctuation(text: str) -> str:
    """Keeps letters/digits/whitespace and a small set of sentence
    punctuation; replaces every other symbol with a space (never deletes
    without replacing, so 'word,,,word' doesn't become 'wordword')."""
    out_chars = []
    for ch in text:
        category = unicodedata.category(ch)[0]
        if category in _KEEP_CATEGORIES or ch in _KEEP_PUNCTUATION:
            out_chars.append(ch)
        else:
            out_chars.append(" ")
    return "".join(out_chars)


def collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_text(raw_text: Optional[str]) -> str:
    """The single entry point every caller should use. Always returns a
    string (possibly empty) — never raises, never returns None.

    Pipeline: unicode-normalize -> strip control chars -> lowercase ->
    normalize punctuation -> collapse whitespace -> strip.
    """
    if raw_text is None:
        return ""
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)

    text = normalize_unicode(raw_text)
    text = strip_control_characters(text)
    text = text.lower()
    text = normalize_punctuation(text)
    text = collapse_whitespace(text)
    return text


def is_effectively_empty(normalized_text: str) -> bool:
    """True for '', whitespace-only, or punctuation-only input — text with
    no actual word content to classify."""
    return len(re.sub(r"[^a-z0-9]", "", normalized_text)) == 0
