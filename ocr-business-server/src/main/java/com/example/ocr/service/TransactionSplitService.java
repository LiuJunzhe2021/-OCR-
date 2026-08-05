package com.example.ocr.service;

import com.example.ocr.domain.OcrAccount;
import com.example.ocr.domain.OcrTransaction;
import com.example.ocr.repository.OcrAccountRepository;
import com.example.ocr.repository.OcrTransactionRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

@Service
public class TransactionSplitService {

    private final OcrTransactionRepository transactionRepo;
    private final OcrAccountRepository accountRepo;
    private final ObjectMapper mapper;

    public TransactionSplitService(
            OcrTransactionRepository transactionRepo,
            OcrAccountRepository accountRepo,
            ObjectMapper mapper
    ) {
        this.transactionRepo = transactionRepo;
        this.accountRepo = accountRepo;
        this.mapper = mapper;
    }

    @Transactional
    public void splitFromResultJson(String taskId, String resultJson) {
        // 清除旧的
        transactionRepo.deleteByTaskId(taskId);
        accountRepo.deleteByTaskId(taskId);

        try {
            JsonNode root = mapper.readTree(resultJson);

            // ----- 账户信息 -----
            JsonNode stmt = root.path("statement");
            OcrAccount account = new OcrAccount(taskId);
            account.setAccountNumber(stmt.path("accountNumber").asText(null));
            account.setBankName(stmt.path("bankName").asText(null));
            account.setEntityName(stmt.path("entityName").asText(null));
            account.setAccountType(stmt.path("accountType").asText("未知"));
            account.setCurrency(stmt.path("currency").asText("CNY"));
            String ps = stmt.path("periodStart").asText(null);
            String pe = stmt.path("periodEnd").asText(null);
            if (ps != null && !ps.isBlank()) account.setPeriodStart(LocalDate.parse(ps));
            if (pe != null && !pe.isBlank()) account.setPeriodEnd(LocalDate.parse(pe));
            accountRepo.save(account);

            // ----- 交易明细 -----
            JsonNode transactions = root.path("transactions");
            List<OcrTransaction> rows = new ArrayList<>();
            for (JsonNode item : transactions) {
                OcrTransaction tr = new OcrTransaction(taskId);

                // source
                String[] idParts = item.path("id").asText("").split("-R");
                if (idParts.length >= 2) {
                    tr.setSourceSection(safeInt(idParts[0].replace("S", "")));
                    tr.setSourceRow(safeInt(idParts[1]));
                }

                // dates
                String dateStr = item.path("transactionDate").asText(null);
                if (dateStr != null && !dateStr.isBlank()) {
                    try { tr.setTransactionDate(LocalDate.parse(dateStr)); } catch (Exception ignored) {}
                }

                // amounts
                JsonNode amountNode = item.path("amount");
                if (amountNode.isNumber()) tr.setAmount(BigDecimal.valueOf(amountNode.asDouble()));

                JsonNode balanceNode = item.path("balance");
                if (balanceNode.isNumber()) tr.setBalance(BigDecimal.valueOf(balanceNode.asDouble()));

                // fields
                tr.setDescription(trimTo(item.path("description").asText(), 2000));
                tr.setCounterpartyName(trimTo(item.path("counterparty").asText(), 200));
                tr.setCounterpartyAccount(trimTo(item.path("counterpartyAccount").asText(), 100));
                tr.setDirection(item.path("direction").asText(""));
                tr.setCategory(item.path("category").asText("其他"));
                tr.setParty(trimTo(item.path("party").asText(), 50));
                tr.setRemarks(trimTo(item.path("remarks").asText(), 400));
                tr.setManualReviewRequired(item.path("manualReviewRequired").asBoolean(false));

                // validations as JSON string
                JsonNode validations = item.path("validations");
                if (validations.isArray() && !validations.isEmpty()) {
                    tr.setValidations(validations.toString());
                }

                rows.add(tr);
            }
            if (!rows.isEmpty()) transactionRepo.saveAll(rows);

        } catch (Exception e) {
            throw new IllegalStateException("拆分 OCR 结果为数据表失败: " + e.getMessage(), e);
        }
    }

    public List<OcrTransaction> getTransactions(String taskId) {
        return transactionRepo.findByTaskIdOrderBySourceSectionAscSourceRowAsc(taskId);
    }

    public OcrAccount getAccount(String taskId) {
        return accountRepo.findByTaskId(taskId).orElse(null);
    }

    @Transactional
    public OcrAccount updateAccount(String taskId, OcrAccount patch) {
        OcrAccount account = accountRepo.findByTaskId(taskId)
                .orElseThrow(() -> new IllegalArgumentException("账户不存在: " + taskId));
        account.setEntityName(patch.getEntityName());
        account.setBankName(patch.getBankName());
        account.setAccountNumber(patch.getAccountNumber());
        account.setAccountType(patch.getAccountType());
        account.setCurrency(patch.getCurrency());
        account.setPeriodStart(patch.getPeriodStart());
        account.setPeriodEnd(patch.getPeriodEnd());
        return accountRepo.save(account);
    }

    @Transactional
    public void deleteTransaction(String id) {
        if (!transactionRepo.existsById(id)) {
            throw new IllegalArgumentException("交易不存在: " + id);
        }
        transactionRepo.deleteById(id);
    }

    @Transactional
    public void deleteTaskData(String taskId) {
        transactionRepo.deleteByTaskId(taskId);
        accountRepo.deleteByTaskId(taskId);
    }

    @Transactional
    public OcrTransaction updateTransaction(String id, OcrTransaction patch) {
        OcrTransaction tr = transactionRepo.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("交易不存在: " + id));
        if (patch.getCategory() != null) tr.setCategory(patch.getCategory());
        if (patch.getCounterpartyType() != null) tr.setCounterpartyType(patch.getCounterpartyType());
        if (patch.getDescription() != null) tr.setDescription(patch.getDescription());
        if (patch.getCounterpartyName() != null) tr.setCounterpartyName(patch.getCounterpartyName());
        if (patch.getRemarks() != null) tr.setRemarks(patch.getRemarks());
        if (patch.getAmount() != null) tr.setAmount(patch.getAmount());
        if (patch.getBalance() != null) tr.setBalance(patch.getBalance());
        if (patch.getTransactionDate() != null) tr.setTransactionDate(patch.getTransactionDate());
        tr.touch();
        return transactionRepo.save(tr);
    }

    // ---- helpers ----

    private static Integer safeInt(String s) {
        try { return Integer.parseInt(s); } catch (Exception e) { return null; }
    }

    private static String trimTo(String s, int max) {
        if (s == null) return null;
        return s.length() <= max ? s : s.substring(0, max);
    }
}
