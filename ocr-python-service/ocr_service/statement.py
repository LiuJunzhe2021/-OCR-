from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


HEADER_ALIASES = {
    "date": ("交易日期", "交易日", "记账日期", "入账日期", "发生日期", "日期"),
    "time": ("交易时间", "交易时刻", "时间"),
    "description": ("摘要", "用途", "交易摘要", "附言", "备注", "交易说明"),
    "transactionNature": ("交易性质", "交易类型", "业务类型", "交易类别"),
    "counterparty": ("对方户名", "对方账户名称", "对方名称", "交易对手", "收款人", "付款人", "收/付方名称", "收付方名称"),
    "counterpartyAccount": ("对方账号", "对方账户", "收款账号", "付款账号", "收/付方帐号", "收/付方账号", "收付方帐号"),
    "debit": ("支出金额", "借方发生额", "借方金额", "付款金额", "支出"),
    "credit": ("收入金额", "贷方发生额", "贷方金额", "收款金额", "收入"),
    "amount": ("交易金额", "发生额", "金额"),
    "direction": ("收支方向", "借贷标志", "交易方向", "借贷方向"),
    "balance": ("账户余额", "交易后余额", "余额"),
    "currency": ("币种", "货币"),
}

BANKS = (
    "中国工商银行", "中国农业银行", "中国银行", "中国建设银行", "交通银行",
    "招商银行", "浦发银行", "中信银行", "中国民生银行", "兴业银行",
    "中国光大银行", "平安银行", "华夏银行", "广发银行", "邮储银行",
)

CATEGORIES = (
    ("工资薪酬", ("工资", "薪资", "奖金", "社保", "公积金")),
    ("税费", ("税", "税务", "国库", "海关")),
    ("采购付款", ("采购", "货款", "材料", "供应商")),
    ("销售回款", ("销售", "回款", "收款", "货款收入")),
    ("费用报销", ("报销", "差旅", "餐费", "办公费")),
    ("银行费用", ("手续费", "服务费", "账户管理费")),
    ("利息", ("利息", "结息")),
    ("内部转账", ("内部转账", "同名转账", "资金归集")),
    ("融资", ("贷款", "借款", "放款", "还本", "还息")),
)


def _compact(value: Any) -> str:
    return re.sub(r"[\s:：()（）/\\_-]+", "", str(value or "")).lower()


def _field_for(value: Any) -> str | None:
    text = _compact(value)
    if not text:
        return None
    for field, aliases in HEADER_ALIASES.items():
        if any(_compact(alias) == text or _compact(alias) in text for alias in aliases):
            return field
    return None


def _decimal(value: Any) -> Decimal | None:
    text = str(value or "").strip().replace(",", "").replace("￥", "").replace("¥", "")
    if not text or text in {"-", "--", "/"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        number = Decimal(text)
        return -number if negative else number
    except InvalidOperation:
        match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
        if not match:
            return None
        try:
            return Decimal(match.group())
        except InvalidOperation:
            return None


def _money(value: Decimal | None) -> float | None:
    return None if value is None else float(value.quantize(Decimal("0.01")))


def _date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"[年月/.]", "-", text).replace("日", "")
    text = re.sub(r"\s+", " ", text)
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d", "%y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    match = re.search(r"(20\d{2})[-](\d{1,2})[-](\d{1,2})", text)
    if match:
        try:
            return datetime(*map(int, match.groups())).date().isoformat()
        except ValueError:
            return None
    return None


def _category(description: str, counterparty: str) -> str:
    text = f"{description} {counterparty}".lower()
    for category, keywords in CATEGORIES:
        if any(keyword.lower() in text for keyword in keywords):
            return category
    return "其他"


def _statement_info(text: str, source_name: str = "") -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", text)
    bank = next((name for name in BANKS if name in source_name), "")
    if not bank:
        bank = next((name for name in BANKS if name in normalized), "")
    account_match = re.search(r"(?:银行账号|银行帐号|账号|帐号|账户|卡号)\s*[：:]?\s*([0-9][0-9*-]{7,30})", normalized)
    account = re.sub(r"\D", "", account_match.group(1)) if account_match else ""
    entity_match = re.search(
        r"(?:户名|账户名称|客户名称|单位名称|公司名称)\s*[：:]?\s*([^\n\t]{2,50}?)(?=\s+(?:银行账号|银行帐号|账号|帐号|账户|开户行|银行码|币种)[：:]?|$)",
        normalized,
    )
    entity = entity_match.group(1).strip() if entity_match else ""
    period_start = re.search(r"查询开始日期\s*[：:]?\s*(20\d{6})", normalized)
    period_end = re.search(r"查询结束日期\s*[：:]?\s*(20\d{6})", normalized)
    company_tokens = ("公司", "集团", "企业", "中心", "事务所", "委员会", "大学", "医院")
    return {
        "entityName": entity,
        "bankName": bank,
        "accountNumber": account,
        "accountType": "对公" if any(token in entity for token in company_tokens) else ("对私" if entity else "未知"),
        "currency": "CNY",
        "periodStart": _date(period_start.group(1)) if period_start else None,
        "periodEnd": _date(period_end.group(1)) if period_end else None,
    }


