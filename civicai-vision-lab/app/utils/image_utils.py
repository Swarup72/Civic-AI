"""
Shared, dependency-light image I/O helpers. Nothing in this file ever raises
on a bad/missing/corrupt file — every function returns None on failure, and
every caller is expected to handle that explicitly. This mirrors (but does
not import) the general engineering discipline of "never trust a file blindly"
used elsewhere in the broader CivicAI product line, reimplemented here from
scratch for this standalone prototype.
"""
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
import cv2
from PIL import Image, UnidentifiedImageError


def read_bytes(path: str) -> Optional[bytes]:
    """Reads a file's raw bytes, or None if it doesn't exist / can't be read."""
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def decode_image_bytes(data: Optional[bytes]) -> Optional[Image.Image]:
    """Bytes -> a verified, loaded PIL Image, or None if the bytes are empty,
    truncated, or not a real image at all. Never trusts a file extension —
    only what Pillow can actually decode."""
    if not data:
        return None
    try:
        img = Image.open(BytesIO(data))
        img.verify()  # raises on truncation/corruption; consumes the buffer
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    try:
        img = Image.open(BytesIO(data))  # verify() invalidated the first handle - reopen
        img.load()
        return img
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def safe_open_image(path: str) -> Optional[Image.Image]:
    """Path -> a verified PIL Image, or None. Combines read_bytes + decode_image_bytes."""
    return decode_image_bytes(read_bytes(path))


def to_cv2_gray(data: Optional[bytes]) -> Optional[np.ndarray]:
    """Bytes -> a grayscale OpenCV/numpy array, or None if undecodable."""
    if not data:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    if arr.size == 0:
        return None
    return cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)


def to_cv2_color(data: Optional[bytes]) -> Optional[np.ndarray]:
    """Bytes -> a BGR OpenCV/numpy array, or None if undecodable."""
    if not data:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    if arr.size == 0:
        return None
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)
