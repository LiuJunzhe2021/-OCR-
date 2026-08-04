package com.example.ocr.repository;

import com.example.ocr.domain.OcrTask;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface OcrTaskRepository extends JpaRepository<OcrTask, String> {
    List<OcrTask> findTop30ByOrderByCreatedAtDesc();
}