def _issues(transaction: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not transaction["date"]:
        issues.append({"code": "INVALID_DATE", "level": "ERROR", "message": "交易日期缺失或格式无效"})
    debit, credit, amount = transaction["debit"], transaction["credit"], transaction["amount"]
    if debit is None and credit is None and amount is None:
        issues.append({"code": "MISSING_AMOUNT", "level": "ERROR", "message": "未识别到交易金额"})
    if debit is not None and credit is not None and debit != 0 and credit != 0:
        issues.append({"code": "DEBIT_CREDIT_CONFLICT", "level": "ERROR", "message": "收入和支出不能同时非零"})
    if any(value is not None and value < 0 for value in (debit, credit)):
        issues.append({"code": "NEGATIVE_SPLIT_AMOUNT", "level": "WARNING", "message": "收入/支出列存在负数"})
    if not transaction["description"]:
        issues.append({"code": "MISSING_DESCRIPTION", "level": "WARNING", "message": "交易摘要为空"})
    return issues


def normalize_statement(sections: list[dict[str, Any]], full_text: str, source_name: str = "") -> dict[str, Any]:
    transactions: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    detected_tables = 0
    formula_count = 0
    statement = _statement_info(full_text, source_name)

    for section_index, section in enumerate(sections):
        rows = section.get("tableRows") or []
        formula_count += len(section.get("metadata", {}).get("formulaCells", []))
        best_header: tuple[int, dict[int, str]] | None = None
        for row_index, row in enumerate(rows[:30]):
            mapping: dict[int, str] = {}
            for column, value in enumerate(row):
                field = _field_for(value)
                # 银行模板常同时包含“摘要/业务摘要/其它摘要”等近义列。
                # 优先保留最靠前的主字段，避免后面的空列覆盖有效值。
                if field and field not in mapping.values():
                    mapping[column] = field
            if len(set(mapping.values())) >= 2 and (best_header is None or len(mapping) > len(best_header[1])):
                best_header = (row_index, mapping)
        if best_header is None:
            continue
        detected_tables += 1
        header_index, mapping = best_header
        for source_row, row in enumerate(rows[header_index + 1 :], header_index + 2):
            values = {field: (row[column] if column < len(row) else "") for column, field in mapping.items()}
            if not any(str(value).strip() for value in values.values()):
                continue
            parsed_date = _date(values.get("date"))
            debit = _decimal(values.get("debit"))
            credit = _decimal(values.get("credit"))
            amount = _decimal(values.get("amount"))
            direction_text = str(values.get("direction", ""))
            if debit is None and credit is None and amount is not None:
                if any(token in direction_text for token in ("支", "借", "付", "出")) or amount < 0:
                    debit, credit = abs(amount), None
                else:
                    credit, debit = abs(amount), None
            if credit is not None and credit != 0:
                signed_amount = credit
            elif debit is not None and debit != 0:
                signed_amount = -debit
            elif amount is not None:
                signed_amount = amount
            else:
                signed_amount = credit if credit is not None else (-debit if debit is not None else None)
            description = str(values.get("description", "")).strip()
            counterparty = str(values.get("counterparty", "")).strip()
            transaction = {
                "id": f"S{section_index + 1}-R{source_row}",
                # 六个跨模板统一字段。源材料不存在时保持空值。
                "transactionDate": parsed_date,
                "party": statement["entityName"],
                "transactionNature": str(values.get("transactionNature", "")).strip(),
                "remarks": description,
                "date": parsed_date,
                "time": str(values.get("time", "")).strip(),
                "description": description,
                "counterparty": counterparty,
                "counterpartyAccount": re.sub(r"\s", "", str(values.get("counterpartyAccount", ""))),
                "debit": _money(debit),
                "credit": _money(credit),
                "amount": _money(signed_amount),
                "direction": "收入" if signed_amount is not None and signed_amount >= 0 else "支出",
                "balance": _money(_decimal(values.get("balance"))),
                "currency": str(values.get("currency", "")).strip() or "CNY",
                "category": _category(description, counterparty),
                "source": section.get("source", ""),
                "sourceRow": source_row,
                "originalRow": [str(item) for item in row],
            }
            transaction["validations"] = _issues(transaction)
            transaction["manualReviewRequired"] = bool(transaction["validations"])
            transactions.append(transaction)

    if not statement["accountNumber"]:
        validation_issues.append({"code": "ACCOUNT_NOT_FOUND", "level": "WARNING", "message": "未识别到账户号码"})
    elif not 8 <= len(statement["accountNumber"]) <= 30:
        validation_issues.append({"code": "INVALID_ACCOUNT", "level": "ERROR", "message": "账户号码长度异常"})
    if detected_tables == 0:
        validation_issues.append({"code": "HEADER_NOT_FOUND", "level": "ERROR", "message": "未找到可识别的流水表头"})
    if formula_count:
        validation_issues.append({"code": "FORMULA_DETECTED", "level": "WARNING", "message": f"原文件检测到 {formula_count} 个公式单元格"})

    previous = None
    for transaction in transactions:
        balance, amount = transaction["balance"], transaction["amount"]
        if previous is not None and balance is not None and amount is not None:
            if abs((previous + amount) - balance) > 0.02:
                issue = {"code": "BALANCE_MISMATCH", "level": "WARNING", "message": "余额与上一笔收支不连续"}
                transaction["validations"].append(issue)
                transaction["manualReviewRequired"] = True
        if balance is not None:
            previous = balance

    transaction_issue_count = sum(len(item["validations"]) for item in transactions)
    return {
        "statement": statement,
        "transactions": transactions,
        "validation": {
            "status": "PASS" if not validation_issues and transaction_issue_count == 0 else "REVIEW",
            "issues": validation_issues,
            "transactionIssueCount": transaction_issue_count,
            "formulaCount": formula_count,
            "detectedTableCount": detected_tables,
        },
    }
