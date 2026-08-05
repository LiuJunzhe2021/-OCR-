<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ArrowRight, BarChart3, Building2, CalendarDays, CheckCircle2, ChevronDown, CircleAlert, Download, FileSpreadsheet, Files, FilterX, LocateFixed, Pencil, Plus, RefreshCw, Search, Trash2, UploadCloud, UserRound, Users, WalletCards, X } from 'lucide-vue-next'
import EChart from './components/EChart.vue'
import { createTask, deleteTask, deleteTransaction, downloadUrl, getAccount, getResult, getTask, getTransactions, listTasks, updateAccount, updateResult, updateTransaction } from './api'

const view = ref('records')
const tasks = ref([])
const activeTask = ref(null)
const result = ref(null)
const dbRows = ref([])
const account = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const uploadProgress = ref(0)
const query = ref('')
const statusFilter = ref('ALL')
const entityFilter = ref('ALL')
const txQuery = ref('')
const txDirection = ref('ALL')
const txStart = ref('')
const txEnd = ref('')
const txMin = ref('')
const txMax = ref('')
const txPage = ref(1)
const txPageSize = 20
const counterpartyQuery = ref('')
const expandedCounterparty = ref('')
const sourceRow = ref(null)
const selectedIds = ref([])
const editAccountOpen = ref(false)
const editRowOpen = ref(false)
const editingRow = reactive({})
const error = ref('')
let pollTimer

const finishedTasks = computed(() => tasks.value.filter(t => t.status === 'COMPLETED'))
const filteredTasks = computed(() => tasks.value.filter(t => {
  const keyword = query.value.trim().toLowerCase()
  const matches = !keyword || t.originalFilename.toLowerCase().includes(keyword)
  return matches && (statusFilter.value === 'ALL' || t.status === statusFilter.value) && (entityFilter.value === 'ALL' || t.account?.entityName === entityFilter.value)
}))
const sourceRows = computed(() => dbRows.value.length ? dbRows.value : (result.value?.transactions || []))
const filteredRows = computed(() => sourceRows.value.filter(row => {
  const keyword = txQuery.value.trim().toLowerCase()
  const text = `${row.counterpartyName || row.counterparty || ''} ${row.description || ''} ${row.remarks || ''} ${row.category || ''}`.toLowerCase()
  const date = row.transactionDate || row.date || ''
  const amount = Math.abs(Number(row.amount) || 0)
  return (!keyword || text.includes(keyword))
    && (txDirection.value === 'ALL' || (txDirection.value === 'IN' ? isIncome(row) : !isIncome(row)))
    && (!txStart.value || date >= txStart.value) && (!txEnd.value || date <= txEnd.value)
    && (txMin.value === '' || amount >= Number(txMin.value)) && (txMax.value === '' || amount <= Number(txMax.value))
}))
const pageCount = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / txPageSize)))
const pagedRows = computed(() => filteredRows.value.slice((txPage.value - 1) * txPageSize, txPage.value * txPageSize))
const totalIn = computed(() => sourceRows.value.filter(isIncome).reduce((n, r) => n + Math.abs(Number(r.amount) || 0), 0))
const totalOut = computed(() => sourceRows.value.filter(r => !isIncome(r)).reduce((n, r) => n + Math.abs(Number(r.amount) || 0), 0))
const reviewRows = computed(() => sourceRows.value.filter(r => r.manualReviewRequired || r.validations?.length).length)
const entities = computed(() => [...new Set(tasks.value.map(t => t.account?.entityName).filter(Boolean))])
const counterparties = computed(() => {
  const groups = new Map()
  sourceRows.value.forEach(row => {
    const name = row.counterpartyName || row.counterparty || '未知对手方'
    if (!groups.has(name)) groups.set(name, { name, rows: [], income: 0, expense: 0, latestDate: '' })
    const group = groups.get(name)
    group.rows.push(row)
    group.latestDate = [group.latestDate, row.transactionDate || row.date || ''].sort().at(-1)
    group[isIncome(row) ? 'income' : 'expense'] += Math.abs(Number(row.amount) || 0)
  })
  const keyword = counterpartyQuery.value.trim().toLowerCase()
  return [...groups.values()].filter(group => !keyword || group.name.toLowerCase().includes(keyword) || group.rows.some(row => `${row.counterpartyAccount || ''} ${row.description || ''}`.toLowerCase().includes(keyword))).sort((a,b) => b.income + b.expense - a.income - a.expense)
})
const sourceSection = computed(() => {
  if (!sourceRow.value || !result.value?.sections?.length) return null
  const index = Number(sourceRow.value.sourceSection)
  return result.value.sections[index - 1] || result.value.sections[index] || null
})

