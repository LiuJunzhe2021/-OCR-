# LLM 自动分类 实施计划

> **目标：** 用户在前端配置大模型 → 一键触发 → LLM 自动给每笔交易打 `category` 和 `counterpartyType` → 回写 `ocr_transactions` 表 → 前端展示可修正

**架构：** 前端配置模型 + 发送交易列表 → Java 编排 → Python LLM 代理 → 外部 LLM → 结果逐行 PATCH 回数据库

**约束：** 新建文件为主，不动现有框架代码（`TaskController`、`TaskService`、`statement.py` 等）

---

## 文件清单

### 新建（7 个）

| # | 文件 | 职责 |
|---|------|------|
| 1 | `ocr-python-service/ocr_service/llm_classify.py` | LLM 分类调用器（无状态） |
| 2 | `ocr-python-service/llm_server.py` | Flask 代理服务 (:5002) |
| 3 | `ocr-business-server/.../service/LlmClassifyService.java` | 从 DB 取交易 → 调 LLM → 写回 |
| 4 | `ocr-business-server/.../controller/ClassifyController.java` | REST API |
| 5 | `ocr-web/src/llm-presets.js` | LLM 供应商预设 |
| 6 | `ocr-web/src/components/ClassifyPanel.vue` | 模型配置 + 分类按钮 |

### 修改（3 个）

| # | 文件 | 改动量 | 内容 |
|---|------|--------|------|
| 7 | `ocr-business-server/.../application.yml` | +3 行 | `app.llm.python-base-url` |
| 8 | `ocr-web/src/api.js` | +6 行 | 3 个分类 API 函数 |
| 9 | `ocr-web/src/App.vue` | +2 行 | import + 组件引用 |

---

## 数据流

```
前端 ClassifyPanel
  ├─ 用户选预设(OpenAI/Claude/DeepSeek/Ollama) + 填 Key
  ├─ 点"开始分类"
  │     ↓ POST /api/tasks/{id}/classify
  │     ↓ body: { llm: { apiUrl, apiKey, model } }
  │     ↓
Java ClassifyController
  ↓
LlmClassifyService
  ├─ 1. 从 ocr_transactions 表取所有交易
  ├─ 2. 组装 prompt（分类列表 + 交易数据）
  ├─ 3. POST Python :5002/internal/classify
  │     ↓
  │   llm_server.py → llm_classify.py
  │     ↓ POST {apiUrl}/chat/completions
  │     ↓ 带分类 prompt + 交易 JSON
  │     ↓ LLM 返回 JSON: [{id, category, counterpartyType}, ...]
  │     ↓
  ├─ 4. 逐行 PATCH /api/transactions/{id} 写回 DB
  ├─ 5. 返回前端: { classified: 18, categories: [...] }
  ↓
前端展示分类结果 → 用户可手动修正
```

---

## Task 1: Python LLM 分类服务

**文件：** 新建 `ocr-python-service/ocr_service/llm_classify.py`

**职责：** 无状态 LLM 调用器，接收交易列表和分类规则，返回每行的分类标签

### Step 1: 创建 llm_classify.py

