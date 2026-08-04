package com.example.ocr.service;

import com.example.ocr.client.FlaskOcrClient;
import com.example.ocr.domain.OcrTask;
import com.example.ocr.repository.OcrTaskRepository;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.file.Files;
import java.nio.file.Path;

@Service
public class TaskProcessor {
    private final OcrTaskRepository repository;
    private final FlaskOcrClient client;

    public TaskProcessor(OcrTaskRepository repository, FlaskOcrClient client) {
        this.repository = repository;
        this.client = client;
    }

    @Async
    @Transactional
    public void process(String id) {
        OcrTask task = repository.findById(id).orElseThrow();
        task.processing();
        repository.saveAndFlush(task);
        try {
            String result = client.recognize(Path.of(task.getUploadPath()), task.getMode());
            task.completed(result);
        } catch (Exception exc) {
            task.failed(exc.getMessage());
        } finally {
            repository.save(task);
            try {
                Files.deleteIfExists(Path.of(task.getUploadPath()));
            } catch (Exception ignored) {
                // 临时文件清理失败不改变识别任务结果。
            }
        }
    }
}
