"""LLM 交易分类调用器。无状态 — 所有配置由请求传入。"""
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

CP_TYPE_OPTIONS = ["本方", "关联方", "银行", "非银", "需关注对手方", ""]


class LlmClassifyError(Exception):
    """LLM 分类调用失败。"""


class LlmClassifyClient:
    """无状态 LLM 分类客户端。"""

    def __init__(self) -> None:
        self._session = requests.Session()

    def classify(
        self,
        transactions: list[dict[str, Any]],
        *,
        api_url: str,
        api_key: str,
        model: str,
        timeout: int = 120,
    ) -> dict[str, Any]:
        url = api_url.rstrip("/") + "/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._build_prompt(transactions)},
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
                content: str = resp.json()["choices"][0]["message"]["content"]
                return self._parse_json(content)
            except LlmClassifyError:
                raise
            except Exception as exc:
                if attempt == 2:
                    raise LlmClassifyError(f"LLM 调用失败（已重试3次）: {exc}") from exc
                time.sleep(1.0 * (attempt + 1))
        raise LlmClassifyError("LLM 调用失败")

    def test_connection(self, api_url: str, api_key: str, model: str) -> dict[str, Any]:
        url = api_url.rstrip("/") + "/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            resp = self._session.post(url, headers=headers, json={
                "model": model, "messages": [{"role": "user", "content": "回复 OK"}],
                "max_tokens": 5,
            }, timeout=15)
            resp.raise_for_status()
            return {"success": True, "message": f"连接成功 ({model})"}
        except Exception as exc:
            return {"success": False, "message": str(exc)[:200]}

    # ---- private ----

    @staticmethod
    def _system_prompt() -> str:
        return f"""你是一位银行流水分析专家。对每条交易标注分类和对手方类型。

## 分类选项
{', '.join(CATEGORY_OPTIONS)}

## 对手方类型
{', '.join(cp for cp in CP_TYPE_OPTIONS if cp)}

## 规则
1. 只输出 JSON，格式: {{"results":[{{"id":"...","category":"...","counterpartyType":"..."}}]}}
2. 工资/奖金/社保 → 人力成本；贷款放款 → 贷款流入；还贷款 → 偿还贷款
3. 对手方含"公司/集团/企业/科技/贸易/有限/股份" → 非银
4. 对手方含"银行/支行/分理处/信用社" → 银行
5. 小额贷款/融资租赁/担保 → 非银
6. 内部转账/同名账户互转/资金归集 → 内部转账，对手方类型填 本方
7. 对手方为自然人姓名（2-3 字中文）且金额超过 5000 → 需关注对手方
8. 无法判断的交易类别填 其他"""

    @staticmethod
    def _build_prompt(transactions: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for i, t in enumerate(transactions[:100]):
            tid = str(t.get("id", ""))[:8]
            date = str(t.get("transactionDate", ""))
            desc = str(t.get("description", "") or t.get("remarks", "") or "")
            cp = str(t.get("counterpartyName", ""))
            amt = t.get("amount", 0) or 0
            direction = str(t.get("direction", ""))
            lines.append(
                f'{i + 1}. id={tid} date={date} desc={desc} '
                f'cp={cp} amount={amt} dir={direction}'
            )
        return "请对以下交易分类:\n" + "\n".join(lines)

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
            fixed = re.sub(r",\s*([}\]])", r"\1", text)
            return json.loads(fixed)
