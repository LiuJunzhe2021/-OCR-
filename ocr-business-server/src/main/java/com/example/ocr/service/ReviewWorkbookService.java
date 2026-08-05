package com.example.ocr.service;

import com.example.ocr.domain.OcrTask;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.poi.ss.usermodel.BorderStyle;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellStyle;
import org.apache.poi.ss.usermodel.DataValidation;
import org.apache.poi.ss.usermodel.DataValidationConstraint;
import org.apache.poi.ss.usermodel.DataValidationHelper;
import org.apache.poi.ss.usermodel.FillPatternType;
import org.apache.poi.ss.usermodel.Font;
import org.apache.poi.ss.usermodel.HorizontalAlignment;
import org.apache.poi.ss.usermodel.IndexedColors;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.util.CellRangeAddress;
import org.apache.poi.ss.util.CellRangeAddressList;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.stereotype.Service;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.HashSet;
import java.util.Set;

@Service
public class ReviewWorkbookService {
    private final ObjectMapper objectMapper;

    public ReviewWorkbookService(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public byte[] create(OcrTask task) throws IOException {
        if (task.getResultJson() == null) {
            throw new IllegalStateException("任务尚未产生识别结果");
        }
        JsonNode root = objectMapper.readTree(task.getResultJson());
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            CellStyle header = headerStyle(workbook);
            CellStyle wrap = wrapStyle(workbook);
            CellStyle percent = workbook.createCellStyle();
            percent.setDataFormat(workbook.createDataFormat().getFormat("0.00%"));

            DueDiligenceReportSheet.create(workbook, root);

            Sheet review = workbook.createSheet("识别结果");
            String[] headers = {"序号", "来源", "解析/识别方式", "原始识别文本", "修订文本（可覆盖公式）", "置信度", "需人工复核", "复核状态", "备注", "校验结果"};
            writeHeader(review, headers, header);
            int rowIndex = 1;
            int sequence = 1;
            for (JsonNode item : root.path("sections")) {
                String source = item.path("source").asText();
                String method = item.path("method").asText();
                JsonNode metadata = item.path("metadata");
                double confidence = metadata.path("confidence").asDouble(1.0);
                boolean needsReview = metadata.path("manualReviewRequired").asBoolean(false);
                String[] lines = item.path("text").asText("").split("\\R");
                if (lines.length == 0) lines = new String[]{""};
                for (String line : lines) {
                    if (line.isBlank() && lines.length > 1) continue;
                    Row row = review.createRow(rowIndex);
                    text(row, 0, String.valueOf(sequence++), wrap);
                    text(row, 1, source, wrap);
                    text(row, 2, method, wrap);
                    text(row, 3, line, wrap);
                    Cell corrected = row.createCell(4);
                    corrected.setCellFormula("D" + (rowIndex + 1));
                    corrected.setCellStyle(wrap);
                    Cell confidenceCell = row.createCell(5);
                    confidenceCell.setCellValue(confidence);
                    confidenceCell.setCellStyle(percent);
                    text(row, 6, needsReview ? "是" : "否", wrap);
                    text(row, 7, "待复核", wrap);
                    text(row, 8, "", wrap);
                    Cell check = row.createCell(9);
                    check.setCellFormula("IF(H" + (rowIndex + 1) + "=\"待复核\",\"待复核\",IF(E" + (rowIndex + 1) + "=D" + (rowIndex + 1) + ",\"已确认\",\"已修改\"))");
                    check.setCellStyle(wrap);
                    rowIndex++;
                }
            }
            configureReviewSheet(review, rowIndex);

            Sheet candidates = workbook.createSheet("候选模型");
            writeHeader(candidates, new String[]{"来源", "模型", "置信度", "质量分", "候选文本"}, header);
            int candidateRow = 1;
            for (JsonNode item : root.path("sections")) {
                for (JsonNode candidate : item.path("metadata").path("candidates")) {
                    Row row = candidates.createRow(candidateRow++);
                    text(row, 0, item.path("source").asText(), wrap);
                    text(row, 1, candidate.path("engine").asText(), wrap);
                    row.createCell(2).setCellValue(candidate.path("confidence").asDouble());
                    row.getCell(2).setCellStyle(percent);
                    row.createCell(3).setCellValue(candidate.path("quality_score").asDouble());
                    row.getCell(3).setCellStyle(percent);
                    text(row, 4, candidate.path("text").asText(), wrap);
                }
            }
            candidates.createFreezePane(0, 1);
            candidates.setAutoFilter(new CellRangeAddress(0, Math.max(1, candidateRow - 1), 0, 4));
            setWidths(candidates, new int[]{24, 16, 12, 12, 80});

            createSummary(workbook, header, percent, task, rowIndex);
            createTransactionsSheet(workbook, root, header, wrap);
            createSourceSheets(workbook, root, header, wrap);
            workbook.setForceFormulaRecalculation(true);
            workbook.write(output);
            return output.toByteArray();
        }
    }

