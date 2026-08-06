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
            assertThat(workbook.getSheetAt(0).getSheetName()).isEqualTo("现金流尽调报告");
            assertThat(workbook.getSheet("现金流尽调报告").getRow(0).getCell(1).getStringCellValue())
                    .isEqualTo("银行流水尽调报告");
            assertThat(workbook.getSheet("识别结果").getRow(1).getCell(4).getCellFormula()).isEqualTo("D2");
            assertThat(workbook.getSheet("质量汇总").getRow(6).getCell(1).getCellFormula()).contains("B5/B4");
            assertThat(workbook.getSheet("候选模型")).isNotNull();
            assertThat(workbook.getSheet("数据1_PDF第1页")).isNotNull();
        }
    }

    @Test
    void dueDiligenceSheetUsesSummaryAnalysisWhenThereAreNoTransactions() throws Exception {
        OcrTask task = new OcrTask("task-2", "尽调汇总.xlsx", "xlsx", "auto", "unused");
        task.completed("""
                {"statement":{"entityName":"甲公司"},"transactions":[],
                 "analysis":{"totalInflow":300,"totalOutflow":80,"netCashflow":220,
                   "monthly":[{"month":"2024-01","inflow":100,"outflow":30}],
                   "categories":[{"name":"经营收入","inflow":300,"outflow":0}],
                   "counterparties":[{"name":"客户甲","inflow":300,"outflow":0}]},
                 "validation":{"status":"PASS","issues":[],"transactionIssueCount":0},"sections":[]}
                """);
        byte[] bytes = new ReviewWorkbookService(new ObjectMapper()).create(task);

        try (var workbook = WorkbookFactory.create(new ByteArrayInputStream(bytes))) {
            var sheet = workbook.getSheet("现金流尽调报告");
            assertThat(sheet.getRow(10).getCell(1).getNumericCellValue()).isEqualTo(300);
            assertThat(sheet.getRow(10).getCell(2).getNumericCellValue()).isEqualTo(-80);
            assertThat(sheet.getRow(24).getCell(1).getStringCellValue()).isEqualTo("2024-01");
            assertThat(sheet.getRow(24).getCell(2).getNumericCellValue()).isEqualTo(100);
            assertThat(sheet.getRow(24).getCell(3).getNumericCellValue()).isEqualTo(-30);
        }
    }
}
