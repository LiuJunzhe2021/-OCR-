package com.example.ocr.service;

import com.fasterxml.jackson.databind.JsonNode;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.ss.util.CellRangeAddress;

import java.time.LocalDate;
import java.time.YearMonth;
import java.util.*;

/** 根据标准化流水生成与银行流水尽调报告蓝本一致的汇总首页。 */
final class DueDiligenceReportSheet {
    private DueDiligenceReportSheet() {}

    static void create(Workbook workbook, JsonNode root) {
        Sheet sheet = workbook.createSheet("现金流尽调报告");
        sheet.setDisplayGridlines(false);
        sheet.setColumnWidth(0, 6 * 256);
        sheet.setColumnWidth(1, 30 * 256);
        for (int i = 2; i <= 5; i++) sheet.setColumnWidth(i, 22 * 256);

        Styles s = new Styles(workbook);
        Row titleRow = sheet.createRow(0);
        titleRow.setHeightInPoints(36);
        put(titleRow, 1, "银行流水尽调报告", s.title);
        sheet.addMergedRegion(new CellRangeAddress(0, 0, 1, 5));
        pair(sheet, 1, "金额单位", "元", s);
        pair(sheet, 2, "货币单位", "人民币", s);

        JsonNode statement = root.path("statement");
        List<Tx> transactions = transactions(root);
        JsonNode analysis = root.path("analysis");
        double inflow = transactions.isEmpty() ? analysis.path("totalInflow").asDouble() : transactions.stream().mapToDouble(Tx::amount).filter(v -> v > 0).sum();
        double outflow = transactions.isEmpty() ? -analysis.path("totalOutflow").asDouble() : transactions.stream().mapToDouble(Tx::amount).filter(v -> v < 0).sum();

        section(sheet, 4, "一", "核心速览", s.section);
        section(sheet, 5, "1.1", "核心统计", s.subsection);
        labels(sheet, 6, s, "分析主体", "分析账户", "所属银行", "流水笔数");
        values(sheet, 7, s.value, statement.path("entityName").asText(),
                statement.path("accountNumber").asText(), statement.path("bankName").asText(), transactions.size());
        labels(sheet, 9, s, "总流入", "总流出", "净现金流", "期末余额");
        values(sheet, 10, s.money, inflow, outflow, inflow + outflow, endingBalance(transactions));

        section(sheet, 12, "1.2", "风险提示", s.subsection);
        labels(sheet, 13, s, "综合数据质量", "需复核流水", "流水校验问题", "文件级校验问题");
        boolean pass = "PASS".equals(root.path("validation").path("status").asText());
        values(sheet, 14, s.value, pass ? "良好" : "需关注",
                transactions.stream().filter(Tx::review).count(),
                root.path("validation").path("transactionIssueCount").asInt(),
                root.path("validation").path("issues").size());

        section(sheet, 16, "二", "数据验证", s.section);
        section(sheet, 17, "2.1", "账户与数据完整性", s.subsection);
        labels(sheet, 18, s, "本方名称", "账号", "数据时间范围", "数据质量");
        String period = text(statement, "periodStart") + " ~ " + text(statement, "periodEnd");
        values(sheet, 19, s.value, text(statement, "entityName"), text(statement, "accountNumber"), period,
                pass ? "良好" : "需复核");

        section(sheet, 21, "三", "指标明细", s.section);
        int row = monthly(sheet, 22, transactions, root, s);
        row = categories(sheet, row + 1, transactions, root, s);
        counterparties(sheet, row + 1, transactions, root, s);

        sheet.createFreezePane(0, 4);
        sheet.setRepeatingRows(CellRangeAddress.valueOf("1:4"));
        sheet.getPrintSetup().setLandscape(true);
        sheet.getPrintSetup().setFitWidth((short) 1);
        sheet.setFitToPage(true);
    }

