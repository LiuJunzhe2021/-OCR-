package com.example.ocr.controller;

import com.example.ocr.domain.OcrTask;
import com.example.ocr.domain.TaskStatus;
import com.example.ocr.dto.TaskResponse;
import com.example.ocr.service.ReviewWorkbookService;
import com.example.ocr.service.TaskService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;

@RestController
@RequestMapping("/api/tasks")
public class TaskController {
    private final TaskService taskService;
    private final ReviewWorkbookService workbookService;
    private final ObjectMapper objectMapper;

    public TaskController(TaskService taskService, ReviewWorkbookService workbookService, ObjectMapper objectMapper) {
        this.taskService = taskService;
        this.workbookService = workbookService;
        this.objectMapper = objectMapper;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<TaskResponse> create(
            @RequestPart("file") MultipartFile file,
            @RequestParam(defaultValue = "auto") String mode
    ) throws IOException {
        return ResponseEntity.accepted().body(taskService.create(file, mode));
    }

    @GetMapping
    public List<TaskResponse> recent() {
        return taskService.recent();
    }

    @GetMapping("/{id}")
    public TaskResponse get(@PathVariable String id) {
        return taskService.get(id);
    }

    @GetMapping("/{id}/result")
    public JsonNode result(@PathVariable String id) throws IOException {
        OcrTask task = requireCompleted(id);
        return objectMapper.readTree(task.getResultJson());
    }

    @PutMapping(value = "/{id}/result", consumes = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode updateResult(@PathVariable String id, @RequestBody JsonNode result) throws IOException {
        requireCompleted(id);
        if (!result.isObject() || !result.path("transactions").isArray()) {
            throw new IllegalArgumentException("修订结果必须包含 transactions 数组");
        }
        taskService.updateResult(id, objectMapper.writeValueAsString(result));
        return result;
    }

    @GetMapping("/{id}/result.json")
    public ResponseEntity<byte[]> json(@PathVariable String id) {
        OcrTask task = requireCompleted(id);
        return download(
                task.getResultJson().getBytes(StandardCharsets.UTF_8),
                stem(task.getOriginalFilename()) + "_ocr_result.json",
                MediaType.APPLICATION_JSON
        );
    }

    @GetMapping("/{id}/result.txt")
    public ResponseEntity<byte[]> text(@PathVariable String id) throws IOException {
        OcrTask task = requireCompleted(id);
        String fullText = objectMapper.readTree(task.getResultJson()).path("fullText").asText();
        return download(
                fullText.getBytes(StandardCharsets.UTF_8),
                stem(task.getOriginalFilename()) + "_ocr_result.txt",
                MediaType.TEXT_PLAIN
        );
    }

    @GetMapping("/{id}/review.xlsx")
    public ResponseEntity<byte[]> workbook(@PathVariable String id) throws IOException {
        OcrTask task = requireCompleted(id);
        return download(
                workbookService.create(task),
                stem(task.getOriginalFilename()) + "_银行流水尽调报告.xlsx",
                MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        );
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable String id) throws IOException {
        taskService.delete(id);
        return ResponseEntity.noContent().build();
    }

    private OcrTask requireCompleted(String id) {
        OcrTask task = taskService.require(id);
        if (task.getStatus() != TaskStatus.COMPLETED) {
            throw new IllegalStateException("任务尚未完成");
        }
        return task;
    }

    private static ResponseEntity<byte[]> download(byte[] bytes, String filename, MediaType type) {
        ContentDisposition disposition = ContentDisposition.attachment()
                .filename(filename, StandardCharsets.UTF_8)
                .build();
        return ResponseEntity.ok()
                .contentType(type)
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString())
                .body(bytes);
    }

    private static String stem(String filename) {
        int index = filename.lastIndexOf('.');
        return index <= 0 ? filename : filename.substring(0, index);
    }
}
