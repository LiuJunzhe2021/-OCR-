from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    paddle_language: str = "ch"
    paddle_device: str = "cpu"
    paddle_doc_orientation: bool = True
    paddle_doc_unwarping: bool = False
    paddle_textline_orientation: bool = True
    tesseract_cmd: str = ""
    tesseract_lang: str = "chi_sim+eng"
    easyocr_languages: str = "ch_sim,en"
    easyocr_gpu: bool = False
    verify_with_tesseract: bool = True
    easyocr_fallback: bool = True
    min_confidence: float = 0.85
    min_similarity: float = 0.90
    pdf_text_threshold: int = 20
    pdf_dpi: int = 300
    max_upload_mb: int = 50

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            paddle_language=os.getenv("PADDLEOCR_LANGUAGE", "ch"),
            paddle_device=os.getenv("PADDLEOCR_DEVICE", "cpu"),
            paddle_doc_orientation=env_bool("PADDLEOCR_DOC_ORIENTATION", True),
            paddle_doc_unwarping=env_bool("PADDLEOCR_DOC_UNWARPING", False),
            paddle_textline_orientation=env_bool(
                "PADDLEOCR_TEXTLINE_ORIENTATION", True
            ),
            tesseract_cmd=os.getenv("TESSERACT_CMD", "").strip(),
            tesseract_lang=os.getenv("TESSERACT_LANG", "chi_sim+eng"),
            easyocr_languages=os.getenv("EASYOCR_LANGUAGES", "ch_sim,en"),
            easyocr_gpu=env_bool("EASYOCR_GPU", False),
            verify_with_tesseract=env_bool("VERIFY_WITH_TESSERACT", True),
            easyocr_fallback=env_bool("EASYOCR_FALLBACK", True),
            min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.85")),
            min_similarity=float(os.getenv("OCR_MIN_SIMILARITY", "0.90")),
            pdf_text_threshold=int(os.getenv("PDF_TEXT_THRESHOLD", "20")),
            pdf_dpi=int(os.getenv("PDF_OCR_DPI", "300")),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "50")),
        )
