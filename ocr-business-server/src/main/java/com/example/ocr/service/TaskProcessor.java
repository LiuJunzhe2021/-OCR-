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
    private final TransactionSplitService splitService;

    public TaskProcessor(OcrTaskRepository repository, FlaskOcrClient client,
                         TransactionSplitService splitService) {
        this.repository = repository;
        this.client = client;
        this.splitService = splitService;
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
            repository.save(task);
            // OCR 完成后自动拆解为关系表行
            try {
                splitService.splitFromResultJson(id, result);
            } catch (Exception ignored) {
                // 拆表失败不影响任务完成状态，后续可手动触发
            }
        } catch (Exception exc) {
            task.failed(exc.getMessage());
            repository.save(task);
        } finally {
            try {
                Files.deleteIfExists(Path.of(task.getUploadPath()));
            } catch (Exception ignored) {}
        }
    }
}