```python
"""LLM 交易分类调用器。无状态 — 所有配置由请求传入。"""
from __future__ import annotations
import json, re, time, requests
from typing import Any

CATEGORY_OPTIONS = [
    "经营收入", "贷款流入", "借款流入", "内部转账", "个人流入",
    "经营支出", "偿还贷款", "人力成本", "纳税支出", "水电能源",
    "租金支出", "退款流出", "需关注流出", "其他流出",
    "活期利息", "银行费用", "其他",
]

CP_TYPE_OPTIONS = ["本方", "关联方", "银行", "非银", "需关注对手方", ""]


class LlmClassifyError(Exception):
    pass


class LlmClassifyClient:
    def classify(
        self,
        transactions: list[dict],
        *,
        api_url: str,
        api_key: str,
        model: str,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """发送交易列表给 LLM，返回分类结果。"""
        url = api_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        prompt = self._build_prompt(transactions)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        }

        for attempt in range(3):
            try:
                resp = self._session.post(url, headers=headers, json=payload, timeout=timeout)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                return self._parse_json(content)
            except LlmClassifyError:
                raise
            except Exception as e:
                if attempt == 2:
                    raise LlmClassifyError(f"LLM 调用失败: {e}") from e
                time.sleep(1.0 * (attempt + 1))

        raise LlmClassifyError("LLM 调用失败")

    def test_connection(self, api_url: str, api_key: str, model: str) -> dict:
        """测试 LLM 连通性。"""
        url = api_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            resp = self._session.post(url, headers=headers, json={
                "model": model, "messages": [{"role": "user", "content": "OK"}],
                "max_tokens": 5,
            }, timeout=15)
            resp.raise_for_status()
            return {"success": True, "message": f"连接成功 ({model})"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def __init__(self):
        self._session = requests.Session()

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
3. 对手方含"公司/集团/企业/科技/贸易" → 非银（除非匹配本方名称）
4. 对手方含"银行/支行/分理处" → 银行
5. 对手方含个人姓名(2-3字) → 需关注对手方
6. 内部转账/同名账户互转 → 内部转账, 本方"""

    @staticmethod
    def _build_prompt(transactions: list[dict]) -> str:
        lines = []
        for i, t in enumerate(transactions[:100]):  # 最多100条
            date = t.get("transactionDate", "")
            desc = t.get("description", "") or t.get("remarks", "") or ""
            cp = t.get("counterpartyName", "") or ""
            amt = t.get("amount", 0) or 0
            direction = t.get("direction", "")
            lines.append(
                f'{i+1}. id={t["id"][:8]} date={date} desc={desc} '
                f'cp={cp} amount={amt} dir={direction}'
            )
        return "请对以下交易分类:\n" + "\n".join(lines)

    @staticmethod
    def _parse_json(content: str) -> dict:
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
```

### Step 2: 创建 llm_server.py

```python
"""LLM 代理服务 — 独立 Flask (:5002)。"""
from __future__ import annotations
import os, time
from flask import Flask, jsonify, request
from ocr_service.llm_classify import LlmClassifyClient, LlmClassifyError

app = Flask(__name__)
client = LlmClassifyClient()

@app.get("/health")
def health():
    return jsonify({"service": "llm-classify", "status": "UP"})

@app.post("/internal/classify")
def classify():
    data = request.get_json(silent=True) or {}
    transactions = data.get("transactions", [])
    llm_config = data.get("llm", {})
    if not transactions:
        return jsonify({"success": False, "message": "缺少 transactions"}), 400

    api_url = llm_config.get("apiUrl", "").strip()
    api_key = llm_config.get("apiKey", "")
    model = llm_config.get("model", "").strip()
    if not api_url or not model:
        return jsonify({"success": False, "message": "缺少 apiUrl/model"}), 400

    started = time.monotonic()
    try:
        result = client.classify(transactions, api_url=api_url, api_key=api_key, model=model)
        elapsed = round((time.monotonic() - started) * 1000)
        return jsonify({"success": True, "results": result.get("results", []), "modelUsed": model, "processingTimeMs": elapsed})
    except LlmClassifyError as e:
        return jsonify({"success": False, "message": str(e)}), 502

@app.post("/internal/llm/test")
def test_connection():
    data = request.get_json(silent=True) or {}
    return jsonify(client.test_connection(
        data.get("apiUrl", ""), data.get("apiKey", ""), data.get("model", "")
    ))

if __name__ == "__main__":
    app.run(host=os.getenv("LLM_HOST", "127.0.0.1"), port=int(os.getenv("LLM_PORT", "5002")), debug=False)
```

### Step 3: 验证 Python 服务

```bash
cd ocr-python-service && python llm_server.py &
sleep 2
curl http://127.0.0.1:5002/health
# → {"service":"llm-classify","status":"UP"}
```

---

## Task 2: Java 分类服务 + API

### Step 4: 创建 LlmClassifyService.java

**文件：** 新建 `ocr-business-server/.../service/LlmClassifyService.java`

