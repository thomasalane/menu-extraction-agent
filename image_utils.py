from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps

from config import (
    BLUR_THRESHOLD,
    BRIGHTNESS_BRIGHT,
    BRIGHTNESS_DARK,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_SIZE_MB,
    MIN_IMAGE_DIMENSION,
    SUPPORTED_FORMATS,
)

__all__ = [
    "validate_image",
    "analyze_quality",
    "QualityReport",
    "prepare_for_api",
    "make_thumbnail",
]


def _open_oriented(file_bytes: bytes) -> Image.Image:
    """Abre a imagem respeitando a orientação EXIF (fotos de celular)."""
    img = Image.open(io.BytesIO(file_bytes))
    return ImageOps.exif_transpose(img)


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


@dataclass
class QualityReport:
    width: int = 0
    height: int = 0
    blur_score: float = 0.0
    brightness: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.warnings


def analyze_quality(file_bytes: bytes) -> QualityReport:
    """Heurísticas de qualidade: resolução, desfoque e iluminação.

    Gera avisos (não bloqueia) para o usuário decidir se vale reenviar
    uma foto melhor antes de gastar uma chamada de API.
    """
    img = _open_oriented(file_bytes).convert("L")
    w, h = img.size
    report = QualityReport(width=w, height=h)

    if min(w, h) < MIN_IMAGE_DIMENSION:
        report.warnings.append(
            f"Resolução baixa ({w}×{h}px). Textos pequenos podem não ser lidos — "
            f"ideal é o menor lado ter pelo menos {MIN_IMAGE_DIMENSION}px."
        )

    # Reduz para tamanho fixo antes de medir, para o limiar de blur ser comparável
    # entre imagens de resoluções diferentes
    if max(w, h) > 1200:
        ratio = 1200 / max(w, h)
        img = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)

    arr = np.asarray(img, dtype=np.float32)

    # Variância do Laplaciano: baixo = poucas bordas nítidas = provável desfoque
    if arr.shape[0] > 2 and arr.shape[1] > 2:
        lap = (
            arr[:-2, 1:-1] + arr[2:, 1:-1] + arr[1:-1, :-2] + arr[1:-1, 2:]
            - 4 * arr[1:-1, 1:-1]
        )
        report.blur_score = float(lap.var())
        if report.blur_score < BLUR_THRESHOLD:
            report.warnings.append(
                "Imagem possivelmente desfocada ou sem nitidez. "
                "A extração pode ter baixa confiança."
            )

    report.brightness = float(arr.mean())
    if report.brightness < BRIGHTNESS_DARK:
        report.warnings.append("Imagem muito escura. Tente uma foto com mais iluminação.")
    elif report.brightness > BRIGHTNESS_BRIGHT:
        report.warnings.append("Imagem estourada (muito clara). Evite flash ou luz direta.")

    return report


def prepare_for_api(file_bytes: bytes) -> tuple[bytes, str]:
    img = _open_oriented(file_bytes).convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_IMAGE_DIMENSION:
        ratio = MAX_IMAGE_DIMENSION / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def make_thumbnail(file_bytes: bytes, max_width: int = 500) -> bytes:
    img = _open_oriented(file_bytes).convert("RGB")
    w, h = img.size
    if w > max_width:
        img = img.resize((max_width, int(h * max_width / w)), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()
