from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, request

from ocr_service.config import Settings
from ocr_service.service import DocumentService


def create_app(document_service: DocumentService | None = None) -> Flask:
    app = Flask(__name__)
    settings = Settings.from_env()
    service = document_service or DocumentService(settings)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_mb * 1024 * 1024

    @app.get("/health")
    def health():
        return jsonify(service.health())

    @app.post("/internal/ocr")
    def recognize():
        upload = request.files.get("file")
        mode = request.form.get("mode", "auto")
        if upload is None or not upload.filename:
            return jsonify({"success": False, "message": "缺少上传文件"}), 400

        suffix = Path(upload.filename).suffix.lower()
        if suffix not in service.supported_extensions:
            return jsonify(
                {
                    "success": False,
                    "message": f"不支持的文件类型：{suffix or '无扩展名'}",
                }
            ), 400
        if mode not in {"auto", "native", "ocr"}:
            return jsonify({"success": False, "message": "mode参数无效"}), 400

        try:
            with tempfile.TemporaryDirectory(prefix="advanced_ocr_") as temp_dir:
                path = Path(temp_dir) / f"{uuid4().hex}{suffix}"
                upload.save(path)
                result = service.extract(path, upload.filename, mode)
                return jsonify({"success": True, **result})
        except Exception as exc:
            app.logger.exception("文档识别失败")
            return jsonify({"success": False, "message": str(exc)}), 500

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(
            {
                "success": False,
                "message": f"文件超过{settings.max_upload_mb}MB限制",
            }
        ), 413

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5001")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
