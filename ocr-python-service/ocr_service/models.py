from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Candidate:
    engine: str
    text: str
    confidence: float
    quality_score: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = round(self.confidence, 4)
        data["quality_score"] = round(self.quality_score, 4)
        return data


@dataclass
class Recognition:
    text: str
    engine: str
    confidence: float
    quality_score: float
    candidates: list[Candidate]
    manual_review_required: bool
    similarity: float | None = None
    warnings: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "ocrEngine": self.engine,
            "confidence": round(self.confidence, 4),
            "qualityScore": round(self.quality_score, 4),
            "similarity": (
                None if self.similarity is None else round(self.similarity, 4)
            ),
            "manualReviewRequired": self.manual_review_required,
            "candidates": [item.to_dict() for item in self.candidates],
            "warnings": self.warnings,
        }
