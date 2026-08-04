package com.example.ocr.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

@Entity
@Table(name = "ocr_transactions")
public class OcrTransaction {

    @Id
    private String id;

    @Column(nullable = false)
    private String taskId;

    private Integer sourceSection;
    private Integer sourceRow;

    private LocalDate transactionDate;

    @Column(precision = 18, scale = 2)
    private BigDecimal amount;

    @Column(precision = 18, scale = 2)
    private BigDecimal balance;

    @Column(length = 2000)
    private String description;

    @Column(length = 200)
    private String counterpartyName;

    @Column(length = 100)
    private String counterpartyAccount;

    @Column(length = 10)
    private String direction;  // "收入" | "支出"

    @Column(length = 50)
    private String category;  // 交易分类（LLM/规则填写）

    @Column(length = 30)
    private String counterpartyType;  // "本方"|"关联方"|"银行"|"非银"|"需关注"|""

    @Column(length = 50)
    private String party;  // 本方名称

    @Column(length = 400)
    private String remarks;

    @Column(nullable = false)
    private boolean manualReviewRequired;

    @Column(length = 2000)
    private String validations;  // JSON array of validation issues

    @Column(nullable = false)
    private Instant createdAt;

    @Column(nullable = false)
    private Instant updatedAt;

    protected OcrTransaction() {}

    public OcrTransaction(String taskId) {
        this.id = UUID.randomUUID().toString();
        this.taskId = taskId;
        this.category = "其他";
        this.createdAt = Instant.now();
        this.updatedAt = this.createdAt;
    }

    // ---------- getters / setters ----------

    public String getId() { return id; }
    public String getTaskId() { return taskId; }
    public Integer getSourceSection() { return sourceSection; }
    public Integer getSourceRow() { return sourceRow; }
    public LocalDate getTransactionDate() { return transactionDate; }
    public BigDecimal getAmount() { return amount; }
    public BigDecimal getBalance() { return balance; }
    public String getDescription() { return description; }
    public String getCounterpartyName() { return counterpartyName; }
    public String getCounterpartyAccount() { return counterpartyAccount; }
    public String getDirection() { return direction; }
    public String getCategory() { return category; }
    public String getCounterpartyType() { return counterpartyType; }
    public String getParty() { return party; }
    public String getRemarks() { return remarks; }
    public boolean isManualReviewRequired() { return manualReviewRequired; }
    public String getValidations() { return validations; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }

    public void setSourceSection(Integer v) { this.sourceSection = v; }
    public void setSourceRow(Integer v) { this.sourceRow = v; }
    public void setTransactionDate(LocalDate v) { this.transactionDate = v; }
    public void setAmount(BigDecimal v) { this.amount = v; }
    public void setBalance(BigDecimal v) { this.balance = v; }
    public void setDescription(String v) { this.description = v; }
    public void setCounterpartyName(String v) { this.counterpartyName = v; }
    public void setCounterpartyAccount(String v) { this.counterpartyAccount = v; }
    public void setDirection(String v) { this.direction = v; }
    public void setCategory(String v) { this.category = v; }
    public void setCounterpartyType(String v) { this.counterpartyType = v; }
    public void setParty(String v) { this.party = v; }
    public void setRemarks(String v) { this.remarks = v; }
    public void setManualReviewRequired(boolean v) { this.manualReviewRequired = v; }
    public void setValidations(String v) { this.validations = v; }
    public void touch() { this.updatedAt = Instant.now(); }
}
