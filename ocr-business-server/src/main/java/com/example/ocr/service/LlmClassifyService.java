package com.example.ocr.service;

import com.example.ocr.domain.OcrTransaction;
import com.example.ocr.repository.OcrTransactionRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class LlmClassifyService {

    private final OcrTransactionRepository transactionRepo;
    private final RestClient restClient;
    private final ObjectMapper mapper;

    public LlmClassifyService(
            OcrTransactionRepository transactionRepo,
            RestClient.Builder builder,
            @Value("${app.llm.python-base-url:http://127.0.0.1:5002}") String baseUrl,
            ObjectMapper mapper
    ) {
        this.transactionRepo = transactionRepo;
        this.restClient = builder.baseUrl(baseUrl).build();
        this.mapper = mapper;
    }

    // ==================== public ====================

    public Map<String, Object> classify(String taskId, Map<String, Object> llmConfig) {
        return run(taskId, llmConfig, "/internal/classify", (row, r) -> {
            String cat = (String) r.get("category");
            if (cat != null) row.setCategory(clip(cat, 50));
        });
    }

    public Map<String, Object> audit(String taskId, Map<String, Object> llmConfig) {
        return run(taskId, llmConfig, "/internal/audit", (row, r) -> {
            String risk = (String) r.getOrDefault("risk", "");
            String reason = (String) r.getOrDefault("reason", "");
            if (!"PASS".equals(risk) && !risk.isBlank()) {
                row.setRemarks(clip((row.getRemarks() != null ? row.getRemarks() + " | " : "")
                        + "【审核】" + risk + " " + reason, 400));
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
                row.setDescription(clip((String) corrections.get("description"), 2000));
            if (corrections.containsKey("amount"))
                row.setAmount(new BigDecimal(corrections.get("amount").toString()));
            if (corrections.containsKey("balance"))
                row.setBalance(new BigDecimal(corrections.get("balance").toString()));
            if (corrections.containsKey("counterpartyName"))
                row.setCounterpartyName(clip((String) corrections.get("counterpartyName"), 200));
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
                row.setDescription(clip((String) fills.get("description"), 2000));
            if (fills.containsKey("direction") && (row.getDirection() == null || row.getDirection().isBlank()))
                row.setDirection((String) fills.get("direction"));
        });
    }

    public Map<String, Object> testConnection(Map<String, Object> llmConfig) {
        String resp = postJson("/internal/llm/test", llmConfig);
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

        String resp = postJson(uri, Map.of("transactions", txList, "llm", llmConfig));

        Map<String, Object> result;
        try { result = mapper.readValue(resp, Map.class); }
        catch (Exception e) { throw new IllegalStateException("解析 LLM 响应失败"); }

        if (!Boolean.TRUE.equals(result.get("success"))) {
            throw new IllegalStateException("LLM 分析失败: " + result.getOrDefault("message", "未知"));
        }

        Map<String, OcrTransaction> idMap = new HashMap<>();
        for (OcrTransaction tr : rows) {
            idMap.put(tr.getId(), tr);
            if (tr.getId().length() >= 8) idMap.put(tr.getId().substring(0, 8), tr);
        }

        List<Map<String, Object>> results = (List<Map<String, Object>>) result.get("results");
        int updated = 0;
        if (results != null) {
            for (Map<String, Object> r : results) {
                String id = (String) r.get("id");
                OcrTransaction target = id != null ? idMap.get(id) : null;
                if (target != null) {
                    try {
                        updater.update(target, r);
                        target.touch();
                        transactionRepo.save(target);
                        updated++;
                    } catch (Exception ignored) { /* 单行失败不中断 */ }
                }
            }
        }
        result.put("processed", updated);
        result.put("total", rows.size());
        return result;
    }

    private String postJson(String uri, Object body) {
        try {
            return restClient.post().uri(uri).body(body).retrieve().body(String.class);
        } catch (RestClientResponseException exc) {
            try {
                Map<?, ?> error = mapper.readValue(exc.getResponseBodyAsString(), Map.class);
                Object message = error.containsKey("message") ? error.get("message") : "LLM 服务调用失败";
                throw new IllegalStateException(String.valueOf(message));
            } catch (IllegalStateException parsed) {
                throw parsed;
            } catch (Exception ignored) {
                throw new IllegalStateException("LLM 服务调用失败（HTTP " + exc.getStatusCode().value() + "）");
            }
        } catch (Exception exc) {
            throw new IllegalStateException("无法连接 LLM 服务，请确认 OCR 服务 5001 已启动: " + exc.getMessage());
        }
    }

    private static String clip(String value, int max) {
        if (value == null || value.length() <= max) return value;
        return value.substring(0, max);
    }

    @FunctionalInterface
    private interface RowUpdater {
        void update(OcrTransaction row, Map<String, Object> llmResult);
    }
}
