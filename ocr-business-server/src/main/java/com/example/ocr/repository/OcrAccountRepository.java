package com.example.ocr.repository;

import com.example.ocr.domain.OcrAccount;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface OcrAccountRepository extends JpaRepository<OcrAccount, String> {
    Optional<OcrAccount> findByTaskId(String taskId);
    void deleteByTaskId(String taskId);
}
