from __future__ import annotations

import io

from app import create_app
from ocr_service.llm_classify import LlmClassifyClient


class FakeService:
    supported_extensions = {".pdf"}

    @staticmethod
    def health():
        return {"status": "UP", "ocr": {"paddleOcrPrimary": True}}

    @staticmethod
    def extract(_path, original_name, mode):
        return {
            "originalFilename": original_name,
            "fileType": "pdf",
            "mode": mode,
            "sections": [],
            "warnings": [],
            "fullText": "",
            "summary": {"primaryOcrModel": "paddleocr"},
        }


def test_health_and_upload_contract():
    app = create_app(FakeService())
    client = app.test_client()

    assert client.get("/health").get_json()["status"] == "UP"
    response = client.post(
        "/internal/ocr",
        data={
            "mode": "auto",
            "file": (io.BytesIO(b"pdf"), "statement.pdf"),
        },
        content_type="multipart/form-data",
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["summary"]["primaryOcrModel"] == "paddleocr"


def test_llm_routes_are_available_on_main_ocr_service(monkeypatch):
    monkeypatch.setattr(
        LlmClassifyClient,
        "classify",
        lambda self, transactions, **kwargs: {"results": [{"id": transactions[0]["id"], "category": "经营收入"}]},
    )
    client = create_app(FakeService()).test_client()
    response = client.post("/internal/classify", json={
        "transactions": [{"id": "tx-1", "amount": 100}],
        "llm": {"apiUrl": "https://example.com/v1", "model": "test-model"},
    })
    assert response.status_code == 200
    assert response.get_json()["results"][0]["category"] == "经营收入"


def test_llm_route_rejects_empty_transactions():
    client = create_app(FakeService()).test_client()
    response = client.post("/internal/classify", json={"transactions": [], "llm": {}})
    assert response.status_code == 400
    assert "没有可分析" in response.get_json()["message"]
