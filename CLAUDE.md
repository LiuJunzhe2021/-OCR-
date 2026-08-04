# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

三层架构的离线多格式 OCR 文档识别系统，不依赖第三方云 OCR 服务。

- **Python** (`ocr-python-service/`) — Flask OCR 引擎，PaddleOCR 主识别 + Tesseract 复核 + EasyOCR 仲裁
- **Java** (`ocr-business-server/`) — Spring Boot 3.5 业务层，任务管理、OCR 转发、人工复核 Excel 导出
- **Vue** (`ocr-web/`) — Vite + Vue 3 前端，上传/轮询/结果展示/下载

## 启动命令

全部在项目根目录 `-OCR-\` 下执行，需四个终端：

```bash
# 终端 1 — Python OCR 引擎（必须先启）
cd ocr-python-service
python app.py                                    # → :5001

# 终端 2 — Java 业务层（依赖 :5001）
cd ocr-business-server
java -jar target/ocr-business-server-1.0.0.jar   # → :8080

# 终端 3 — Vue 前端
cd ocr-web
npm run dev                                      # → :5173
```

浏览器打开 `http://localhost:5173`。

## 构建

```bash
# Java（Maven 在 $TEMP/apache-maven-3.9.9）
cd ocr-business-server
mvn package -DskipTests -q

# Vue
cd ocr-web
npm install
```

## 环境依赖

| 组件 | 本机路径 |
|------|---------|
| Python 3.13 | `/d/anaconda/python` |
| Java 17 | `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.8-hotspot` |
| Maven 3.9 | `$TEMP/apache-maven-3.9.9` |
| Node.js | `C:\Program Files\nodejs` |
| Tesseract | 未安装（OCR 图片时需 `C:\Program Files\Tesseract-OCR\tesseract.exe`） |

Bash shell 中需手动 export JAVA_HOME 和 Maven PATH（Windows 环境变量对 Git Bash 不生效）。

## 架构

### 数据流

```
浏览器 :5173 上传文件
  → Java :8080 TaskController.create() → 存文件 + 入库 + 异步处理
  → TaskProcessor (异步) → FlaskOcrClient POST :5001/internal/ocr
  → Python DocumentService.extract() → 按文件类型分流:
      XLS/XLSX → pandas 直接读（不 OCR）
      PDF      → pdfplumber 逐页；文本不足的页 → OCR
      DOC/DOCX → python-docx + 内嵌图片 OCR
      图片      → PaddleOCR 主识别 → Tesseract 复核 → EasyOCR 仲裁
  → 返回 JSON（sections + transactions + fullText）
  → Java 轮询完成后存 resultJson
  → 前端轮询获取结果 → 展示 + 下载 TXT/JSON/XLSX
```

### Python 关键模块

| 文件 | 职责 |
|------|------|
| `app.py` | Flask 入口，提供 `/health` + `/internal/ocr` |
| `ocr_service/service.py` | `DocumentService` — 统一入口，按后缀分流到 extractors |
| `ocr_service/extractors.py` | `Extractors` — Excel/PDF/Word/图片四种提取器 |
| `ocr_service/ocr_engine.py` | `MultiModelOCREngine` — PaddleOCR→Tesseract→EasyOCR 三级调度 |
| `ocr_service/config.py` | `Settings` — 从 `.env` 读所有配置 |
| `ocr_service/models.py` | 数据类 `Recognition`, `Candidate` |
| `ocr_service/statement.py` | 银行流水行解析与余额连续性校验 |

### Java 关键模块

