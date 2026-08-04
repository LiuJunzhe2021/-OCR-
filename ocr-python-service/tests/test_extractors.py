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


def test_excel_statement_is_normalized_classified_and_validated(tmp_path: Path):
    path = tmp_path / "statement.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["中国建设银行 对公账户流水"])
    sheet.append(["户名：示例科技有限公司 账号：6217000012345678901"])
    sheet.append(["交易日期", "摘要", "对方户名", "支出金额", "收入金额", "余额"])
    sheet.append(["2026-08-01", "销售回款", "客户甲", "", 1000, 5000])
    sheet.append(["2026/08/02", "采购货款", "供应商乙", 200, "", 4800])
    sheet["G4"] = "=E4-D4"
    workbook.save(path)

    result = make_service().extract(path, path.name, "auto")

    assert result["statement"]["bankName"] == "中国建设银行"
    assert result["statement"]["accountNumber"] == "6217000012345678901"
    assert result["statement"]["accountType"] == "对公"
    assert result["summary"]["transactionCount"] == 2
    assert result["transactions"][0]["category"] == "销售回款"
    assert result["transactions"][0]["amount"] == 1000.0
    assert result["transactions"][1]["amount"] == -200.0
    assert result["validation"]["formulaCount"] == 1
    assert any(issue["code"] == "FORMULA_DETECTED" for issue in result["validation"]["issues"])
