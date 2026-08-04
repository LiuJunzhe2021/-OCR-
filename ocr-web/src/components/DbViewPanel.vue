<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { getTransactions, getAccount } from '../api'

const props = defineProps({ taskId: { type: String, required: true } })

const account = ref(null)
const transactions = ref([])
const loading = ref(false)
const error = ref('')

async function load() {
  if (!props.taskId) return
  loading.value = true; error.value = ''
  try {
    const [a, t] = await Promise.all([
      getAccount(props.taskId).catch(() => null),
      getTransactions(props.taskId).catch(() => []),
    ])
    account.value = a
    transactions.value = t
  } catch (e) {
    error.value = e?.response?.data?.message || e.message || '加载失败'
  } finally { loading.value = false }
}

watch(() => props.taskId, load)
onMounted(load)

// 字段中文映射
const fieldLabels = {
  transactionDate: '交易日期', amount: '金额', balance: '余额',
  description: '摘要', counterpartyName: '对手方', direction: '方向',
  category: '分类', counterpartyType: '对手方类型', party: '本方',
  manualReviewRequired: '需复核', remarks: '备注',
  sourceSection: '段落', sourceRow: '行号',
}

// 分类统计
const categoryCounts = computed(() => {
  const map = {}
  for (const t of transactions.value) {
    const cat = t.category || '其他'
    map[cat] = (map[cat] || 0) + 1
  }
  return Object.entries(map).sort((a, b) => b[1] - a[1])
})

// 金额汇总
const amountSummary = computed(() => {
  let inflow = 0, outflow = 0
  for (const t of transactions.value) {
    const amt = t.amount || 0
    if (amt > 0) inflow += amt
    else outflow += Math.abs(amt)
  }
  return { inflow, outflow, net: inflow - outflow }
})

function fmt(val) {
  if (val == null) return '—'
  if (typeof val === 'number') return val.toLocaleString('zh-CN', { minimumFractionDigits: 2 })
  return val
}
</script>

<template>
  <div class="db-panel" v-if="transactions.length || account">
    <!-- ====== 标题栏 ====== -->
    <div class="db-titlebar">
      <div>
        <span class="eyebrow">数据库</span>
        <h3>📊 结构化数据</h3>
      </div>
      <button class="ghost sm" @click="load" :disabled="loading">刷新</button>
    </div>

    <!-- ====== 账户信息卡片 ====== -->
    <div v-if="account" class="db-account">
      <div class="db-account-grid">
        <div v-if="account.entityName"><span>户名</span><strong>{{ account.entityName }}</strong></div>
        <div v-if="account.bankName"><span>银行</span><strong>{{ account.bankName }}</strong></div>
        <div v-if="account.accountNumber"><span>账号</span><strong>{{ account.accountNumber }}</strong></div>
        <div v-if="account.accountType"><span>类型</span><strong>{{ account.accountType }}</strong></div>
        <div v-if="account.currency"><span>币种</span><strong>{{ account.currency }}</strong></div>
        <div v-if="account.periodStart"><span>周期</span><strong>{{ account.periodStart }} ~ {{ account.periodEnd }}</strong></div>
      </div>
    </div>

    <!-- ====== 统计 ====== -->
    <div v-if="transactions.length" class="db-stats">
      <div class="summary-grid">
        <div><span>交易总数</span><strong>{{ transactions.length }}</strong></div>
        <div><span>流入合计</span><strong>{{ fmt(amountSummary.inflow) }}</strong></div>
        <div><span>流出合计</span><strong>{{ fmt(amountSummary.outflow) }}</strong></div>
        <div><span>净额</span><strong>{{ fmt(amountSummary.net) }}</strong></div>
        <div><span>需复核</span><strong :class="{ danger: transactions.filter(t=>t.manualReviewRequired).length }">{{ transactions.filter(t=>t.manualReviewRequired).length }}</strong></div>
        <div><span>分类数</span><strong>{{ categoryCounts.length }}</strong></div>
      </div>
    </div>

    <!-- ====== 分类标签 ====== -->
    <div v-if="categoryCounts.length" class="db-cats">
      <span v-for="[cat, n] in categoryCounts" :key="cat" class="db-tag">{{ cat }} ×{{ n }}</span>
    </div>

    <!-- ====== 交易明细表 ====== -->
    <div v-if="transactions.length" class="db-table-wrap">
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>金额</th>
            <th>余额</th>
            <th>摘要</th>
            <th>对手方</th>
            <th>方向</th>
            <th>分类</th>
            <th>复核</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in transactions" :key="t.id" :class="{ 'row-review': t.manualReviewRequired }">
            <td>{{ t.transactionDate || '—' }}</td>
            <td :class="{ 'amount-in': t.amount > 0, 'amount-out': t.amount < 0 }">{{ fmt(t.amount) }}</td>
            <td>{{ fmt(t.balance) }}</td>
            <td class="cell-desc">{{ t.description || '—' }}</td>
            <td>{{ t.counterpartyName || '—' }}</td>
            <td>{{ t.direction || '—' }}</td>
            <td>{{ t.category || '—' }}</td>
            <td><span v-if="t.manualReviewRequired" class="review-tag">需复核</span><span v-else style="color:#999">—</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!transactions.length && !loading && !error" class="empty" style="padding:20px">
      数据库暂无结构化数据，OCR 完成后自动生成。
    </div>
    <p v-if="error" class="error" style="margin:12px 18px;">{{ error }}</p>
  </div>
