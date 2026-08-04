from __future__ import annotations

import importlib
import importlib.util
import json
import re
import shutil
import threading
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output

from .config import Settings
from .models import Candidate, Recognition


class MultiModelOCREngine:
    """PaddleOCR主识别、Tesseract复核、EasyOCR按需仲裁。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        self._paddle = None
        self._easy = None
        self._paddle_lock = threading.Lock()
        self._easy_lock = threading.Lock()

    def health(self) -> dict[str, Any]:
        paddle_installed = (
            importlib.util.find_spec("paddleocr") is not None
            and importlib.util.find_spec("paddle") is not None
        )
        tesseract = self.settings.tesseract_cmd or shutil.which("tesseract")
        return {
            "paddleOcrInstalled": paddle_installed,
            "paddleOcrPrimary": True,
            "tesseractInstalled": bool(tesseract),
            "easyOcrInstalled": importlib.util.find_spec("easyocr") is not None,
            "ready": paddle_installed,
        }

    @staticmethod
    def _quality(text: str, confidence: float) -> float:
        compact = [char for char in text if not char.isspace()]
        if not compact:
            return 0.0
        valid = sum(
            char.isalnum()
            or "\u4e00" <= char <= "\u9fff"
            or char in ".,，。:：/+-()%（）"
            for char in compact
        ) / len(compact)
        length_score = min(1.0, len(compact) / 40.0)
        return confidence * 0.65 + valid * 0.25 + length_score * 0.10

    @staticmethod
    def _similarity(first: str, second: str) -> float:
        normalize = lambda value: re.sub(r"\s+", "", value).lower()
        return SequenceMatcher(None, normalize(first), normalize(second)).ratio()

    def _get_paddle(self):
        if self._paddle is not None:
            return self._paddle
        with self._paddle_lock:
            if self._paddle is None:
                if importlib.util.find_spec("paddleocr") is None:
                    raise RuntimeError("未安装PaddleOCR，请安装requirements.txt")
                module = importlib.import_module("paddleocr")
                self._paddle = module.PaddleOCR(
                    lang=self.settings.paddle_language,
                    device=self.settings.paddle_device,
                    enable_mkldnn=False,
                    use_doc_orientation_classify=(
                        self.settings.paddle_doc_orientation
                    ),
                    use_doc_unwarping=self.settings.paddle_doc_unwarping,
                    use_textline_orientation=(
                        self.settings.paddle_textline_orientation
                    ),
                )
        return self._paddle

    def _get_easy(self):
        if self._easy is not None:
            return self._easy
        with self._easy_lock:
            if self._easy is None:
                if importlib.util.find_spec("easyocr") is None:
                    raise RuntimeError("未安装EasyOCR")
                module = importlib.import_module("easyocr")
                languages = [
                    item.strip()
                    for item in self.settings.easyocr_languages.split(",")
                    if item.strip()
                ]
                self._easy = module.Reader(
                    languages, gpu=self.settings.easyocr_gpu, verbose=False
                )
        return self._easy

    @staticmethod
    def _payload(result: Any) -> dict[str, Any]:
        value = getattr(result, "json", result)
        if callable(value):
            value = value()
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            return {}
        return value.get("res", value)

    @staticmethod
    def _ordered_text(entries: list[tuple[Any, str, float]]) -> tuple[str, float]:
        items = []
        weighted = []
        for index, (box, text, confidence) in enumerate(entries):
            text = str(text).strip()
            if not text:
                continue
            try:
                points = list(box)
                left = min(float(point[0]) for point in points)
                top = min(float(point[1]) for point in points)
                bottom = max(float(point[1]) for point in points)
            except (TypeError, ValueError, IndexError):
                left, top, bottom = 0.0, index * 20.0, index * 20.0 + 10.0
            items.append(
                {
                    "text": text,
                    "left": left,
                    "y": (top + bottom) / 2,
                    "height": max(1.0, bottom - top),
                }
            )
            weighted.append((float(confidence), max(1, len(text))))

        tolerance = max(8.0, median([item["height"] for item in items]) * 0.65) if items else 8.0
        lines: list[dict[str, Any]] = []
        for item in sorted(items, key=lambda value: (value["y"], value["left"])):
            line = next(
                (line for line in lines if abs(line["y"] - item["y"]) <= tolerance),
                None,
            )
            if line is None:
                lines.append({"y": item["y"], "items": [item]})
            else:
                line["items"].append(item)
                line["y"] = sum(value["y"] for value in line["items"]) / len(line["items"])
        text = "\n".join(
            " ".join(value["text"] for value in sorted(line["items"], key=lambda value: value["left"]))
            for line in sorted(lines, key=lambda value: value["y"])
        )
        confidence = (
            sum(value * weight for value, weight in weighted) / sum(weight for _, weight in weighted)
            if weighted
            else 0.0
        )
        return text, confidence

    def _run_paddle(self, image: Image.Image) -> Candidate:
        reader = self._get_paddle()
        raw = list(reader.predict(input=np.asarray(image.convert("RGB"))))
        entries = []
        for result in raw:
            payload = self._payload(result)
            texts = list(payload.get("rec_texts", []))
            scores_raw = payload.get("rec_scores")
            boxes_raw = payload.get("rec_polys")
            if boxes_raw is None:
                boxes_raw = payload.get("rec_boxes")
            scores = list(scores_raw) if scores_raw is not None else []
            boxes = list(boxes_raw) if boxes_raw is not None else []
            for index, text in enumerate(texts):
                entries.append(
                    (
                        boxes[index] if index < len(boxes) else None,
                        text,
                        float(scores[index]) if index < len(scores) else 0.0,
                    )
                )
        text, confidence = self._ordered_text(entries)
        return Candidate("paddleocr", text, confidence, self._quality(text, confidence))

    def _run_tesseract(self, image: Image.Image) -> Candidate:
        data = pytesseract.image_to_data(
            image,
            lang=self.settings.tesseract_lang,
            config="--oem 3 --psm 6",
            output_type=Output.DICT,
        )
        entries = []
        total = len(data.get("text", []))
        for index in range(total):
            text = str(data["text"][index]).strip()
            try:
                score = max(0.0, float(data["conf"][index]) / 100.0)
            except (TypeError, ValueError):
                score = 0.0
            if text:
                left = float(data["left"][index])
                top = float(data["top"][index])
                width = float(data["width"][index])
                height = float(data["height"][index])
                box = [[left, top], [left + width, top], [left + width, top + height], [left, top + height]]
                entries.append((box, text, score))
        text, confidence = self._ordered_text(entries)
        return Candidate("tesseract", text, confidence, self._quality(text, confidence))

    def _run_easy(self, image: Image.Image) -> Candidate:
        results = self._get_easy().readtext(np.asarray(image.convert("RGB")), detail=1)
        entries = [(box, text, float(score)) for box, text, score in results]
        text, confidence = self._ordered_text(entries)
        return Candidate("easyocr", text, confidence, self._quality(text, confidence))

    def recognize(self, source: Image.Image | Path) -> Recognition:
        image = source.copy() if isinstance(source, Image.Image) else Image.open(source)
        try:
            image = ImageOps.exif_transpose(image).convert("RGB")
            warnings: list[str] = []
            paddle = self._run_paddle(image)
            candidates = [paddle]
            tesseract = None

            if self.settings.verify_with_tesseract:
                try:
                    tesseract = self._run_tesseract(image)
                    candidates.append(tesseract)
                except Exception:
                    warnings.append("tesseract_unavailable")

            similarity = (
                self._similarity(paddle.text, tesseract.text)
                if tesseract is not None
                else None
            )
            weak = (
                paddle.confidence < self.settings.min_confidence
                or len(paddle.text.strip()) < 12
                or (
                    similarity is not None
                    and similarity < self.settings.min_similarity
                )
            )
            if weak and self.settings.easyocr_fallback:
                try:
                    candidates.append(self._run_easy(image))
                except Exception:
                    warnings.append("easyocr_unavailable")

            selected = max(candidates, key=lambda item: item.quality_score)
            manual_review = (
                selected.confidence < self.settings.min_confidence
                or (
                    similarity is not None
                    and similarity < self.settings.min_similarity
                )
            )
            return Recognition(
                selected.text,
                selected.engine,
                selected.confidence,
                selected.quality_score,
                candidates,
                manual_review,
                similarity,
                warnings,
            )
        finally:
            image.close()
