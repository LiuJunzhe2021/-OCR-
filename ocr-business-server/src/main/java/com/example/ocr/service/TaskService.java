package com.example.ocr.service;

import com.example.ocr.domain.OcrTask;
import com.example.ocr.dto.TaskResponse;
import com.example.ocr.repository.OcrTaskRepository;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

@Service
public class TaskService {
    private static final Set<String> SUPPORTED = Set.of(
            ".pdf", ".doc", ".docx", ".xls", ".xlsx",
            ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"
    );

    private final OcrTaskRepository repository;
    private final TaskProcessor processor;
    private final TransactionSplitService splitService;
    private final Path uploadDirectory;

    public TaskService(
            OcrTaskRepository repository,
            TaskProcessor processor,
            TransactionSplitService splitService,
            @Value("${app.storage-dir:./data}") String storageDirectory
    ) {
        this.repository = repository;
        this.processor = processor;
        this.splitService = splitService;
        this.uploadDirectory = Path.of(storageDirectory).toAbsolutePath().normalize().resolve("uploads");
    }

    @PostConstruct
    void initialize() throws IOException {
        Files.createDirectories(uploadDirectory);
    }

    public TaskResponse create(MultipartFile file, String mode) throws IOException {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("请选择文件");
        }
        if (!Set.of("auto", "native", "ocr").contains(mode)) {
            throw new IllegalArgumentException("PDF处理模式无效");
        }
        String original = file.getOriginalFilename() == null ? "document" : file.getOriginalFilename();
        original = Path.of(original.replace("\\", "/")).getFileName().toString();
        String extension = extension(original);
        if (!SUPPORTED.contains(extension)) {
            throw new IllegalArgumentException("不支持的文件类型：" + extension);
        }

        String id = UUID.randomUUID().toString();
        Path target = uploadDirectory.resolve(id + extension).normalize();
        if (!target.startsWith(uploadDirectory)) {
            throw new IllegalArgumentException("文件路径无效");
        }
        Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);
        OcrTask task = repository.save(new OcrTask(id, original, extension.substring(1), mode, target.toString()));
        processor.process(task.getId());
        return TaskResponse.from(task);
    }

    public OcrTask require(String id) {
        return repository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("任务不存在：" + id));
    }

    public TaskResponse get(String id) {
        return TaskResponse.from(require(id));
    }

    public List<TaskResponse> recent() {
        return repository.findTop30ByOrderByCreatedAtDesc().stream()
                .map(TaskResponse::from)
                .toList();
    }

    @Transactional
    public void updateResult(String id, String resultJson) {
        if (resultJson == null || resultJson.isBlank()) {
            throw new IllegalArgumentException("修订结果不能为空");
        }
        OcrTask task = require(id);
        task.reviseResult(resultJson);
        repository.save(task);
        // 修订后重新拆分为关系表行
        try {
            splitService.splitFromResultJson(id, resultJson);
        } catch (Exception ignored) {}
    }

    public void delete(String id) throws IOException {
        OcrTask task = require(id);
        Files.deleteIfExists(Path.of(task.getUploadPath()));
        repository.delete(task);
    }

    private static String extension(String filename) {
        int index = filename.lastIndexOf('.');
        return index < 0 ? "" : filename.substring(index).toLowerCase(Locale.ROOT);
    }
}
