"""LLM 分类代理服务 — 独立 Flask (:5002)。"""
from __future__ import annotations

import os
import time
from typing import Any

from flask import Flask, jsonify, request

from ocr_service.llm_classify import LlmClassifyClient, LlmClassifyError

app = Flask(__name__)
client = LlmClassifyClient()


@app.get("/health")
def health() -> Any:
    return jsonify({"service": "llm-classify", "status": "UP"})


@app.post("/internal/classify")
def classify() -> Any:
    data: dict[str, Any] = request.get_json(silent=True) or {}
    transactions: list[dict[str, Any]] = data.get("transactions", [])
    llm_config: dict[str, str] = data.get("llm", {})

    if not transactions:
        return jsonify({"success": False, "message": "缺少 transactions"}), 400

    api_url: str = (llm_config.get("apiUrl") or "").strip()
    api_key: str = llm_config.get("apiKey", "")
    model: str = (llm_config.get("model") or "").strip()

    if not api_url or not model:
        return jsonify({"success": False, "message": "缺少 llm.apiUrl 或 llm.model"}), 400

    started = time.monotonic()
    try:
        result = client.classify(transactions, api_url=api_url, api_key=api_key, model=model)
        elapsed = round((time.monotonic() - started) * 1000)
        return jsonify({
            "success": True,
            "results": result.get("results", []),
            "modelUsed": model,
            "processingTimeMs": elapsed,
        })
    except LlmClassifyError as exc:
        return jsonify({"success": False, "message": str(exc)}), 502


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