    private static void createTransactionsSheet(Workbook workbook, JsonNode root, CellStyle header, CellStyle wrap) {
        Sheet sheet = workbook.createSheet("标准化流水");
        String[] headers = {
                "流水ID", "交易日期", "交易方", "对手方", "交易性质", "金额", "备注",
                "自动分类", "需复核", "校验信息"
        };
        writeHeader(sheet, headers, header);
        int rowIndex = 1;
        for (JsonNode transaction : root.path("transactions")) {
            Row row = sheet.createRow(rowIndex++);
            text(row, 0, transaction.path("id").asText(), wrap);
            text(row, 1, transaction.path("transactionDate").asText(), wrap);
            text(row, 2, transaction.path("party").asText(), wrap);
            text(row, 3, transaction.path("counterparty").asText(), wrap);
            text(row, 4, transaction.path("transactionNature").asText(), wrap);
            number(row, 5, transaction.get("amount"), wrap);
            text(row, 6, transaction.path("remarks").asText(), wrap);
            text(row, 7, transaction.path("category").asText("其他"), wrap);
            text(row, 8, transaction.path("manualReviewRequired").asBoolean() ? "是" : "否", wrap);
            StringBuilder issues = new StringBuilder();
            for (JsonNode issue : transaction.path("validations")) {
                if (!issues.isEmpty()) issues.append("；");
                issues.append(issue.path("message").asText());
            }
            text(row, 9, issues.toString(), wrap);
        }
        sheet.createFreezePane(0, 1);
        sheet.setAutoFilter(new CellRangeAddress(0, Math.max(1, rowIndex - 1), 0, headers.length - 1));
        setWidths(sheet, new int[]{18, 13, 24, 24, 20, 14, 36, 15, 10, 36});
    }

    private static void configureReviewSheet(Sheet sheet, int rowCount) {
        sheet.createFreezePane(0, 1);
        sheet.setAutoFilter(new CellRangeAddress(0, Math.max(1, rowCount - 1), 0, 9));
        setWidths(sheet, new int[]{8, 24, 18, 60, 60, 12, 14, 14, 30, 14});
        DataValidationHelper helper = sheet.getDataValidationHelper();
        DataValidationConstraint constraint = helper.createExplicitListConstraint(new String[]{"待复核", "已确认", "已修改"});
        DataValidation validation = helper.createValidation(constraint, new CellRangeAddressList(1, 100000, 7, 7));
        validation.setShowErrorBox(true);
        sheet.addValidationData(validation);
        var formatting = sheet.getSheetConditionalFormatting();
        var rule = formatting.createConditionalFormattingRule("$G2=\"是\"");
        rule.createPatternFormatting().setFillForegroundColor(IndexedColors.ROSE.getIndex());
        rule.getPatternFormatting().setFillPattern(FillPatternType.SOLID_FOREGROUND.getCode());
        formatting.addConditionalFormatting(new CellRangeAddress[]{new CellRangeAddress(1, Math.max(1, rowCount - 1), 0, 9)}, rule);
    }

