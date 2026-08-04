package com.example.ocr.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "ocr_tasks")
public class OcrTask {
    @Id
    private String id;
    @Column(nullable = false)
    private String originalFilename;
    @Column(nullable = false)
    private String fileType;
    @Column(nullable = false)
    private String mode;
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private TaskStatus status;
    @Column(nullable = false)
    private int progress;
    @Column(nullable = false, length = 1024)
    private String uploadPath;
    @Lob
    @Column(columnDefinition = "CLOB")
    private String resultJson;
    @Column(length = 4000)
    private String errorMessage;
    @Column(nullable = false)
    private Instant createdAt;
    @Column(nullable = false)
    private Instant updatedAt;

    protected OcrTask() {}

    public OcrTask(String id, String originalFilename, String fileType, String mode, String uploadPath) {
        this.id = id;
        this.originalFilename = originalFilename;
        this.fileType = fileType;
        this.mode = mode;
        this.uploadPath = uploadPath;
        this.status = TaskStatus.PENDING;
        this.progress = 0;
        this.createdAt = Instant.now();
        this.updatedAt = this.createdAt;
    }

    public void processing() {
        this.status = TaskStatus.PROCESSING;
        this.progress = 20;
        this.updatedAt = Instant.now();
    }

    public void completed(String resultJson) {
        this.resultJson = resultJson;
        this.status = TaskStatus.COMPLETED;
        this.progress = 100;
        this.updatedAt = Instant.now();
    }

    public void failed(String message) {
        this.errorMessage = message == null ? "未知错误" : message.substring(0, Math.min(message.length(), 4000));
        this.status = TaskStatus.FAILED;
        this.progress = 100;
        this.updatedAt = Instant.now();
    }

    public String getId() { return id; }
    public String getOriginalFilename() { return originalFilename; }
    public String getFileType() { return fileType; }
    public String getMode() { return mode; }
    public TaskStatus getStatus() { return status; }
    public int getProgress() { return progress; }
    public String getUploadPath() { return uploadPath; }
    public String getResultJson() { return resultJson; }
    public String getErrorMessage() { return errorMessage; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
}
