from __future__ import annotations

from pathlib import Path

import fitz
import openpyxl

from ocr_service.config import Settings
from ocr_service.service import DocumentService


class FakeEngine:
    @staticmethod
    def health():
        return {"ready": True, "paddleOcrPrimary": True}


def make_service() -> DocumentService:
    return DocumentService(Settings(), FakeEngine())


def test_excel_uses_pandas_and_keeps_table_rows(tmp_path: Path):
    path = tmp_path / "statement.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "流水"
    sheet.append(["日期", "摘要", "金额"])
    sheet.append(["2026-08-02", "转账", 1000])
    workbook.save(path)

    result = make_service().extract(path, path.name, "auto")
    item = result["sections"][0]
    assert item["method"] == "pandas"
    assert item["metadata"]["ocrUsed"] is False
    assert item["tableRows"][1] == ["2026-08-02", "转账", "1000"]


def test_native_pdf_uses_pdfplumber(tmp_path: Path):
    path = tmp_path / "native.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Computer generated PDF statement amount 1000.00")
    document.save(path)
    document.close()

    result = make_service().extract(path, path.name, "auto")
    item = result["sections"][0]
    assert item["method"] == "pdfplumber-text"
    assert item["metadata"]["pdfRoute"] == "native-page"