| 文件 | 职责 |
|------|------|
| `controller/TaskController.java` | 任务 CRUD + 下载 + 结果修订 |
| `controller/TransactionController.java` | **新增** — 关系表查询 + 单行更新 |
| `service/TaskService.java` | 任务管理 + 修订后自动触发拆表 |
| `service/TaskProcessor.java` | 异步 OCR → 完成后自动拆分关系表 |
| `service/TransactionSplitService.java` | **新增** — JSON → ocr_transactions + ocr_accounts |
| `service/ReviewWorkbookService.java` | Apache POI 生成人工复核 Excel |
| `client/FlaskOcrClient.java` | HTTP 客户端 → `:5001/internal/ocr` |
| `domain/OcrTask.java` | 任务实体 |
| `domain/OcrTransaction.java` | **新增** — 交易明细关系表实体 |
| `domain/OcrAccount.java` | **新增** — 账户信息关系表实体 |

### Vue 前端

| 文件 | 职责 |
|------|------|
| `App.vue` | 单文件应用 — 上传、任务列表、结果展示、下载 |
| `api.js` | axios 封装，`VITE_API_BASE_URL` 代理到 `:8080` |
| `vite.config.js` | 端口 5173，`/api` → `127.0.0.1:8080` |

### API 端点

**任务管理：**
```
GET    /api/tasks              — 最近 30 个任务
POST   /api/tasks              — 上传文件创建任务 (multipart)
GET    /api/tasks/{id}          — 任务详情
GET    /api/tasks/{id}/result   — OCR 结果 JSON
PUT    /api/tasks/{id}/result   — 修订结果（保存后自动拆分到关系表）
GET    /api/tasks/{id}/result.json  — 下载 JSON
GET    /api/tasks/{id}/result.txt   — 下载 TXT
GET    /api/tasks/{id}/review.xlsx  — 下载人工复核 Excel
DELETE /api/tasks/{id}          — 删除任务
```

**关系表 API（P1 新增）：**
```
GET    /api/tasks/{id}/transactions  — 查该任务的交易明细（数据库表 ocr_transactions）
GET    /api/tasks/{id}/account       — 查该任务的账户信息（数据库表 ocr_accounts）
PATCH  /api/transactions/{id}        — 单行更新分类/对手方类型/备注等字段
```

### 数据库结构

OCR 完成或修订保存时，自动从 `resultJson` 拆分为关系表：

```
ocr_tasks (原有)          ocr_accounts (新增)       ocr_transactions (新增)
├─ id                     ├─ id                     ├─ id
├─ resultJson (CLOB)      ├─ taskId (FK)            ├─ taskId (FK)
├─ status                 ├─ accountNumber          ├─ transactionDate
├─ ...                    ├─ bankName               ├─ amount (正=收入/负=支出)
                          ├─ entityName             ├─ balance
                          ├─ accountType            ├─ description
                          ├─ currency               ├─ counterpartyName
                          ├─ periodStart/End        ├─ direction (收入/支出)
                                                    ├─ category (交易分类)
                                                    ├─ counterpartyType (本方/关联方/银行/需关注)
                                                    ├─ manualReviewRequired
                                                    └─ validations (JSON)
```

## 配置

- Python: 复制 `ocr-python-service/.env.example` → `.env`
- Java: `application.yml`，可用环境变量覆盖 `FLASK_BASE_URL`、`OCR_DATABASE_URL` 等
- Vue: `VITE_API_BASE_URL` 默认 `/api`（Vite proxy 到 `:8080`）

## OCR 策略

PaddleOCR 3.3.1 为主识别引擎。**必须设置 `FLAGS_use_onednn=0`** 禁用 ONEDNN，
否则 CPU 上会报 `pir::ArrayAttribute<DoubleAttribute>` 错误。
此修复已写入 `.env` 和 `ocr_engine.py` 的懒加载逻辑中。

- `.env` 中 `VERIFY_WITH_TESSERACT=true` 需要 Tesseract 二进制（本机未安装，Python 包 `pytesseract` 已装）。
- EasyOCR 作为仲裁引擎已安装可用（`ocr_engine.py` 懒加载）。
- PaddleOCR CPU 上首次识别会下载模型（~100MB），后续使用缓存。
