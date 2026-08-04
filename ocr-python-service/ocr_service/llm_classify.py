"""LLM 交易分析调用器 —— 无状态，所有配置由请求传入。

支持模式:
  classify    — 交易分类（经营收入/贷款流入…）
  audit       — 智能审核（标记金额异常、余额不连续、可疑交易）
  correct     — OCR 纠错（对比原文识别文本，发现并修正错误）
  fill        — 缺失补全（对空字段根据上下文推断补全）
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import requests

CATEGORY_OPTIONS = [
    "经营收入", "贷款流入", "借款流入", "内部转账", "个人流入",
    "经营支出", "偿还贷款", "人力成本", "纳税支出", "水电能源",
    "租金支出", "退款流出", "需关注流出", "其他流出",
    "活期利息", "银行费用", "其他",
]


class LlmClassifyError(Exception):
    pass


class LlmClassifyClient:

    def __init__(self) -> None:
        self._session = requests.Session()

    # ---- public API ----

    def classify(
        self, transactions: list[dict[str, Any]], *, api_url: str,
        api_key: str, model: str, timeout: int = 120,
    ) -> dict[str, Any]:
        return self._call(transactions, api_url, api_key, model, timeout,
                          self._sys_classify(), self._prompt_classify)

    def audit(
        self, transactions: list[dict[str, Any]], *, api_url: str,
        api_key: str, model: str, timeout: int = 120,
    ) -> dict[str, Any]:
        return self._call(transactions, api_url, api_key, model, timeout,
                          self._sys_audit(), self._prompt_list)

    def correct(
        self, transactions: list[dict[str, Any]], *, api_url: str,
        api_key: str, model: str, timeout: int = 120,
    ) -> dict[str, Any]:
        return self._call(transactions, api_url, api_key, model, timeout,
                          self._sys_correct(), self._prompt_list)

    def fill(
        self, transactions: list[dict[str, Any]], *, api_url: str,
        api_key: str, model: str, timeout: int = 120,
    ) -> dict[str, Any]:
        return self._call(transactions, api_url, api_key, model, timeout,
                          self._sys_fill(), self._prompt_list)

    def test_connection(self, api_url: str, api_key: str, model: str) -> dict[str, Any]:
        url = api_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            resp = self._session.post(url, headers=headers, json={
                "model": model, "messages": [{"role": "user", "content": "回复 OK"}],
                "max_tokens": 5}, timeout=15)
            resp.raise_for_status()
            return {"success": True, "message": f"连接成功 ({model})"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    # ---- internal ----

    def _call(
        self, transactions: list[dict[str, Any]], api_url: str, api_key: str,
        model: str, timeout: int, system_prompt: str, prompt_fn,
    ) -> dict[str, Any]:
        url = api_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_fn(transactions[:100])},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        }

        for attempt in range(3):
            try:
                resp = self._session.post(url, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 401:
                    raise LlmClassifyError("API Key 无效（401）")
                resp.raise_for_status()
                return self._parse_json(resp.json()["choices"][0]["message"]["content"])
            except LlmClassifyError:
                raise
            except Exception as e:
                if attempt == 2:
                    raise LlmClassifyError(f"LLM 调用失败（已重试3次）: {e}") from e
                time.sleep(1.0 * (attempt + 1))
        raise LlmClassifyError("LLM 调用失败")

    # ---- system prompts ----

    @staticmethod
    def _sys_classify() -> str:
        return f"""你是银行流水分析专家。对每条交易标注分类。

## 分类选项
{', '.join(CATEGORY_OPTIONS)}

## 规则
1. 只输出 JSON: {{"results":[{{"id":"...","category":"..."}}]}}
2. 工资/奖金/社保 → 人力成本；贷款放款 → 贷款流入；还贷款 → 偿还贷款
3. 对手方含"公司/集团/企业/科技/贸易/有限/股份"且收付款 → 经营收入/经营支出
4. 内部转账/同名账户互转/资金归集 → 内部转账
5. 无法判断填 其他"""

    @staticmethod
    def _sys_audit() -> str:
        return """你是银行流水审计专家。逐条审查交易，标注风险。

审计维度：
- AMOUNT_ANOMALY: 金额异常（远大于平均交易额）
- BALANCE_BREAK: 余额不连续（与上笔余额+本笔金额不匹配）
- ROUND_AMOUNT: 大额整数交易（可能是借贷或回扣）
- NIGHT_TRANSFER: 夜间交易（22:00-06:00）
- UNKNOWN_CP: 对手方为空或无意义
- DUPLICATE: 疑似重复交易（日期/金额/对手方相同）
- SENSITIVE_WORD: 对手方含敏感词（KTV/酒吧/会所/娱乐/洗浴）

只输出 JSON: {"results":[{"id":"...","risk":"PASS"或风险码","reason":"简短说明"}]}
多条风险用 / 分隔，无风险填 PASS"""

    @staticmethod
    def _sys_correct() -> str:
        return """你是 OCR 纠错专家。对比原始 OCR 文本和解析后的交易字段，发现并纠正识别错误。

常见 OCR 错误：
- 形近字：末/未、己/已、藉/籍、拔/拨
- 数字：0/O、1/l/I、7/T
- 金额：小数点错位、负号丢失
- 日期：月份超出范围（13月→12月）

只输出 JSON: {"results":[{"id":"...","corrections":{"field":"修正值",...}}]}
只输出有实际纠正的行和字段，无错误的不输出"""

    @staticmethod
    def _sys_fill() -> str:
        return """你是金融数据补全专家。对交易中的空字段，根据上下文推断补全。

补全策略：
- 对方相同但某条缺描述 → 参考相邻行的描述
- 金额为整数且较大 → 摘要可能为"转账"
- 收支方向和金额正负矛盾 → 修正方向
- 日期缺失 → 不可补（留空）

只输出 JSON: {"results":[{"id":"...","fills":{"description":"补全值",...}}]}
只输出有补全的行，无补全的不输出"""

    # ---- user prompts ----

    @staticmethod
    def _prompt_classify(transactions: list[dict[str, Any]]) -> str:
        return "请对以下交易分类:\n" + LlmClassifyClient._txn_list(transactions)

    @staticmethod
    def _prompt_list(transactions: list[dict[str, Any]]) -> str:
        return "请分析以下交易:\n" + LlmClassifyClient._txn_list(transactions)

    @staticmethod
    def _txn_list(transactions: list[dict[str, Any]]) -> str:
        lines = []
        for i, t in enumerate(transactions[:100]):
            tid = str(t.get("id", ""))
            date = str(t.get("transactionDate", ""))
            desc = str(t.get("description", "") or "")
            cp = str(t.get("counterpartyName", ""))
            amt = t.get("amount", 0) or 0
            bal = t.get("balance", "")
            direction = str(t.get("direction", ""))
            lines.append(
                f"{i+1}. id={tid} date={date} desc={desc} "
                f"cp={cp} amount={amt} balance={bal} dir={direction}"
            )
        return "\n".join(lines)

    # ---- parse ----

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        text = match.group(1) if match else content
        text = text.strip().lstrip("`").rstrip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", text))
