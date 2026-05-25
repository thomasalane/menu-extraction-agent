from __future__ import annotations

import io

import numpy as np
from PIL import Image

from config import (
    BLUR_THRESHOLD_ERROR,
    BLUR_THRESHOLD_WARNING,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_SIZE_MB,
    SUPPORTED_FORMATS,
)

__all__ = [
    "BLUR_THRESHOLD_ERROR",
    "BLUR_THRESHOLD_WARNING",
    "validate_image",
    "compute_blur_score",
    "prepare_for_api",
    "make_thumbnail",
]


def validate_image(file_bytes: bytes) -> tuple[bool, str]:
    if len(file_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        return False, f"Arquivo excede o limite de {MAX_IMAGE_SIZE_MB}MB."
    try:
        img = Image.open(io.BytesIO(file_bytes))
        fmt = (img.format or "").upper()
        allowed = {f.upper() for f in SUPPORTED_FORMATS} | {"JPEG"}
        if fmt not in allowed:
            return False, f"Formato não suportado: {fmt}. Use JPEG, PNG ou WEBP."
        return True, ""
    except Exception as exc:
        return False, f"Não foi possível abrir a imagem: {exc}"


def compute_blur_score(file_bytes: bytes) -> float:
    img = Image.open(io.BytesIO(file_bytes)).convert("L")
    arr = np.array(img, dtype=np.float32)

    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)

    try:
        from scipy.signal import convolve2d
        convolved = convolve2d(arr, kernel, mode="valid")
    except ImportError:
        # Fallback: pixel-difference variance when scipy is unavailable
        convolved = arr[1:, :] - arr[:-1, :]

    return float(np.var(convolved))


def prepare_for_api(file_bytes: bytes) -> tuple[bytes, str]:
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_IMAGE_DIMENSION:
        ratio = MAX_IMAGE_DIMENSION / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def make_thumbnail(file_bytes: bytes, max_width: int = 500) -> bytes:
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    w, h = img.size
    if w > max_width:
        img = img.resize((max_width, int(h * max_width / w)), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()
