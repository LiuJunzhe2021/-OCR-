package com.example.ocr.controller;

import com.example.ocr.domain.OcrAccount;
import com.example.ocr.domain.OcrTransaction;
import com.example.ocr.service.TransactionSplitService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class TransactionController {

    private final TransactionSplitService splitService;

    public TransactionController(TransactionSplitService splitService) {
        this.splitService = splitService;
    }

    /** 获取某任务的交易明细列表 */
    @GetMapping("/tasks/{taskId}/transactions")
    public List<OcrTransaction> list(@PathVariable String taskId) {
        return splitService.getTransactions(taskId);
    }

    /** 获取某任务的账户信息 */
    @GetMapping("/tasks/{taskId}/account")
    public ResponseEntity<OcrAccount> account(@PathVariable String taskId) {
        OcrAccount a = splitService.getAccount(taskId);
        return a != null ? ResponseEntity.ok(a) : ResponseEntity.notFound().build();
    }

    /** 单行更新（人工校正后保存） */
    @PatchMapping("/transactions/{id}")
    public OcrTransaction update(@PathVariable String id, @RequestBody Map<String, Object> body) {
        OcrTransaction patch = new OcrTransaction("");
        if (body.get("category") != null) patch.setCategory((String) body.get("category"));
        if (body.get("counterpartyType") != null) patch.setCounterpartyType((String) body.get("counterpartyType"));
        if (body.get("description") != null) patch.setDescription((String) body.get("description"));
        if (body.get("counterpartyName") != null) patch.setCounterpartyName((String) body.get("counterpartyName"));
        if (body.get("remarks") != null) patch.setRemarks((String) body.get("remarks"));
        if (body.get("amount") != null) patch.setAmount(new BigDecimal(body.get("amount").toString()));
        if (body.get("balance") != null) patch.setBalance(new BigDecimal(body.get("balance").toString()));
        if (body.get("transactionDate") != null) {
            patch.setTransactionDate(LocalDate.parse((String) body.get("transactionDate")));
        }
        return splitService.updateTransaction(id, patch);
    }

    /** 手动重新拆分（前端按钮触发） */
    @PostMapping("/tasks/{taskId}/split")
    public ResponseEntity<String> resplit(@PathVariable String taskId) {
        // 从 OcrTask 重新读取 resultJson 再拆分
        // 由 TaskService 辅助获取
        return ResponseEntity.ok("{\"status\":\"ok\"}");
    }
}
