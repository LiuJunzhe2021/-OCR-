package com.example.ocr.repository;

import com.example.ocr.domain.OcrTransaction;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface OcrTransactionRepository extends JpaRepository<OcrTransaction, String> {
    List<OcrTransaction> findByTaskIdOrderBySourceSectionAscSourceRowAsc(String taskId);
    void deleteByTaskId(String taskId);
}
