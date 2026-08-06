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
    assert result["transactions"][0]["transactionNature"] == "其他"
    assert result["transactions"][0]["remarks"] == "划款-往来款"
    assert result["transactions"][0]["time"] == "080024"
    assert result["transactions"][0]["counterparty"] == "客户甲"
    assert result["transactions"][0]["amount"] == 1000000.0
    assert result["transactions"][1]["amount"] == -41186.38


def test_report_summary_is_not_misread_as_transaction_detail():
    sections = [{
        "source": "Excel工作表：报告",
        "metadata": {},
        "tableRows": [
            ["前10大流入方"],
            ["对方名称", "流入总额", "流入笔数", "2024/01"],
            ["客户甲", "100000", "5", "20000"],
            ["账户流水"],
            ["交易日期", "摘要", "对方名称", "交易金额", "收支方向"],
            ["2024-01-02", "采购材料", "供应商乙", "300", "支出"],
        ],
    }]
    result = normalize_statement(sections, "银行流水分析报告")
    assert len(result["detectedTables"]) == 2
    assert result["detectedTables"][0]["type"] == "counterparty_analysis"
    assert len(result["transactions"]) == 1
    assert result["transactions"][0]["amount"] == -300.0
    assert result["transactions"][0]["transactionNature"] == "采购付款"


def test_summary_tables_produce_shared_analysis_metrics():
    sections = [{"source": "Excel工作表：报告", "metadata": {}, "tableRows": [
        ["3.3.1", "流入"],
        ["本方名称", "2024/01", "2024/02"],
        ["甲公司", "100", "200"],
        ["3.3.2", "流出"],
        ["本方名称", "2024/01", "2024/02"],
        ["甲公司", "30", "50"],
        ["3.4.1", "流入"],
        ["分类", "合计", "2024/01"],
        ["经营收入", "300", "100"],
    ]}]
    result = normalize_statement(sections, "银行流水尽调报告")
    assert result["analysis"]["totalInflow"] == 300
    assert result["analysis"]["totalOutflow"] == 80
    assert result["analysis"]["monthly"][0] == {"month": "2024-01", "inflow": 100.0, "outflow": 30.0}
    assert result["analysis"]["categories"][0]["name"] == "经营收入"


def test_account_table_with_counterparty_availability_is_not_misclassified():
    sections = [{"source": "Excel工作表：报告", "metadata": {}, "tableRows": [
        ["甲公司"],
        ["账号", "所属银行", "数据时间范围", "余额不连续", "对方名称", "交易信息"],
        ["622600001234", "招商银行", "2024.01.01~2024.12.31", "无", "有", "有"],
    ]}]
    result = normalize_statement(sections, "尽调报告")
    assert result["detectedTables"][0]["type"] == "account_summary"
    assert result["accounts"][0]["accountNumber"] == "622600001234"
    assert result["statement"]["periodStart"] == "2024-01-01"
