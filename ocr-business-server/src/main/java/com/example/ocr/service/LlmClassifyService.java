package com.example.ocr.service;

import com.example.ocr.domain.OcrTransaction;
import com.example.ocr.repository.OcrTransactionRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class LlmClassifyService {

    private final OcrTransactionRepository transactionRepo;
    private final TransactionSplitService splitService;
    private final RestClient restClient;
    private final ObjectMapper mapper;

    public LlmClassifyService(
            OcrTransactionRepository transactionRepo,
            TransactionSplitService splitService,
            RestClient.Builder builder,
            @Value("${app.llm.python-base-url:http://127.0.0.1:5002}") String baseUrl,
            ObjectMapper mapper
    ) {
        this.transactionRepo = transactionRepo;
        this.splitService = splitService;
        this.restClient = builder.baseUrl(baseUrl).build();
        this.mapper = mapper;
    }

    @Transactional
    @SuppressWarnings("unchecked")
    public Map<String, Object> classify(String taskId, Map<String, Object> llmConfig) {
        List<OcrTransaction> rows = transactionRepo
                .findByTaskIdOrderBySourceSectionAscSourceRowAsc(taskId);
        if (rows.isEmpty()) {
            throw new IllegalStateException("该任务没有交易数据，请先完成 OCR 识别");
        }

        // 组装交易列表
        List<Map<String, Object>> txList = rows.stream().map(tr -> {
            Map<String, Object> m = new HashMap<>();
            m.put("id", tr.getId());
            m.put("transactionDate", tr.getTransactionDate() != null
                    ? tr.getTransactionDate().toString() : "");
            m.put("description", tr.getDescription() != null ? tr.getDescription() : "");
            m.put("counterpartyName", tr.getCounterpartyName() != null
                    ? tr.getCounterpartyName() : "");
            m.put("amount", tr.getAmount());
            m.put("direction", tr.getDirection() != null ? tr.getDirection() : "");
            return m;
        }).toList();

        Map<String, Object> body = Map.of(
                "transactions", txList,
                "llm", llmConfig
        );

        // 调用 Python LLM 代理
        String resp = restClient.post()
                .uri("/internal/classify")
                .body(body)
                .retrieve()
                .body(String.class);

        Map<String, Object> result;
        try {
            result = mapper.readValue(resp, Map.class);
        } catch (Exception e) {
            throw new IllegalStateException("解析 LLM 代理响应失败: " + e.getMessage());
        }

        if (!Boolean.TRUE.equals(result.get("success"))) {
            throw new IllegalStateException("LLM 分类失败: " +
                    result.getOrDefault("message", "未知错误"));
        }

        // 逐行写回 DB
        List<Map<String, Object>> results =
                (List<Map<String, Object>>) result.get("results");
        int updated = 0;
        if (results != null) {
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
        }

        result.put("classified", updated);
        result.put("total", rows.size());
        return result;
    }

    public Map<String, Object> testConnection(Map<String, Object> llmConfig) {
        String resp = restClient.post()
                .uri("/internal/llm/test")
                .body(llmConfig)
                .retrieve()
                .body(String.class);
        try {
            return mapper.readValue(resp, Map.class);
        } catch (Exception e) {
            throw new IllegalStateException("解析连接测试响应失败: " + e.getMessage());
        }
    }
}
