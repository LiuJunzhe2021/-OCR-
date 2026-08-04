"""LLM AI 辅助代理服务 — 独立 Flask (:5002)。

端点:
  POST /internal/classify  — 交易分类
  POST /internal/audit     — 智能审核
  POST /internal/correct   — OCR 纠错
  POST /internal/fill      — 缺失补全
  POST /internal/llm/test  — 连接测试
"""
from __future__ import annotations

import os
import time
from typing import Any

from flask import Flask, jsonify, request

from ocr_service.llm_classify import LlmClassifyClient, LlmClassifyError

app = Flask(__name__)
client = LlmClassifyClient()


def _common(classify_method) -> Any:
    data: dict[str, Any] = request.get_json(silent=True) or {}
    transactions: list[dict[str, Any]] = data.get("transactions", [])
    llm_config: dict[str, str] = data.get("llm", {})

    if not transactions:
        return jsonify({"success": False, "message": "缺少 transactions"}), 400

    api_url = (llm_config.get("apiUrl") or "").strip()
    api_key = llm_config.get("apiKey", "")
    model = (llm_config.get("model") or "").strip()
    if not api_url or not model:
        return jsonify({"success": False, "message": "缺少 llm.apiUrl 或 llm.model"}), 400

    started = time.monotonic()
    try:
        result = classify_method(transactions, api_url=api_url, api_key=api_key, model=model)
        elapsed = round((time.monotonic() - started) * 1000)
        return jsonify({
            "success": True,
            "results": result.get("results", []),
            "modelUsed": model,
            "processingTimeMs": elapsed,
        })
    except LlmClassifyError as exc:
        return jsonify({"success": False, "message": str(exc)}), 502


@app.get("/health")
def health() -> Any:
    return jsonify({"service": "llm-classify", "status": "UP"})


@app.post("/internal/classify")
def classify() -> Any:
    return _common(client.classify)


@app.post("/internal/audit")
def audit() -> Any:
    return _common(client.audit)


@app.post("/internal/correct")
def correct() -> Any:
    return _common(client.correct)


@app.post("/internal/fill")
def fill() -> Any:
    return _common(client.fill)


@app.post("/internal/llm/test")
def test_connection() -> Any:
    data: dict[str, Any] = request.get_json(silent=True) or {}
    return jsonify(client.test_connection(
        (data.get("apiUrl") or "").strip(),
        data.get("apiKey", ""),
        (data.get("model") or "").strip(),
    ))


@app.errorhandler(Exception)
def handle_error(exc: Exception) -> Any:
    return jsonify({"success": False, "message": str(exc)}), 500


if __name__ == "__main__":
    app.run(
        host=os.getenv("LLM_HOST", "127.0.0.1"),
        port=int(os.getenv("LLM_PORT", "5002")),
        debug=False,
    )
