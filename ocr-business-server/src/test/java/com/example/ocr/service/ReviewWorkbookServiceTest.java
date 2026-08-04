package com.example.ocr.service;

import com.example.ocr.domain.OcrTask;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.poi.ss.usermodel.WorkbookFactory;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;

import static org.assertj.core.api.Assertions.assertThat;

class ReviewWorkbookServiceTest {
    @Test
    void createsEditableFormulaWorkbook() throws Exception {
        OcrTask task = new OcrTask("task-1", "流水.pdf", "pdf", "auto", "unused");
        task.completed("""
                {"sections":[{"source":"PDF第1页","method":"ocr-paddleocr","text":"金额 1000.00","metadata":{"confidence":0.96,"manualReviewRequired":false,"candidates":[{"engine":"paddleocr","confidence":0.96,"quality_score":0.95,"text":"金额 1000.00"}]},"tableRows":[["金额","1000.00"]]}]}
                """);
        byte[] bytes = new ReviewWorkbookService(new ObjectMapper()).create(task);

        try (var workbook = WorkbookFactory.create(new ByteArrayInputStream(bytes))) {
            assertThat(workbook.getSheet("识别结果").getRow(1).getCell(4).getCellFormula()).isEqualTo("D2");
            assertThat(workbook.getSheet("质量汇总").getRow(6).getCell(1).getCellFormula()).contains("B5/B4");
            assertThat(workbook.getSheet("候选模型")).isNotNull();
            assertThat(workbook.getSheet("数据1_PDF第1页")).isNotNull();
        }
    }
}