```java
@Service
public class LlmClassifyService {
    private final OcrTransactionRepository transactionRepo;
    private final TransactionSplitService splitService;
    private final ObjectMapper mapper;

    // 从 DB 取交易列表，传给 Python LLM 代理，结果写回 DB
    @Transactional
    public Map<String, Object> classify(String taskId, LlmConfig llm) {
        List<OcrTransaction> rows = transactionRepo.findByTaskIdOrderBySourceSectionAscSourceRowAsc(taskId);
        if (rows.isEmpty()) throw new IllegalStateException("该任务没有交易数据");

        // 组装请求
        List<Map<String, Object>> txList = rows.stream().map(tr -> {
            Map<String, Object> m = new HashMap<>();
            m.put("id", tr.getId());
            m.put("transactionDate", tr.getTransactionDate() != null ? tr.getTransactionDate().toString() : "");
            m.put("description", tr.getDescription() != null ? tr.getDescription() : "");
            m.put("counterpartyName", tr.getCounterpartyName() != null ? tr.getCounterpartyName() : "");
            m.put("amount", tr.getAmount());
            m.put("direction", tr.getDirection() != null ? tr.getDirection() : "");
            return m;
        }).toList();

        Map<String, Object> body = Map.of("transactions", txList, "llm", Map.of(
            "apiUrl", llm.apiUrl(), "apiKey", llm.apiKey(), "model", llm.model()
        ));

        // 调用 Python LLM 代理
        String resp = restClient.post().uri("/internal/classify").body(body).retrieve().body(String.class);
        Map<String, Object> result = mapper.readValue(resp, Map.class);
        if (!Boolean.TRUE.equals(result.get("success"))) {
            throw new IllegalStateException("LLM 分类失败: " + result.get("message"));
        }

        // 逐行写回 DB
        List<Map<String, Object>> results = (List<Map<String, Object>>) result.get("results");
        int updated = 0;
        for (Map<String, Object> r : results) {
            String id = (String) r.get("id");
            String cat = (String) r.get("category");
            String cpType = (String) r.get("counterpartyType");
            if (id != null && (cat != null || cpType != null)) {
                OcrTransaction patch = new OcrTransaction("");
                if (cat != null) patch.setCategory(cat);
                if (cpType != null) patch.setCounterpartyType(cpType);
                splitService.updateTransaction(id, patch);
                updated++;
            }
        }
        result.put("classified", updated);
        result.put("total", rows.size());
        return result;
    }
}
```

### Step 5: 创建 ClassifyController.java

**文件：** 新建 `ocr-business-server/.../controller/ClassifyController.java`

```java
@RestController
public class ClassifyController {
    // POST /api/tasks/{taskId}/classify        → 触发LLM分类
    // POST /api/llm/test                       → 测试LLM连接
}
```

### Step 6: 追加 application.yml 配置

```yaml
app:
  llm:
    python-base-url: ${LLM_PYTHON_URL:http://127.0.0.1:5002}
```

---

## Task 3: Vue 前端分类面板

### Step 7: 创建 llm-presets.js

复用之前项目的 LLM 预设模板（OpenAI/Claude/DeepSeek/Ollama/自定义 6 个预设）。

### Step 8: 创建 ClassifyPanel.vue

组件包含：
- 模型设置区（可折叠）：预设选择 + API 地址 + Key + 模型名 + 测试连接
- 分类按钮："开始 LLM 分类"
- 结果展示：分类完成 N/M 条 + 分类统计

### Step 9: 追加 api.js

```javascript
export const classifyTransactions = (taskId, body) =>
  api.post(`/tasks/${taskId}/classify`, body).then(({ data }) => data)
export const testLlmConnection = (config) =>
  api.post('/llm/test', config).then(({ data }) => data)
```

### Step 10: App.vue 追加组件引用

```html
<ClassifyPanel :task-id="activeTask.id" />
```
（放在 StructurePanel 同一位置，下载栏下方）

---

## Task 4: 构建与验证

### Step 11: 重建 Java + 启动四服务

```bash
# 终端 1: OCR
cd ocr-python-service && FLAGS_use_onednn=0 python app.py

# 终端 2: LLM 代理（新增）
cd ocr-python-service && python llm_server.py

# 终端 3: Java
cd ocr-business-server && java -jar target/ocr-business-server-1.0.0.jar

# 终端 4: Vue
cd ocr-web && npm run dev
```

### Step 12: 端到端测试

1. 打开 `http://localhost:5173`
2. 完成一个 OCR 任务（或使用已有任务）
3. 在结果下方看到"LLM 自动分类"面板
4. 选 OpenAI 预设 → 填 Key → 测试连接
5. 点"开始分类" → 等待 LLM 返回
6. 查看每笔交易的 category 和 counterpartyType
7. 手动修改不满意的那行

---

## 全局约束

- 不动现有 `TaskController`、`TaskService`、`TaskProcessor`、`statement.py`
- LLM Key 不存服务器，前端传 → Java 转 → Python 发
- 所有 LLM 请求由 Python :5002 代理发出，不经过浏览器直连
- 分类失败不影响 OCR 结果和已有交易数据