</template>

<style scoped>
.db-panel {
  margin-top: 20px; border: 1px solid #dfe7ee; border-radius: 18px;
  background: white; box-shadow: 0 9px 28px rgba(31,61,88,.07); overflow: hidden;
}
.db-titlebar {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  padding: 24px 24px 18px;
}
.db-titlebar .eyebrow { color: #5b7188; font-size: 11px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
.db-titlebar h3 { margin: 5px 0 0; font-size: 18px; color: #162235; font-weight: 750; }
.ghost.sm { padding: 6px 13px; font-size: 12px; border-radius: 10px; font-weight: 800; border: 0; color: #31516d; background: #edf3f7; cursor: pointer; }
.ghost.sm:hover { background: #dfe6ee; }

/* 账户卡片 */
.db-account { padding: 0 24px 12px; }
.db-account-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.db-account-grid div { padding: 10px 12px; background: #f4f7f9; border-radius: 12px; display: flex; flex-direction: column; gap: 3px; }
.db-account-grid span { color: #718397; font-size: 11px; }
.db-account-grid strong { font-size: 15px; color: #162235; }

/* 统计 */
.db-stats { padding: 0 24px 12px; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
.summary-grid div { padding: 10px 12px; background: #f4f7f9; border-radius: 12px; display: flex; flex-direction: column; gap: 3px; }
.summary-grid span { color: #718397; font-size: 11px; }
.summary-grid strong { font-size: 16px; }
.danger { color: #bf3040; }

/* 分类标签 */
.db-cats { padding: 0 24px 12px; display: flex; gap: 6px; flex-wrap: wrap; }
.db-tag { padding: 3px 10px; border-radius: 999px; background: #e8f5e9; color: #2e7d32; font-size: 11px; font-weight: 700; }

/* 表格 */
.db-table-wrap { padding: 0 24px 16px; overflow-x: auto; }
.db-table-wrap table { width: 100%; border-collapse: collapse; font-size: 12px; }
.db-table-wrap th {
  background: #f4f7f9; padding: 8px 10px; text-align: left;
  font-weight: 800; font-size: 10px; color: #5b7188;
  text-transform: uppercase; letter-spacing: .04em; border-bottom: 2px solid #dfe7ee; white-space: nowrap;
}
.db-table-wrap td { padding: 7px 10px; border-bottom: 1px solid #edf1f4; white-space: nowrap; color: #162235; }
.cell-desc { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.db-table-wrap tbody tr:hover { background: #f7f9fb; }
.row-review { background: #fff8e8; }
.row-review:hover { background: #fff3cd !important; }
.amount-in { color: #2e7d32; font-weight: 700; }
.amount-out { color: #a22b36; font-weight: 700; }
.review-tag { color: #ad2836; background: #ffe3e6; font-size: 10px; border-radius: 5px; padding: 3px 5px; white-space: nowrap; }
.empty { text-align: center; color: #8a9aab; }
.error { color: #ad2634; background: #ffe8ea; border-radius: 8px; padding: 10px; font-size: 12px; }
</style>