    private static int monthly(Sheet sheet, int start, List<Tx> txs, JsonNode root, Styles s) {
        section(sheet, start, "3.1", "月度收支", s.subsection);
        labels(sheet, start + 1, s, "月份", "流入金额", "流出金额", "净现金流");
        if (txs.isEmpty() && root.path("analysis").path("monthly").isArray()) {
            int row = start + 2;
            for (JsonNode item : root.path("analysis").path("monthly")) {
                double in = item.path("inflow").asDouble();
                double out = -item.path("outflow").asDouble();
                values(sheet, row++, s.money, item.path("month").asText(), in, out, in + out);
            }
            if (row == start + 2) values(sheet, row++, s.value, "暂无数据", "", "", "");
            return row - 1;
        }
        YearMonth first = firstMonth(txs, root);
        for (int i = 0; i < 12; i++) {
            YearMonth month = first.plusMonths(i);
            double in = txs.stream().filter(t -> month.equals(t.month()) && t.amount > 0).mapToDouble(Tx::amount).sum();
            double out = txs.stream().filter(t -> month.equals(t.month()) && t.amount < 0).mapToDouble(Tx::amount).sum();
            values(sheet, start + 2 + i, s.money, month.toString(), in, out, in + out);
        }
        return start + 13;
    }

    private static int categories(Sheet sheet, int start, List<Tx> txs, JsonNode root, Styles s) {
        section(sheet, start, "3.2", "交易分类汇总", s.subsection);
        labels(sheet, start + 1, s, "交易分类", "流入金额", "流出金额", "净额");
        Map<String, double[]> grouped = new LinkedHashMap<>();
        for (Tx tx : txs) {
            double[] totals = grouped.computeIfAbsent(tx.category, ignored -> new double[2]);
            totals[tx.amount >= 0 ? 0 : 1] += tx.amount;
        }
        int row = start + 2;
        if (txs.isEmpty()) {
            for (JsonNode item : root.path("analysis").path("categories")) {
                double in = item.path("inflow").asDouble();
                double out = -item.path("outflow").asDouble();
                values(sheet, row++, s.money, item.path("name").asText("其他"), in, out, in + out);
            }
            if (row == start + 2) values(sheet, row++, s.value, "暂无数据", "", "", "");
            return row - 1;
        }
        for (Map.Entry<String, double[]> entry : grouped.entrySet()) {
            double[] totals = entry.getValue();
            values(sheet, row++, s.money, entry.getKey(), totals[0], totals[1], totals[0] + totals[1]);
        }
        if (grouped.isEmpty()) values(sheet, row++, s.value, "暂无数据", "", "", "");
        return row - 1;
    }

    private static void counterparties(Sheet sheet, int start, List<Tx> txs, JsonNode root, Styles s) {
        section(sheet, start, "3.3", "主要交易对手方", s.subsection);
        labels(sheet, start + 1, s, "对方名称", "流入金额", "流出金额", "净额");
        Map<String, double[]> grouped = new HashMap<>();
        for (Tx tx : txs) {
            String name = tx.counterparty.isBlank() ? "无对方名称" : tx.counterparty;
            double[] totals = grouped.computeIfAbsent(name, ignored -> new double[2]);
            totals[tx.amount >= 0 ? 0 : 1] += tx.amount;
        }
        if (txs.isEmpty()) {
            for (JsonNode item : root.path("analysis").path("counterparties")) {
                grouped.put(item.path("name").asText("无对方名称"), new double[]{item.path("inflow").asDouble(), -item.path("outflow").asDouble()});
            }
        }
        List<Map.Entry<String, double[]>> entries = new ArrayList<>(grouped.entrySet());
        entries.sort(Comparator.comparingDouble((Map.Entry<String, double[]> e) ->
                Math.abs(e.getValue()[0]) + Math.abs(e.getValue()[1])).reversed());
        int row = start + 2;
        for (Map.Entry<String, double[]> entry : entries.stream().limit(10).toList()) {
            double[] totals = entry.getValue();
            values(sheet, row++, s.money, entry.getKey(), totals[0], totals[1], totals[0] + totals[1]);
        }
        if (entries.isEmpty()) values(sheet, row, s.value, "暂无数据", "", "", "");
    }

    private static List<Tx> transactions(JsonNode root) {
        List<Tx> result = new ArrayList<>();
        for (JsonNode node : root.path("transactions")) {
            LocalDate date = null;
            try { date = LocalDate.parse(node.path("transactionDate").asText()); } catch (RuntimeException ignored) {}
            result.add(new Tx(date, node.path("amount").asDouble(), node.path("balance").isNumber() ? node.path("balance").asDouble() : null,
                    node.path("counterparty").asText(), node.path("category").asText("其他"),
                    node.path("manualReviewRequired").asBoolean()));
        }
        return result;
    }

