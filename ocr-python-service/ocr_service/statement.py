from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


HEADER_ALIASES = {
    "date": ("交易日期", "交易日", "记账日期", "入账日期", "发生日期", "日期"),
    "time": ("交易时间", "交易时刻", "时间"),
    "description": ("摘要", "用途", "交易摘要", "业务摘要", "附言", "备注", "交易说明", "交易信息"),
    "transactionNature": ("交易性质", "交易类型", "业务类型", "交易类别"),
    "counterparty": ("对方户名", "对方账户名称", "对方名称", "交易对手", "交易对手方", "收款人", "付款人", "收/付方名称", "收付方名称"),
    "counterpartyAccount": ("对方账号", "对方账户", "收款账号", "付款账号", "收/付方帐号", "收/付方账号", "收付方帐号"),
    "debit": ("支出金额", "流出金额", "流出总额", "借方发生额", "借方金额", "付款金额", "支出", "流出"),
    "credit": ("收入金额", "流入金额", "流入总额", "贷方发生额", "贷方金额", "收款金额", "收入", "流入"),
    "amount": ("交易金额", "发生额", "金额"),
    "direction": ("收支方向", "借贷标志", "交易方向", "借贷方向"),
    "balance": ("账户余额", "交易后余额", "余额"),
    "currency": ("币种", "货币"),
}

# 用于识别“是不是交易流水”的最低语义要求。统计报表中也常出现流入/流出，
# 但没有逐笔交易日期，不能将它们伪装成流水记录。
MONEY_FIELDS = {"debit", "credit", "amount"}
DETAIL_FIELDS = {"description", "counterparty", "counterpartyAccount", "transactionNature"}

GENERIC_HEADER_WORDS = (
    "名称", "账号", "账户", "银行", "日期", "时间", "金额", "余额", "摘要",
    "类型", "分类", "方向", "合计", "占比", "笔数", "均值", "范围", "质量",
    "风险", "来源", "详情", "性质", "本方", "对方", "流入", "流出", "借方", "贷方",
)

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


def _header_mapping(row: list[Any]) -> dict[int, str]:
    """将任意银行模板的表头映射到统一交易字段。"""
    mapping: dict[int, str] = {}
    for column, value in enumerate(row):
        field = _field_for(value)
        if field and field not in mapping.values():
            mapping[column] = field
    return mapping


def _is_transaction_header(mapping: dict[int, str]) -> bool:
    fields = set(mapping.values())
    # 日期 + 金额是逐笔流水不可缺少的结构特征；再要求一个明细语义列，避免将
    # “月度流入/流出统计”误识别成交易流水。
    return "date" in fields and bool(fields & MONEY_FIELDS) and bool(fields & DETAIL_FIELDS)


def _looks_like_generic_header(row: list[Any]) -> bool:
    values = [str(value).strip() for value in row if str(value or "").strip()]
    if len(values) < 2:
        return False
    hits = sum(any(word in value for word in GENERIC_HEADER_WORDS) or bool(re.fullmatch(r"20\d{2}[/.-]\d{1,2}", value)) for value in values)
    numeric = sum(_decimal(value) is not None and not re.search(r"[\u4e00-\u9fff]", value) for value in values)
    return hits >= 2 and hits >= numeric


def _table_type(headers: list[str], title: str) -> str:
    text = " ".join([title, *headers])
    mapping = _header_mapping(headers)
    if _is_transaction_header(mapping):
        return "transaction_detail"
    counterparty_metrics = any(token in text for token in ("金额", "总额", "差额", "笔数", "构成", "占比"))
    if (("对方名称" in text and counterparty_metrics) or "对手方" in text or "流入方" in text or "流出方" in text):
        return "counterparty_analysis"
    if "分类" in text and ("金额" in text or "合计" in text):
        return "category_summary"
    if any(re.fullmatch(r"20\d{2}[/.-]\d{1,2}", item) for item in headers):
        return "monthly_summary"
    if ("本方账号" in text or "账号" in headers) and ("所属银行" in text or "本方银行" in text):
        return "account_summary"
    if "质量" in text or "校验" in text or "风险" in text:
        return "quality_or_risk"
    return "structured_table"


