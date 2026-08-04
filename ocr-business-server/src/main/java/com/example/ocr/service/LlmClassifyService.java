package com.example.ocr.service;

import com.example.ocr.domain.OcrTransaction;
import com.example.ocr.repository.OcrTransactionRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;

import java.math.BigDecimal;
import java.time.LocalDate;
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

    // ==================== public ====================

    public Map<String, Object> classify(String taskId, Map<String, Object> llmConfig) {
        return run(taskId, llmConfig, "/internal/classify", (row, r) -> {
            String cat = (String) r.get("category");
            if (cat != null) row.setCategory(cat);
        });
    }

    public Map<String, Object> audit(String taskId, Map<String, Object> llmConfig) {
        return run(taskId, llmConfig, "/internal/audit", (row, r) -> {
            String risk = (String) r.getOrDefault("risk", "");
            String reason = (String) r.getOrDefault("reason", "");
            if (!"PASS".equals(risk) && !risk.isBlank()) {
                row.setRemarks((row.getRemarks() != null ? row.getRemarks() + " | " : "")
                        + "【审核】" + risk + " " + reason);
                row.setManualReviewRequired(true);
            }
        });
    }

    public Map<String, Object> correct(String taskId, Map<String, Object> llmConfig) {
        return run(taskId, llmConfig, "/internal/correct", (row, r) -> {
            @SuppressWarnings("unchecked")
            Map<String, Object> corrections = (Map<String, Object>) r.get("corrections");
            if (corrections == null) return;
            if (corrections.containsKey("description"))
                row.setDescription((String) corrections.get("description"));
            if (corrections.containsKey("amount"))
                row.setAmount(new BigDecimal(corrections.get("amount").toString()));
            if (corrections.containsKey("balance"))
                row.setBalance(new BigDecimal(corrections.get("balance").toString()));
            if (corrections.containsKey("counterpartyName"))
                row.setCounterpartyName((String) corrections.get("counterpartyName"));
            if (corrections.containsKey("transactionDate"))
                row.setTransactionDate(LocalDate.parse((String) corrections.get("transactionDate")));
            if (corrections.containsKey("direction"))
                row.setDirection((String) corrections.get("direction"));
        });
    }

    public Map<String, Object> fill(String taskId, Map<String, Object> llmConfig) {
        return run(taskId, llmConfig, "/internal/fill", (row, r) -> {
            @SuppressWarnings("unchecked")
            Map<String, Object> fills = (Map<String, Object>) r.get("fills");
            if (fills == null) return;
            if (fills.containsKey("description") && (row.getDescription() == null || row.getDescription().isBlank()))
                row.setDescription((String) fills.get("description"));
            if (fills.containsKey("direction") && (row.getDirection() == null || row.getDirection().isBlank()))
                row.setDirection((String) fills.get("direction"));
        });
    }

    public Map<String, Object> testConnection(Map<String, Object> llmConfig) {
        String resp = restClient.post().uri("/internal/llm/test").body(llmConfig).retrieve().body(String.class);
        try { return mapper.readValue(resp, Map.class); }
        catch (Exception e) { throw new IllegalStateException("解析响应失败: " + e.getMessage()); }
    }

    // ==================== private ====================

    @SuppressWarnings("unchecked")
    private Map<String, Object> run(
            String taskId, Map<String, Object> llmConfig, String uri, RowUpdater updater
    ) {
        List<OcrTransaction> rows = transactionRepo
                .findByTaskIdOrderBySourceSectionAscSourceRowAsc(taskId);
        if (rows.isEmpty()) throw new IllegalStateException("该任务没有交易数据，请先完成 OCR 识别");

        List<Map<String, Object>> txList = rows.stream().map(tr -> {
            Map<String, Object> m = new HashMap<>();
            m.put("id", tr.getId());
            m.put("transactionDate", tr.getTransactionDate() != null ? tr.getTransactionDate().toString() : "");
            m.put("description", tr.getDescription() != null ? tr.getDescription() : "");
            m.put("counterpartyName", tr.getCounterpartyName() != null ? tr.getCounterpartyName() : "");
            m.put("amount", tr.getAmount());
            m.put("balance", tr.getBalance());
            m.put("direction", tr.getDirection() != null ? tr.getDirection() : "");
            return m;
        }).toList();

        String resp = restClient.post().uri(uri)
                .body(Map.of("transactions", txList, "llm", llmConfig))
                .retrieve().body(String.class);

        Map<String, Object> result;
        try { result = mapper.readValue(resp, Map.class); }
        catch (Exception e) { throw new IllegalStateException("解析 LLM 响应失败"); }

        if (!Boolean.TRUE.equals(result.get("success"))) {
            throw new IllegalStateException("LLM 分析失败: " + result.getOrDefault("message", "未知"));
        }

        Map<String, String> idMap = new HashMap<>();
        for (OcrTransaction tr : rows) {
            idMap.put(tr.getId(), tr.getId());
            if (tr.getId().length() >= 8) idMap.put(tr.getId().substring(0, 8), tr.getId());
        }

        List<Map<String, Object>> results = (List<Map<String, Object>>) result.get("results");
        int updated = 0;
        if (results != null) {
            for (Map<String, Object> r : results) {
                String id = (String) r.get("id");
                String fullId = id != null ? idMap.get(id) : null;
                if (fullId != null) {
                    try {
                        OcrTransaction patch = new OcrTransaction("");
                        updater.update(patch, r);
                        splitService.updateTransaction(fullId, patch);
                        updated++;
                    } catch (Exception ignored) { /* 单行失败不中断 */ }
                }
            }
        }
        result.put("processed", updated);
        result.put("total", rows.size());
        return result;
    }

    @FunctionalInterface
    private interface RowUpdater {
        void update(OcrTransaction row, Map<String, Object> llmResult);
    }
}
