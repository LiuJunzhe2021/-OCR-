package com.example.ocr.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

@Entity
@Table(name = "ocr_accounts")
public class OcrAccount {

    @Id
    private String id;

    @Column(nullable = false)
    private String taskId;

    @Column(length = 100)
    private String accountNumber;

    @Column(length = 100)
    private String bankName;

    @Column(length = 200)
    private String entityName;

    @Column(length = 10)
    private String accountType;  // "对公" | "对私" | "未知"

    @Column(length = 10)
    private String currency;

    private LocalDate periodStart;
    private LocalDate periodEnd;

    @Column(nullable = false)
    private Instant createdAt;

    protected OcrAccount() {}

    public OcrAccount(String taskId) {
        this.id = UUID.randomUUID().toString();
        this.taskId = taskId;
        this.createdAt = Instant.now();
    }

    // ---------- getters / setters ----------

    public String getId() { return id; }
    public String getTaskId() { return taskId; }
    public String getAccountNumber() { return accountNumber; }
    public String getBankName() { return bankName; }
    public String getEntityName() { return entityName; }
    public String getAccountType() { return accountType; }
    public String getCurrency() { return currency; }
    public LocalDate getPeriodStart() { return periodStart; }
    public LocalDate getPeriodEnd() { return periodEnd; }
    public Instant getCreatedAt() { return createdAt; }

    public void setAccountNumber(String v) { this.accountNumber = v; }
    public void setBankName(String v) { this.bankName = v; }
    public void setEntityName(String v) { this.entityName = v; }
    public void setAccountType(String v) { this.accountType = v; }
    public void setCurrency(String v) { this.currency = v; }
    public void setPeriodStart(LocalDate v) { this.periodStart = v; }
    public void setPeriodEnd(LocalDate v) { this.periodEnd = v; }
}
