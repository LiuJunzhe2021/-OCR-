"""Flask文档解析与多模型OCR服务。"""

from .config import Settings
from .service import DocumentService

__all__ = ["DocumentService", "Settings"]
