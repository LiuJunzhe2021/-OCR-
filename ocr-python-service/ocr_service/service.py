from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .extractors import IMAGE_EXTENSIONS, Extractors
from .ocr_engine import MultiModelOCREngine
from .statement import normalize_statement


class DocumentService:
    supported_extensions = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", *IMAGE_EXTENSIONS
    }

    def __init__(
        self,
        settings: Settings | None = None,
        engine: MultiModelOCREngine | None = None,
    ):
        self.settings = settings or Settings.from_env()
        self.engine = engine or MultiModelOCREngine(self.settings)
        self.extractors = Extractors(self.settings, self.engine)

    def health(self) -> dict[str, Any]:
        return {
            "service": "ocr-python-service",
            "status": "UP",
            "parsers": {"excel": "pandas", "pdf": "pdfplumber"},
            "ocr": self.engine.health(),
        }

    def extract(self, path: Path, original_name: str, mode: str) -> dict[str, Any]:
        suffix = path.suffix.lower()
        if suffix in {".xls", ".xlsx"}:
            sections, warnings = self.extractors.excel(path)
        elif suffix == ".pdf":
            sections, warnings = self.extractors.pdf(path, mode)
        elif suffix in {".doc", ".docx"}:
            sections, warnings = self.extractors.word(path)
        else:
            sections, warnings = self.extractors.image(path)

        full_text = "\n\n".join(
            f"===== {item['source']} | {item['method']} =====\n{item['text']}"
            for item in sections
        )
        review_count = sum(
            bool(item["metadata"].get("manualReviewRequired"))
            for item in sections
        )
        normalized = normalize_statement(sections, full_text, original_name)
        transaction_review_count = sum(
            bool(item["manualReviewRequired"])
            for item in normalized["transactions"]
        )
        return {
            "originalFilename": original_name,
            "fileType": suffix.lstrip("."),
            "mode": mode,
            "sections": sections,
            "warnings": warnings,
            "fullText": full_text,
            **normalized,
            "summary": {
                "sectionCount": len(sections),
                "manualReviewCount": review_count + transaction_review_count,
                "transactionCount": len(normalized["transactions"]),
                "transactionReviewCount": transaction_review_count,
                "primaryOcrModel": "paddleocr",
            },
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