    private static void createSummary(Workbook workbook, CellStyle header, CellStyle percent, OcrTask task, int reviewRows) {
        Sheet sheet = workbook.createSheet("质量汇总");
        writeHeader(sheet, new String[]{"指标", "数值"}, header);
        String[][] values = {
                {"任务编号", task.getId()}, {"文件名", task.getOriginalFilename()},
                {"识别条目总数", ""}, {"需人工复核数", ""},
                {"已完成复核数", ""}, {"已修改数", ""}, {"复核完成率", ""}
        };
        for (int i = 0; i < values.length; i++) {
            Row row = sheet.createRow(i + 1);
            row.createCell(0).setCellValue(values[i][0]);
            row.createCell(1).setCellValue(values[i][1]);
        }
        sheet.getRow(3).getCell(1).setCellFormula("COUNTIF('识别结果'!G:G,\"是\")");
        sheet.getRow(2).getCell(1).setCellFormula("COUNTA('识别结果'!A:A)-1");
        sheet.getRow(4).getCell(1).setCellFormula("COUNTIF('识别结果'!H:H,\"已确认\")+COUNTIF('识别结果'!H:H,\"已修改\")");
        sheet.getRow(5).getCell(1).setCellFormula("COUNTIF('识别结果'!J:J,\"已修改\")");
        sheet.getRow(6).getCell(1).setCellFormula("IF(B4=0,1,B5/B4)");
        sheet.getRow(6).getCell(1).setCellStyle(percent);
        sheet.setColumnWidth(0, 24 * 256);
        sheet.setColumnWidth(1, 48 * 256);
    }

    private static void createSourceSheets(Workbook workbook, JsonNode root, CellStyle header, CellStyle wrap) {
        Set<String> names = new HashSet<>();
        int number = 1;
        for (JsonNode item : root.path("sections")) {
            JsonNode rows = item.path("tableRows");
            if (!rows.isArray() || rows.isEmpty()) continue;
            String name = uniqueSheetName(names, "数据" + number++ + "_" + item.path("source").asText());
            Sheet sheet = workbook.createSheet(name);
            int rowIndex = 0;
            int maxColumns = 0;
            for (JsonNode cells : rows) {
                Row row = sheet.createRow(rowIndex++);
                int column = 0;
                for (JsonNode value : cells) {
                    Cell cell = row.createCell(column++);
                    cell.setCellValue(value.asText());
                    cell.setCellStyle(rowIndex == 1 ? header : wrap);
                }
                maxColumns = Math.max(maxColumns, column);
            }
            sheet.createFreezePane(0, 1);
            if (rowIndex > 0 && maxColumns > 0) {
                sheet.setAutoFilter(new CellRangeAddress(0, rowIndex - 1, 0, maxColumns - 1));
                for (int column = 0; column < maxColumns; column++) {
                    sheet.setColumnWidth(column, 20 * 256);
                }
            }
        }
    }

    private static String uniqueSheetName(Set<String> names, String raw) {
        String base = raw.replaceAll("[\\\\/?*\\[\\]:]", "_");
        base = base.substring(0, Math.min(base.length(), 28));
        String name = base;
        int suffix = 1;
        while (!names.add(name)) {
            name = base.substring(0, Math.min(base.length(), 25)) + "_" + suffix++;
        }
        return name;
    }

    private static CellStyle headerStyle(Workbook workbook) {
        CellStyle style = workbook.createCellStyle();
        style.setFillForegroundColor(IndexedColors.DARK_BLUE.getIndex());
        style.setFillPattern(FillPatternType.SOLID_FOREGROUND);
        style.setAlignment(HorizontalAlignment.CENTER);
        style.setBorderBottom(BorderStyle.THIN);
        Font font = workbook.createFont();
        font.setBold(true);
        font.setColor(IndexedColors.WHITE.getIndex());
        style.setFont(font);
        return style;
    }

    private static CellStyle wrapStyle(Workbook workbook) {
        CellStyle style = workbook.createCellStyle();
        style.setWrapText(true);
        style.setVerticalAlignment(org.apache.poi.ss.usermodel.VerticalAlignment.TOP);
        return style;
    }

    private static void writeHeader(Sheet sheet, String[] values, CellStyle style) {
        Row row = sheet.createRow(0);
        for (int index = 0; index < values.length; index++) {
            Cell cell = row.createCell(index);
            cell.setCellValue(values[index]);
            cell.setCellStyle(style);
        }
    }

    private static void text(Row row, int column, String value, CellStyle style) {
        Cell cell = row.createCell(column);
        cell.setCellValue(value);
        cell.setCellStyle(style);
    }

    private static void number(Row row, int column, JsonNode value, CellStyle style) {
        Cell cell = row.createCell(column);
        if (value != null && value.isNumber()) {
            cell.setCellValue(value.asDouble());
        }
        cell.setCellStyle(style);
    }

    private static void setWidths(Sheet sheet, int[] widths) {
        for (int index = 0; index < widths.length; index++) {
            sheet.setColumnWidth(index, Math.min(255, widths[index]) * 256);
        }
    }
}