    private static YearMonth firstMonth(List<Tx> txs, JsonNode root) {
        return txs.stream().filter(t -> t.date != null).map(Tx::month).min(Comparator.naturalOrder()).orElseGet(() -> {
            try { return YearMonth.from(LocalDate.parse(root.path("statement").path("periodStart").asText())); }
            catch (RuntimeException ignored) { return YearMonth.now().minusMonths(11); }
        });
    }

    private static double endingBalance(List<Tx> txs) {
        for (int i = txs.size() - 1; i >= 0; i--) if (txs.get(i).balance != null) return txs.get(i).balance;
        return 0;
    }

    private static String text(JsonNode node, String field) { return node.path(field).asText(""); }

    private static void section(Sheet sheet, int rowIndex, String no, String name, CellStyle style) {
        Row row = sheet.createRow(rowIndex);
        put(row, 0, no, style);
        put(row, 1, name, style);
        for (int i = 2; i <= 5; i++) put(row, i, "", style);
    }

    private static void pair(Sheet sheet, int rowIndex, String name, String value, Styles s) {
        Row row = sheet.createRow(rowIndex);
        put(row, 1, name, s.label);
        put(row, 2, value, s.value);
    }

    private static void labels(Sheet sheet, int rowIndex, Styles s, String... values) {
        Row row = sheet.createRow(rowIndex);
        for (int i = 0; i < values.length; i++) put(row, i + 1, values[i], s.label);
    }

    private static void values(Sheet sheet, int rowIndex, CellStyle style, Object... values) {
        Row row = sheet.createRow(rowIndex);
        for (int i = 0; i < values.length; i++) {
            Cell cell = row.createCell(i + 1);
            if (values[i] instanceof Number number) cell.setCellValue(number.doubleValue());
            else cell.setCellValue(String.valueOf(values[i]));
            cell.setCellStyle(style);
        }
    }

    private static void put(Row row, int column, String value, CellStyle style) {
        Cell cell = row.createCell(column);
        cell.setCellValue(value);
        cell.setCellStyle(style);
    }

    private record Tx(LocalDate date, double amount, Double balance, String counterparty, String category, boolean review) {
        YearMonth month() { return date == null ? null : YearMonth.from(date); }
    }

    private static final class Styles {
        final CellStyle title, section, subsection, label, value, money;
        Styles(Workbook workbook) {
            title = style(workbook, 18, true, IndexedColors.WHITE, IndexedColors.DARK_BLUE, HorizontalAlignment.LEFT);
            section = style(workbook, 13, true, IndexedColors.WHITE, IndexedColors.DARK_BLUE, HorizontalAlignment.LEFT);
            subsection = style(workbook, 11, true, IndexedColors.DARK_BLUE, IndexedColors.LIGHT_CORNFLOWER_BLUE, HorizontalAlignment.LEFT);
            label = style(workbook, 10, true, IndexedColors.DARK_BLUE, IndexedColors.GREY_25_PERCENT, HorizontalAlignment.CENTER);
            value = style(workbook, 10, false, IndexedColors.BLACK, IndexedColors.WHITE, HorizontalAlignment.CENTER);
            money = workbook.createCellStyle();
            money.cloneStyleFrom(value);
            money.setDataFormat(workbook.createDataFormat().getFormat("#,##0.00;[Red]-#,##0.00"));
        }
        private static CellStyle style(Workbook workbook, int size, boolean bold, IndexedColors color,
                                       IndexedColors fill, HorizontalAlignment alignment) {
            CellStyle style = workbook.createCellStyle();
            style.setAlignment(alignment);
            style.setVerticalAlignment(VerticalAlignment.CENTER);
            style.setFillForegroundColor(fill.getIndex());
            style.setFillPattern(FillPatternType.SOLID_FOREGROUND);
            style.setBorderBottom(BorderStyle.THIN);
            Font font = workbook.createFont();
            font.setFontHeightInPoints((short) size);
            font.setBold(bold);
            font.setColor(color.getIndex());
            style.setFont(font);
            return style;
        }
    }
}
