package com.example.ocr.dto;

import com.example.ocr.domain.OcrTask;
import com.example.ocr.domain.TaskStatus;

import java.time.Instant;

public record TaskResponse(
        String id,
        String originalFilename,
        String fileType,
        String mode,
        TaskStatus status,
        int progress,
        String errorMessage,
        Instant createdAt,
        Instant updatedAt
) {
    public static TaskResponse from(OcrTask task) {
        return new TaskResponse(
                task.getId(), task.getOriginalFilename(), task.getFileType(),
                task.getMode(), task.getStatus(), task.getProgress(),
                task.getErrorMessage(), task.getCreatedAt(), task.getUpdatedAt()
        );
    }
}