def detect_structured_tables(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """发现工作表内的多个表，而不是假定一张 sheet 只有一张流水表。"""
    detected: list[dict[str, Any]] = []
    for section_index, section in enumerate(sections):
        rows = section.get("tableRows") or []
        candidates = [index for index, row in enumerate(rows) if _looks_like_generic_header(row)]
        for position, header_index in enumerate(candidates):
            next_header = candidates[position + 1] if position + 1 < len(candidates) else len(rows)
            header = [str(value).strip() for value in rows[header_index]]
            # 最近的单值/章节行通常就是表名；限制回看距离避免串到上一节。
            title = ""
            for prior in range(header_index - 1, max(-1, header_index - 4), -1):
                nonempty = [str(v).strip() for v in rows[prior] if str(v or "").strip()]
                if 1 <= len(nonempty) <= 2:
                    title = " ".join(nonempty)
                    break
            data_rows = []
            for row in rows[header_index + 1:next_header]:
                values = [str(value).strip() for value in row]
                if not any(values) or any(value == "总计" for value in values):
                    continue
                data_rows.append(values)
            detected.append({
                "id": f"T{len(detected) + 1}",
                "source": section.get("source", ""),
                "title": title,
                "type": _table_type(header, title),
                "headerRow": header_index + 1,
                "headers": header,
                "rows": data_rows,
                "rowCount": len(data_rows),
            })
    return detected


def _detected_accounts(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accounts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for table in tables:
        if table["type"] != "account_summary":
            continue
        headers = table["headers"]
        for row in table["rows"]:
            record = {headers[i]: row[i] for i in range(min(len(headers), len(row))) if headers[i]}
            account = record.get("账号") or record.get("本方账号") or ""
            bank = record.get("所属银行") or record.get("本方银行") or ""
            entity = record.get("本方名称") or table.get("title", "")
            period = record.get("数据时间范围") or record.get("数据时间") or ""
            # 脱敏账号可能是“招行@姓名@”一类非纯数字标识。
            plausible_account = 4 <= len(account) <= 40 and not bool(re.search(r"\s", account))
            if not account or not bank or not plausible_account or account == "总计" or (account, entity) in seen:
                continue
            seen.add((account, entity))
            dates = re.findall(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", period)
            accounts.append({
                "entityName": entity,
                "accountNumber": account,
                "bankName": bank,
                "periodStart": _date(dates[0]) if dates else None,
                "periodEnd": _date(dates[1]) if len(dates) > 1 else None,
            })
    return accounts


def _number(value: Any) -> float:
    parsed = _decimal(value)
    return float(parsed) if parsed is not None else 0.0


def _analysis(transactions: list[dict[str, Any]], tables: list[dict[str, Any]]) -> dict[str, Any]:
    """为前端和导出提供同一份分析口径，兼容逐笔流水及汇总型尽调表。"""
    monthly: dict[str, list[float]] = {}
    categories: dict[str, list[float]] = {}
    counterparties: dict[str, list[float]] = {}
    if transactions:
        for tx in transactions:
            amount = _number(tx.get("amount"))
            month = str(tx.get("transactionDate") or "")[:7]
            if month:
                bucket = monthly.setdefault(month, [0.0, 0.0])
                bucket[0 if amount >= 0 else 1] += abs(amount)
            category = str(tx.get("category") or "其他")
            bucket = categories.setdefault(category, [0.0, 0.0])
            bucket[0 if amount >= 0 else 1] += abs(amount)
            party = str(tx.get("counterparty") or "无对方名称")
            bucket = counterparties.setdefault(party, [0.0, 0.0])
            bucket[0 if amount >= 0 else 1] += abs(amount)
    else:
        canonical_counterparty_ids = {
            table["id"] for table in tables
            if table["type"] == "counterparty_analysis"
            and ("前10大流入方" in table.get("title", "") or "前10大流出方" in table.get("title", ""))
        }
        for table in tables:
            headers, title = table["headers"], table.get("title", "")
            records = [dict(zip(headers, row)) for row in table["rows"]]
            if table["type"] == "monthly_summary":
                out = "流出" in title or any("流出合计" in h for h in headers)
                incoming = "流入" in title or any("流入合计" in h for h in headers)
                if out or incoming:
                    for record in records:
                        for header, value in record.items():
                            if re.fullmatch(r"20\d{2}[/.-]\d{1,2}", header):
                                month = header.replace("/", "-").replace(".", "-")
                                monthly.setdefault(month, [0.0, 0.0])[1 if out else 0] += abs(_number(value))
            elif table["type"] == "category_summary":
                for record in records:
                    name = record.get("分类") or "其他"
                    total = _number(record.get("合计"))
                    if not total:
                        continue
                    out = "流出" in title or total < 0
                    categories.setdefault(name, [0.0, 0.0])[1 if out else 0] += abs(total)
            elif table["type"] == "counterparty_analysis":
                if canonical_counterparty_ids and table["id"] not in canonical_counterparty_ids:
                    continue
                for record in records:
                    name = record.get("对方名称") or record.get("有效流入方") or record.get("核心流出方")
                    if not name:
                        continue
                    incoming = _number(record.get("流入总额") or record.get("流入金额"))
                    outgoing = _number(record.get("流出总额") or record.get("流出金额"))
                    if not incoming and not outgoing:
                        continue
                    bucket = counterparties.setdefault(name, [0.0, 0.0])
                    bucket[0] += abs(incoming)
                    bucket[1] += abs(outgoing)
    month_rows = [{"month": key, "inflow": round(value[0], 2), "outflow": round(value[1], 2)} for key, value in sorted(monthly.items())]
    category_rows = [{"name": key, "inflow": round(value[0], 2), "outflow": round(value[1], 2)} for key, value in categories.items()]
    party_rows = [{"name": key, "inflow": round(value[0], 2), "outflow": round(value[1], 2)} for key, value in counterparties.items()]
    total_in = round(sum(row["inflow"] for row in month_rows) or sum(row["inflow"] for row in category_rows), 2)
    total_out = round(sum(row["outflow"] for row in month_rows) or sum(row["outflow"] for row in category_rows), 2)
    return {"totalInflow": total_in, "totalOutflow": total_out, "netCashflow": round(total_in - total_out, 2),
            "monthly": month_rows, "categories": category_rows, "counterparties": party_rows}


def normalize_statement(sections: list[dict[str, Any]], full_text: str, source_name: str = "") -> dict[str, Any]:
    transactions: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    detected_tables = 0
    formula_count = 0
    statement = _statement_info(full_text, source_name)
    structured_tables = detect_structured_tables(sections)
    accounts = _detected_accounts(structured_tables)
    if len(accounts) == 1:
        statement.update(accounts[0])
    elif accounts:
        entities = sorted({item["entityName"] for item in accounts if item["entityName"]})
        banks = sorted({item["bankName"] for item in accounts if item["bankName"]})
        starts = sorted(item["periodStart"] for item in accounts if item["periodStart"])
        ends = sorted(item["periodEnd"] for item in accounts if item["periodEnd"])
        statement.update({
            "entityName": entities[0] if len(entities) == 1 else f"{len(entities)}个主体",
            "accountNumber": f"{len(accounts)}个账户",
            "bankName": "、".join(banks),
            "accountType": "混合" if len(entities) > 1 else "对公",
            "periodStart": starts[0] if starts else None,
            "periodEnd": ends[-1] if ends else None,
        })

    for section_index, section in enumerate(sections):
        rows = section.get("tableRows") or []
        formula_count += len(section.get("metadata", {}).get("formulaCells", []))
        headers = [
            (row_index, _header_mapping(row))
            for row_index, row in enumerate(rows)
            if _is_transaction_header(_header_mapping(row))
        ]
        if not headers:
            continue
        detected_tables += len(headers)
        for header_position, (header_index, mapping) in enumerate(headers):
          end_index = headers[header_position + 1][0] if header_position + 1 < len(headers) else len(rows)
          for source_row, row in enumerate(rows[header_index + 1:end_index], header_index + 2):
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
            # 标题行、合计行和后续非流水子表不能污染交易结果。
            if not parsed_date or (debit is None and credit is None and amount is None):
                continue
            inferred_category = _category(description, counterparty)
            nature = str(values.get("transactionNature", "")).strip() or inferred_category
            transaction = {
                "id": f"S{section_index + 1}-R{source_row}",
                # 六个跨模板统一字段。源材料不存在时保持空值。
                "transactionDate": parsed_date,
                "party": statement["entityName"],
                "transactionNature": nature,
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
                "category": inferred_category,
                "source": section.get("source", ""),
                "sourceRow": source_row,
                "originalRow": [str(item) for item in row],
            }
            transaction["validations"] = _issues(transaction)
            transaction["manualReviewRequired"] = bool(transaction["validations"])
            transactions.append(transaction)

    if not statement["accountNumber"] and not accounts:
        validation_issues.append({"code": "ACCOUNT_NOT_FOUND", "level": "WARNING", "message": "未识别到账户号码"})
    elif not accounts and not 8 <= len(statement["accountNumber"]) <= 30:
        validation_issues.append({"code": "INVALID_ACCOUNT", "level": "ERROR", "message": "账户号码长度异常"})
    if detected_tables == 0 and not structured_tables:
        validation_issues.append({"code": "HEADER_NOT_FOUND", "level": "ERROR", "message": "未找到可识别的流水表头"})
    elif detected_tables == 0:
        validation_issues.append({"code": "NO_TRANSACTION_DETAIL", "level": "INFO", "message": "文件包含结构化分析表，但不包含逐笔流水明细"})
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
        "accounts": accounts,
        "transactions": transactions,
        "detectedTables": structured_tables,
        "analysis": _analysis(transactions, structured_tables),
        "validation": {
            "status": "PASS" if not validation_issues and transaction_issue_count == 0 else "REVIEW",
            "issues": validation_issues,
            "transactionIssueCount": transaction_issue_count,
            "formulaCount": formula_count,
            "detectedTableCount": detected_tables,
            "structuredTableCount": len(structured_tables),
        },
    }
