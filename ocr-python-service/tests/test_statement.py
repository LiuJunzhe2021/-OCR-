from ocr_service.statement import normalize_statement


def test_missing_header_requires_review():
    result = normalize_statement(
        [{"source": "扫描件", "tableRows": [["无法", "识别"]], "metadata": {}}],
        "普通文本",
    )
    assert result["transactions"] == []
    assert result["validation"]["status"] == "REVIEW"
    assert result["validation"]["issues"][0]["code"] == "ACCOUNT_NOT_FOUND"


def test_balance_mismatch_marks_transaction_for_review():
    sections = [{
        "source": "流水",
        "metadata": {},
        "tableRows": [
            ["日期", "摘要", "收入", "余额"],
            ["2026-01-01", "销售回款", "100", "1000"],
            ["2026-01-02", "销售回款", "100", "1300"],
        ],
    }]
    result = normalize_statement(sections, "账号：1234567890")
    second = result["transactions"][1]
    assert second["manualReviewRequired"] is True
    assert any(issue["code"] == "BALANCE_MISMATCH" for issue in second["validations"])


def test_cmb_template_uses_transaction_day_and_statement_period():
    sections = [{
        "source": "Excel工作表：Sheet1",
        "metadata": {},
        "tableRows": [
            ["公司名称", "小米科技有限责任公司", "银行帐号", "6226100110012002"],
            ["查询开始日期", "20210101", "查询结束日期", "20211231"],
            ["交易日", "交易时间", "借方金额", "贷方金额", "余额", "摘要", "收/付方名称", "收/付方帐号"],
            ["20210112", "080024", "0", "1000000", "1000000", "划款-往来款", "客户甲", "62260001"],
            ["20210113", "154940", "41186.38", "0", "958813.62", "保险费", "保险公司", "62260002"],
        ],
    }]
    result = normalize_statement(sections, "\n".join("\t".join(row) for row in sections[0]["tableRows"]), "招商银行_2021.xlsx")
    assert result["statement"]["bankName"] == "招商银行"
    assert result["statement"]["entityName"] == "小米科技有限责任公司"
    assert result["statement"]["accountNumber"] == "6226100110012002"
    assert result["statement"]["periodStart"] == "2021-01-01"
    assert result["statement"]["periodEnd"] == "2021-12-31"
    assert result["transactions"][0]["date"] == "2021-01-12"
    assert result["transactions"][0]["transactionDate"] == "2021-01-12"
    assert result["transactions"][0]["party"] == "小米科技有限责任公司"
    assert result["transactions"][0]["transactionNature"] == ""
    assert result["transactions"][0]["remarks"] == "划款-往来款"
    assert result["transactions"][0]["time"] == "080024"
    assert result["transactions"][0]["counterparty"] == "客户甲"
    assert result["transactions"][0]["amount"] == 1000000.0
    assert result["transactions"][1]["amount"] == -41186.38
