package com.example.ocr.controller;

import com.example.ocr.service.LlmClassifyService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class ClassifyController {

    private final LlmClassifyService classifyService;

    public ClassifyController(LlmClassifyService classifyService) {
        this.classifyService = classifyService;
    }

    @PostMapping("/api/tasks/{taskId}/classify")
    public ResponseEntity<Map<String, Object>> classify(
            @PathVariable String taskId,
            @RequestBody Map<String, Object> body
    ) {
        @SuppressWarnings("unchecked")
        Map<String, Object> llmConfig = (Map<String, Object>) body.get("llm");
        if (llmConfig == null) {
            throw new IllegalArgumentException("缺少 llm 配置");
        }
        return ResponseEntity.ok(classifyService.classify(taskId, llmConfig));
    }

    @PostMapping("/api/llm/test")
    public ResponseEntity<Map<String, Object>> testConnection(
            @RequestBody Map<String, Object> body
    ) {
        return ResponseEntity.ok(classifyService.testConnection(body));
    }
}