const monthlyOption = computed(() => {
  const bucket = {}
  sourceRows.value.forEach(row => {
    const month = (row.transactionDate || row.date || '').slice(0, 7) || '未知'
    bucket[month] ||= [0, 0]
    bucket[month][isIncome(row) ? 0 : 1] += Math.abs(Number(row.amount) || 0)
  })
  const months = Object.keys(bucket).sort()
  return chartBase({ tooltip: { trigger: 'axis' }, legend: { data: ['流入', '流出'], top: 2 }, xAxis: { type: 'category', data: months }, yAxis: { type: 'value', axisLabel: { formatter: value => shortMoney(value) } }, series: [{ name: '流入', type: 'line', smooth: true, data: months.map(m => bucket[m][0]), itemStyle: { color: '#16a394' }, areaStyle: { color: 'rgba(22,163,148,.08)' } }, { name: '流出', type: 'line', smooth: true, data: months.map(m => bucket[m][1]), itemStyle: { color: '#ee7b55' } }] })
})
const categoryOption = computed(() => {
  const data = aggregate(sourceRows.value, r => r.category || '其他').slice(0, 7)
  return chartBase({ tooltip: { trigger: 'item', formatter: '{b}<br/>金额：{c} 元（{d}%）' }, legend: { type: 'scroll', bottom: 0 }, series: [{ type: 'pie', radius: ['48%', '72%'], center: ['50%', '43%'], label: { formatter: '{d}%' }, data: data.map(([name, value]) => ({ name, value })) }] })
})
const counterpartyOption = computed(() => {
  const data = aggregate(sourceRows.value, r => r.counterpartyName || r.counterparty || '未知对手方').slice(0, 6).reverse()
  return chartBase({ tooltip: { trigger: 'axis' }, grid: { left: 16, right: 22, top: 10, bottom: 10, containLabel: true }, xAxis: { type: 'value', axisLabel: { formatter: value => shortMoney(value) } }, yAxis: { type: 'category', data: data.map(x => x[0]), axisLabel: { width: 100, overflow: 'truncate' } }, series: [{ type: 'bar', data: data.map(x => x[1]), barWidth: 14, itemStyle: { color: '#3796d9', borderRadius: [0, 3, 3, 0] } }] })
})
const heatOption = computed(() => {
  const cells = Array.from({ length: 35 }, (_, i) => [i % 7, Math.floor(i / 7), 0])
  sourceRows.value.forEach(r => {
    const d = new Date(r.transactionDate || r.date)
    if (!Number.isNaN(d.getTime())) cells[(d.getDate() - 1) % 35][2] += Math.abs(Number(r.amount) || 0)
  })
  return chartBase({ tooltip: { formatter: p => `${['周一','周二','周三','周四','周五','周六','周日'][p.data[0]]} · 第${p.data[1] + 1}周<br/>${money(p.data[2])}` }, grid: { left: 45, right: 16, top: 18, bottom: 35 }, xAxis: { type: 'category', data: ['周一','周二','周三','周四','周五','周六','周日'], splitArea: { show: true } }, yAxis: { type: 'category', data: ['第1周','第2周','第3周','第4周','第5周'], splitArea: { show: true } }, visualMap: { min: 0, max: Math.max(...cells.map(x => x[2]), 1), calculable: false, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#edf5f8', '#8ac8d0', '#137f8b'] } }, series: [{ type: 'heatmap', data: cells, emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,.18)' } } }] })
})

function chartBase(option) { return { animationDuration: 500, textStyle: { fontFamily: 'Inter, Microsoft YaHei, sans-serif', color: '#607083' }, color: ['#16a394','#3796d9','#f0b44d','#ee7b55','#7b72c8'], grid: { left: 12, right: 18, top: 42, bottom: 18, containLabel: true }, ...option } }
function aggregate(rows, key) { const map = {}; rows.forEach(r => { const k = key(r); map[k] = (map[k] || 0) + Math.abs(Number(r.amount) || 0) }); return Object.entries(map).sort((a,b) => b[1] - a[1]) }
function isIncome(row) { return ['收入','流入','贷'].some(x => String(row.direction || '').includes(x)) || Number(row.credit) > 0 }
function money(v) { return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(Number(v) || 0) }
function shortMoney(v) { const n = Number(v) || 0; return n >= 10000 ? `${(n / 10000).toFixed(0)}万` : n }
function dateText(v) { return v ? new Date(v).toLocaleDateString('zh-CN') : '-' }
function statusText(v) { return { PENDING: '待处理', PROCESSING: '识别中', COMPLETED: '成功', FAILED: '失败' }[v] || v }
function messageOf(e) { return e?.response?.data?.message || e?.message || '请求失败' }
function downloadReport() { if (activeTask.value) window.open(downloadUrl(activeTask.value.id, 'xlsx'), '_blank') }
function resetTxFilters() { txQuery.value = ''; txDirection.value = 'ALL'; txStart.value = ''; txEnd.value = ''; txMin.value = ''; txMax.value = ''; txPage.value = 1 }
function resultRowFor(row) {
  if (!result.value?.transactions) return null
  const sourceId = row.sourceSection != null && row.sourceRow != null ? `S${row.sourceSection}-R${row.sourceRow}` : row.id
  return result.value.transactions.find(item => item.id === sourceId) || null
}
function syncResultRow(row) {
  const target = resultRowFor(row)
  if (!target) return
  Object.assign(target, { transactionDate: row.transactionDate, amount: row.amount, balance: row.balance, description: row.description, counterparty: row.counterpartyName, counterpartyAccount: row.counterpartyAccount, direction: row.direction, category: row.category, party: row.party, remarks: row.remarks })
}
function exportFilteredCsv() {
  const headers = ['交易日期','交易对手方','摘要','收支方向','金额','余额','分类']
  const quote = value => `"${String(value ?? '').replaceAll('"', '""')}"`
  const lines = filteredRows.value.map(row => [row.transactionDate || row.date, row.counterpartyName || row.counterparty, row.description || row.remarks, row.direction, row.amount, row.balance, row.category].map(quote).join(','))
  const blob = new Blob([`\ufeff${headers.join(',')}\r\n${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `${activeTask.value?.originalFilename || '流水'}_筛选明细.csv`; link.click(); URL.revokeObjectURL(url)
}
function locateSource(row) { sourceRow.value = row }
function openCounterparty(name) { txQuery.value = name; txPage.value = 1; view.value = 'detail' }

async function refresh() {
  try {
    tasks.value = await listTasks()
    await Promise.all(tasks.value.filter(t => t.status === 'COMPLETED').map(async t => { try { t.account = await getAccount(t.id) } catch {} }))
  } catch (e) { error.value = messageOf(e) }
}
async function openTask(task, target = 'records') {
  clearInterval(pollTimer)
  activeTask.value = await getTask(task.id)
  view.value = target
  result.value = null; dbRows.value = []; account.value = null
  if (task.status === 'COMPLETED') {
    const values = await Promise.allSettled([getResult(task.id), getTransactions(task.id), getAccount(task.id)])
    result.value = values[0].value || null; dbRows.value = values[1].value || []; account.value = values[2].value || result.value?.statement || null; resetTxFilters()
  } else if (task.status !== 'FAILED') startPolling(task.id)
}
function startPolling(id) { pollTimer = setInterval(async () => { const task = await getTask(id); activeTask.value = task; await refresh(); if (task.status === 'COMPLETED') { clearInterval(pollTimer); await openTask(task, view.value) } }, 1500) }
async function upload() {
  if (!selectedFile.value) return
  uploading.value = true; error.value = ''
  try { const task = await createTask(selectedFile.value, 'auto', n => uploadProgress.value = n); selectedFile.value = null; await refresh(); await openTask(task) } catch (e) { error.value = messageOf(e) } finally { uploading.value = false }
}
async function remove(task) { if (!confirm(`确定删除“${task.originalFilename}”及其识别数据吗？`)) return; await deleteTask(task.id); if (activeTask.value?.id === task.id) { activeTask.value = null; result.value = null }; await refresh() }
async function removeSelected() { if (!selectedIds.value.length || !confirm(`确定删除选中的 ${selectedIds.value.length} 个文件吗？`)) return; await Promise.all(selectedIds.value.map(deleteTask)); selectedIds.value = []; await refresh() }
function beginRowEdit(row) { Object.assign(editingRow, JSON.parse(JSON.stringify(row))); editRowOpen.value = true }
async function saveRow() {
  syncResultRow(editingRow)
  if (result.value) { await updateResult(activeTask.value.id, result.value); dbRows.value = await getTransactions(activeTask.value.id) }
  else await updateTransaction(editingRow.id, editingRow)
  editRowOpen.value = false
}
async function removeRow(row) {
  if (!confirm('确定删除这条流水吗？')) return
  const target = resultRowFor(row)
  if (target) { result.value.transactions = result.value.transactions.filter(item => item !== target); await updateResult(activeTask.value.id, result.value); dbRows.value = await getTransactions(activeTask.value.id) }
  else { await deleteTransaction(row.id); dbRows.value = dbRows.value.filter(r => r.id !== row.id) }
}
async function saveAccount() {
  account.value = await updateAccount(activeTask.value.id, account.value)
  if (result.value?.statement) { Object.assign(result.value.statement, account.value); await updateResult(activeTask.value.id, result.value) }
  editAccountOpen.value = false; await refresh()
}

onMounted(refresh)
onUnmounted(() => clearInterval(pollTimer))
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <button class="brand" @click="view = 'records'"><span class="brand-mark">V</span><span>流水核查</span></button>
      <nav>
        <button :class="{ active: view === 'records' }" @click="view = 'records'"><Files :size="17" />数据管理</button>
        <button :class="{ active: view === 'detail' }" :disabled="!activeTask" @click="view = 'detail'"><FileSpreadsheet :size="17" />明细查询</button>
        <button :class="{ active: view === 'counterparties' }" :disabled="!activeTask" @click="view = 'counterparties'"><Users :size="17" />对手方</button>
        <button :class="{ active: view === 'report' }" :disabled="!activeTask" @click="view = 'report'"><BarChart3 :size="17" />尽调报告</button>
      </nav>
      <div class="user"><span class="avatar"><UserRound :size="15" /></span><span>尽调项目组</span><ChevronDown :size="14" /></div>
    </header>

    <section class="page-heading">
      <div><p>IPO DUE DILIGENCE</p><h1>{{ view === 'records' ? '数据管理' : view === 'detail' ? '流水明细' : view === 'counterparties' ? '交易对手方' : '尽调分析报告' }}</h1></div>
      <label class="upload-button"><UploadCloud :size="17" /><span>{{ uploading ? `上传中 ${uploadProgress}%` : '上传流水' }}</span><input type="file" @change="selectedFile = $event.target.files[0]; upload()" /></label>
    </section>

    <main v-if="view === 'records'" class="records-layout">
      <aside class="entity-panel">
        <button class="entity-title"><Plus :size="16" />新建主体</button>
        <button class="entity-row" :class="{ active: entityFilter === 'ALL' }" @click="entityFilter = 'ALL'"><span>全部文件</span><b>{{ tasks.length }}</b></button>
        <button v-for="name in entities" :key="name" class="entity-row" :class="{ active: entityFilter === name }" @click="entityFilter = name"><span>{{ name }}</span><b>{{ tasks.filter(t => t.account?.entityName === name).length }}</b></button>
        <div class="quality-box"><CheckCircle2 :size="19" /><div><strong>数据质量良好</strong><span>{{ finishedTasks.length }} 个文件已完成解析</span></div></div>
      </aside>

      <section class="content-panel records-panel">
        <div class="toolbar">
          <div class="toolbar-left"><button class="button danger-outline" :disabled="!selectedIds.length" @click="removeSelected"><Trash2 :size="15" />批量删除</button><button class="icon-button" title="刷新" @click="refresh"><RefreshCw :size="17" /></button></div>
          <div class="filters"><div class="search"><Search :size="16" /><input v-model="query" placeholder="搜索文件名" /></div><select v-model="statusFilter"><option value="ALL">全部状态</option><option value="COMPLETED">成功</option><option value="PROCESSING">识别中</option><option value="FAILED">失败</option></select></div>
        </div>
        <div v-if="error" class="alert"><CircleAlert :size="17" />{{ error }}</div>
        <div class="table-scroll"><table><thead><tr><th class="check"><input type="checkbox" @change="selectedIds = $event.target.checked ? filteredTasks.map(t => t.id) : []" /></th><th>文件名 / 任务信息</th><th>所属主体 / 账户</th><th>上传时间</th><th>状态</th><th>操作</th></tr></thead><tbody>
          <tr v-for="task in filteredTasks" :key="task.id">
            <td class="check"><input v-model="selectedIds" type="checkbox" :value="task.id" /></td>
            <td><button class="file-link" @click="openTask(task, 'detail')"><span class="file-icon">{{ task.fileType?.toUpperCase() }}</span><span><strong>{{ task.originalFilename }}</strong><small>任务 ID · {{ task.id.slice(0, 8) }}</small></span></button></td>
            <td><div class="two-line"><strong>{{ task.account?.entityName || '待识别主体' }}</strong><small>{{ task.account?.bankName || '-' }} · {{ task.account?.accountNumber || '待识别账户' }}</small></div></td>
            <td><div class="two-line"><span>{{ dateText(task.createdAt) }}</span><small>{{ new Date(task.createdAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</small></div></td>
            <td><span class="status" :class="task.status.toLowerCase()"><i />{{ statusText(task.status) }}</span></td>
            <td><div class="actions"><button title="查看" @click="openTask(task, 'detail')"><Search :size="16" /></button><button title="分析" :disabled="task.status !== 'COMPLETED'" @click="openTask(task, 'report')"><BarChart3 :size="16" /></button><button title="删除" @click="remove(task)"><Trash2 :size="16" /></button></div></td>
          </tr></tbody></table></div>
        <div v-if="!filteredTasks.length" class="empty"><Files :size="36" /><strong>暂无匹配的文件记录</strong><span>上传银行流水后会自动归档到这里</span></div>
      </section>
    </main>

    <main v-else-if="view === 'detail'" class="detail-page">
      <section class="context-bar"><div><button class="back-link" @click="view = 'records'">数据管理</button><span>/</span><strong>{{ activeTask?.originalFilename }}</strong></div><div class="context-actions"><button class="button" @click="editAccountOpen = true"><Pencil :size="15" />编辑账户</button><button class="button primary" @click="view = 'report'"><BarChart3 :size="15" />查看分析</button></div></section>
      <section v-if="account" class="account-strip"><div><Building2 /><span>所属主体<strong>{{ account.entityName || '待补充' }}</strong></span></div><div><WalletCards /><span>银行账户<strong>{{ account.bankName || '-' }} · {{ account.accountNumber || '-' }}</strong></span></div><div><CalendarDays /><span>数据期间<strong>{{ account.periodStart || '-' }} 至 {{ account.periodEnd || '-' }}</strong></span></div></section>
      <section class="content-panel transaction-panel"><div class="section-head"><div><h2>结构化流水</h2><p>筛选结果 {{ filteredRows.length }} / 共 {{ sourceRows.length }} 条，{{ reviewRows }} 条需要关注</p></div><button class="button" @click="exportFilteredCsv"><Download :size="15" />导出筛选结果</button></div>
        <div v-if="!sourceRows.length && result?.detectedTables?.length" class="alert table-notice"><CircleAlert :size="17" />该文件包含汇总/分析表，但没有逐笔流水明细，因此不存在可提取的单笔交易日期。下方已按表头自动拆分出 {{ result.detectedTables.length }} 张结构化表。</div>
        <div class="advanced-filters"><div class="search"><Search :size="16" /><input v-model="txQuery" placeholder="搜索对手方、摘要或分类" @input="txPage = 1" /></div><select v-model="txDirection" @change="txPage = 1"><option value="ALL">全部收支</option><option value="IN">仅流入</option><option value="OUT">仅流出</option></select><input v-model="txStart" type="date" @change="txPage = 1" /><span>至</span><input v-model="txEnd" type="date" @change="txPage = 1" /><input v-model="txMin" type="number" placeholder="最小金额" @input="txPage = 1" /><input v-model="txMax" type="number" placeholder="最大金额" @input="txPage = 1" /><button class="icon-button" title="清除筛选" @click="resetTxFilters"><FilterX :size="16" /></button></div>
        <div class="table-scroll"><table><thead><tr><th>交易日期</th><th>交易对手方</th><th>摘要</th><th>收支方向</th><th class="number">金额（元）</th><th class="number">余额（元）</th><th>分类</th><th>操作</th></tr></thead><tbody><tr v-for="row in pagedRows" :key="row.id"><td>{{ row.transactionDate || row.date || '-' }}</td><td><strong>{{ row.counterpartyName || row.counterparty || '-' }}</strong></td><td class="description">{{ row.description || row.remarks || '-' }}</td><td><span class="direction" :class="isIncome(row) ? 'income' : 'expense'">{{ row.direction || '-' }}</span></td><td class="number amount" :class="isIncome(row) ? 'income-text' : 'expense-text'">{{ money(row.amount) }}</td><td class="number">{{ money(row.balance) }}</td><td><span class="category">{{ row.category || '其他' }}</span></td><td><div class="actions"><button title="定位原文" @click="locateSource(row)"><LocateFixed :size="15" /></button><button title="编辑" @click="beginRowEdit(row)"><Pencil :size="15" /></button><button title="删除" @click="removeRow(row)"><Trash2 :size="15" /></button></div></td></tr></tbody></table></div>
        <div class="pagination"><span>第 {{ txPage }} / {{ pageCount }} 页</span><div><button :disabled="txPage <= 1" @click="txPage--">上一页</button><button :disabled="txPage >= pageCount" @click="txPage++">下一页</button></div></div>
      </section>
      <section v-if="result?.detectedTables?.length" class="detected-tables">
        <article v-for="table in result.detectedTables" :key="table.id" class="content-panel detected-table">
          <div class="section-head"><div><h2>{{ table.title || table.source }}</h2><p>{{ ({ transaction_detail: '流水明细', account_summary: '账户信息', counterparty_analysis: '对手方分析', monthly_summary: '月度统计', category_summary: '分类汇总', quality_or_risk: '质量/风险', structured_table: '结构化表' })[table.type] || table.type }} · {{ table.rowCount }} 行</p></div></div>
          <div class="table-scroll"><table><thead><tr><th v-for="(header, index) in table.headers" :key="index">{{ header || '序号' }}</th></tr></thead><tbody><tr v-for="(row, rowIndex) in table.rows" :key="rowIndex"><td v-for="(_, colIndex) in table.headers" :key="colIndex">{{ row[colIndex] ?? '' }}</td></tr></tbody></table></div>
        </article>
      </section>
    </main>

    <main v-else-if="view === 'counterparties'" class="detail-page">
      <section class="context-bar"><div><button class="back-link" @click="view = 'records'">数据管理</button><span>/</span><strong>{{ activeTask?.originalFilename }}</strong></div><button class="button primary" @click="view = 'report'"><BarChart3 :size="15" />查看分析</button></section>
      <section class="content-panel counterparty-panel"><div class="section-head"><div><h2>交易对手方</h2><p>共识别 {{ counterparties.length }} 个对手方，按交易规模排序</p></div><div class="search"><Search :size="16" /><input v-model="counterpartyQuery" placeholder="搜索名称、账号或摘要" /></div></div>
        <div class="counterparty-list"><article v-for="party in counterparties" :key="party.name" class="counterparty-item"><button class="counterparty-summary" @click="expandedCounterparty = expandedCounterparty === party.name ? '' : party.name"><span class="party-avatar">{{ party.name.slice(0, 1) }}</span><span class="party-name"><strong>{{ party.name }}</strong><small>{{ party.rows.length }} 笔交易 · 最近 {{ party.latestDate || '-' }}</small></span><span><small>资金流入</small><strong class="income-text">{{ money(party.income) }}</strong></span><span><small>资金流出</small><strong class="expense-text">{{ money(party.expense) }}</strong></span><ChevronDown :class="{ rotated: expandedCounterparty === party.name }" /></button>
          <div v-if="expandedCounterparty === party.name" class="party-transactions"><div v-for="row in party.rows" :key="row.id" class="party-transaction"><span>{{ row.transactionDate || '-' }}</span><span class="description">{{ row.description || row.remarks || '-' }}</span><strong :class="isIncome(row) ? 'income-text' : 'expense-text'">{{ money(row.amount) }}</strong><button @click="locateSource(row)"><LocateFixed :size="14" />定位原文</button></div><button class="view-all" @click="openCounterparty(party.name)">查看全部流水<ArrowRight :size="15" /></button></div>
        </article></div><div v-if="!counterparties.length" class="empty"><Users :size="36" /><strong>未找到匹配的对手方</strong></div>
      </section>
    </main>

    <main v-else class="report-page">
      <section class="report-toolbar"><div><span class="report-label">分析对象</span><strong>{{ account?.entityName || activeTask?.originalFilename }}</strong><span class="period">{{ account?.periodStart || '数据起始日' }} 至 {{ account?.periodEnd || '数据截止日' }}</span></div><button class="button primary" @click="downloadReport"><Download :size="16" />导出尽调报告</button></section>
      <section class="metric-grid"><article><span>资金流入</span><strong>{{ money(totalIn) }}</strong><small><i class="dot teal" />{{ sourceRows.filter(isIncome).length }} 笔收入</small></article><article><span>资金流出</span><strong>{{ money(totalOut) }}</strong><small><i class="dot coral" />{{ sourceRows.filter(r => !isIncome(r)).length }} 笔支出</small></article><article><span>净现金流</span><strong :class="totalIn - totalOut < 0 ? 'expense-text' : 'income-text'">{{ money(totalIn - totalOut) }}</strong><small>流入 / 流出 {{ totalOut ? (totalIn / totalOut).toFixed(2) : '-' }}</small></article><article><span>风险提示</span><strong>{{ reviewRows }}</strong><small><i class="dot amber" />待人工复核记录</small></article></section>
      <section class="chart-grid"><article class="chart-card wide"><div class="chart-title"><div><h3>月度收支趋势</h3><p>识别资金波动与跨期异常</p></div></div><EChart :option="monthlyOption" /></article><article class="chart-card"><div class="chart-title"><div><h3>收支构成</h3><p>按交易分类汇总</p></div></div><EChart :option="categoryOption" /></article><article class="chart-card"><div class="chart-title"><div><h3>核心交易对手</h3><p>按累计交易金额排序</p></div></div><EChart :option="counterpartyOption" /></article><article class="chart-card wide"><div class="chart-title"><div><h3>交易活跃度热力图</h3><p>按星期与月内周次观察交易集中情况</p></div></div><EChart :option="heatOption" /></article></section>
    </main>

    <div v-if="editAccountOpen" class="modal-mask" @click.self="editAccountOpen = false"><form class="modal" @submit.prevent="saveAccount"><div class="modal-head"><div><h2>编辑主体与账户</h2><p>修改文件的归属和账户基础信息</p></div><button type="button" class="icon-button" @click="editAccountOpen = false"><X /></button></div><div class="form-grid"><label><span>主体名称</span><input v-model="account.entityName" /></label><label><span>开户银行</span><input v-model="account.bankName" /></label><label><span>银行账号</span><input v-model="account.accountNumber" /></label><label><span>币种</span><select v-model="account.currency"><option>CNY</option><option>USD</option><option>HKD</option></select></label><label><span>开始日期</span><input v-model="account.periodStart" type="date" /></label><label><span>结束日期</span><input v-model="account.periodEnd" type="date" /></label></div><div class="modal-actions"><button type="button" class="button" @click="editAccountOpen = false">取消</button><button class="button primary">保存修改</button></div></form></div>
    <div v-if="editRowOpen" class="modal-mask" @click.self="editRowOpen = false"><form class="modal" @submit.prevent="saveRow"><div class="modal-head"><div><h2>修改流水</h2><p>校正识别后的结构化交易数据</p></div><button type="button" class="icon-button" @click="editRowOpen = false"><X /></button></div><div class="form-grid"><label><span>交易日期</span><input v-model="editingRow.transactionDate" type="date" /></label><label><span>交易对手方</span><input v-model="editingRow.counterpartyName" /></label><label><span>交易金额</span><input v-model.number="editingRow.amount" type="number" step="0.01" /></label><label><span>账户余额</span><input v-model.number="editingRow.balance" type="number" step="0.01" /></label><label><span>交易分类</span><input v-model="editingRow.category" /></label><label><span>对手方类型</span><input v-model="editingRow.counterpartyType" /></label><label class="full"><span>交易摘要</span><textarea v-model="editingRow.description" rows="3" /></label></div><div class="modal-actions"><button type="button" class="button" @click="editRowOpen = false">取消</button><button class="button primary">保存修改</button></div></form></div>
    <div v-if="sourceRow" class="drawer-mask" @click.self="sourceRow = null"><aside class="source-drawer"><div class="modal-head"><div><h2>源文件交易定位</h2><p>{{ activeTask?.originalFilename }}</p></div><button class="icon-button" @click="sourceRow = null"><X /></button></div><div class="locator-meta"><span>来源位置<strong>片段 {{ sourceRow.sourceSection ?? '-' }} · 行 {{ sourceRow.sourceRow ?? '-' }}</strong></span><span>交易对手<strong>{{ sourceRow.counterpartyName || sourceRow.counterparty || '-' }}</strong></span><span>交易金额<strong>{{ money(sourceRow.amount) }}</strong></span></div><div class="source-content"><div class="source-label"><span>识别源片段</span><b>{{ sourceSection?.source || '未记录来源页/工作表' }}</b></div><pre>{{ sourceSection?.text || '该笔交易暂时没有可显示的源文本。' }}</pre><div v-if="sourceSection?.tableRows?.length" class="source-table"><div v-for="(cells,index) in sourceSection.tableRows" :key="index" :class="{ highlighted: index === sourceRow.sourceRow }"><span v-for="(cell,cellIndex) in cells" :key="cellIndex">{{ cell }}</span></div></div></div><div class="drawer-note"><CircleAlert :size="16" />定位依据来自识别时保存的来源段和来源行，不会跳转到无关的文件首页。</div></aside></div>
  </div>
</template>
