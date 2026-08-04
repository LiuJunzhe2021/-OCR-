<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { createTask, deleteTask, downloadUrl, getResult, getTask, listTasks, updateResult } from './api'
import ClassifyPanel from './components/ClassifyPanel.vue'
import DbViewPanel from './components/DbViewPanel.vue'

const selectedFile = ref(null)
const mode = ref('auto')
const uploading = ref(false)
const uploadProgress = ref(0)
const tasks = ref([])
const activeTask = ref(null)
const result = ref(null)
const error = ref('')
const dragActive = ref(false)
const saving = ref(false)
const saved = ref(false)
let pollTimer = null

const isFinished = computed(() => activeTask.value?.status === 'COMPLETED')
const reviewCount = computed(() => result.value?.summary?.manualReviewCount || 0)
const transactions = computed(() => result.value?.transactions || [])
const transactionIssueCount = computed(() => transactions.value.reduce((total, item) => total + (item.validations?.length || 0), 0))

function chooseFile(file) {
  if (!file) return
  selectedFile.value = file
  error.value = ''
}

function onFileInput(event) {
  chooseFile(event.target.files?.[0])
}

function onDrop(event) {
  dragActive.value = false
  chooseFile(event.dataTransfer.files?.[0])
}

async function refreshTasks() {
  try {
    tasks.value = await listTasks()
  } catch (exception) {
    error.value = messageOf(exception)
  }
}

async function submit() {
  if (!selectedFile.value || uploading.value) return
  uploading.value = true
  uploadProgress.value = 0
  error.value = ''
  result.value = null
  try {
    const task = await createTask(selectedFile.value, mode.value, (value) => {
      uploadProgress.value = value
    })
    activeTask.value = task
    selectedFile.value = null
    await refreshTasks()
    startPolling(task.id)
  } catch (exception) {
    error.value = messageOf(exception)
  } finally {
    uploading.value = false
  }
}

async function openTask(task) {
  stopPolling()
  activeTask.value = await getTask(task.id)
  result.value = null
  if (activeTask.value.status === 'COMPLETED') {
    result.value = await getResult(task.id)
  } else if (activeTask.value.status !== 'FAILED') {
    startPolling(task.id)
  }
}

function startPolling(id) {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    try {
      activeTask.value = await getTask(id)
      await refreshTasks()
      if (activeTask.value.status === 'COMPLETED') {
        result.value = await getResult(id)
        stopPolling()
      } else if (activeTask.value.status === 'FAILED') {
        stopPolling()
      }
    } catch (exception) {
      error.value = messageOf(exception)
      stopPolling()
    }
  }, 1500)
}

function stopPolling() {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = null
}

async function removeTask(task) {
  if (!window.confirm(`删除任务“${task.originalFilename}”？`)) return
  await deleteTask(task.id)
  if (activeTask.value?.id === task.id) {
    activeTask.value = null
    result.value = null
  }
  await refreshTasks()
}

function download(type) {
  if (activeTask.value) window.open(downloadUrl(activeTask.value.id, type), '_blank')
}

async function saveResult() {
  if (!activeTask.value || !result.value || saving.value) return
  saving.value = true
  saved.value = false
  error.value = ''
  try {
    result.value = await updateResult(activeTask.value.id, result.value)
    saved.value = true
    window.setTimeout(() => { saved.value = false }, 2500)
  } catch (exception) {
    error.value = messageOf(exception)
  } finally {
    saving.value = false
  }
}

function addTransaction() {
  if (!result.value.transactions) result.value.transactions = []
  result.value.transactions.push({
    id: `MANUAL-${Date.now()}`, transactionDate: '', party: result.value.statement?.entityName || '',
    counterparty: '', transactionNature: '', remarks: '', date: '', description: '',
    counterpartyAccount: '', debit: null, credit: null, amount: null,
    direction: '支出', balance: null, currency: 'CNY', category: '其他',
    validations: [], manualReviewRequired: true, source: '人工新增',
  })
}

function removeTransaction(index) {
  if (window.confirm('确定删除这条流水吗？')) result.value.transactions.splice(index, 1)
}

function issueText(item) {
  return item.validations?.map((issue) => issue.message).join('；') || '通过'
}

function statusLabel(status) {
  return { PENDING: '等待处理', PROCESSING: '识别中', COMPLETED: '已完成', FAILED: '失败' }[status] || status
}

function confidence(value) {
  return value == null ? '—' : `${(Number(value) * 100).toFixed(1)}%`
}

function messageOf(exception) {
  return exception?.response?.data?.message || exception?.message || '请求失败'
}

onMounted(refreshTasks)
onUnmounted(stopPolling)
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="logo">P</div>
      <div>
        <h1>智能文档识别与复核</h1>
        <p>PaddleOCR主识别 · pandas/pdfplumber原生解析 · Excel人工复核</p>
      </div>
    </header>

    <main class="workspace">
      <section class="left-column">
        <article class="card upload-card">
          <div class="card-title">
            <div><span class="eyebrow">新建任务</span><h2>上传待识别文档</h2></div>
            <span class="model-badge">PaddleOCR Primary</span>
          </div>

          <label
            class="dropzone"
            :class="{ active: dragActive, ready: selectedFile }"
            @dragenter.prevent="dragActive = true"
            @dragover.prevent
            @dragleave.prevent="dragActive = false"
            @drop.prevent="onDrop"
          >
            <input type="file" @change="onFileInput" />
            <span class="upload-icon">⇧</span>
            <strong>{{ selectedFile ? selectedFile.name : '拖入文件或点击选择' }}</strong>
            <small>PDF、Word、Excel、PNG/JPG/TIFF，单文件不超过50MB</small>
          </label>

          <div class="form-row">
            <label>
              <span>PDF处理模式</span>
              <select v-model="mode">
                <option value="auto">自动判断（推荐）</option>
                <option value="native">只读取文本层</option>
                <option value="ocr">所有页面强制OCR</option>
              </select>
            </label>
            <button class="primary" :disabled="!selectedFile || uploading" @click="submit">
              {{ uploading ? `上传中 ${uploadProgress}%` : '开始识别' }}
            </button>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
        </article>

        <article class="card history-card">
          <div class="card-title compact"><div><span class="eyebrow">最近任务</span><h2>处理记录</h2></div><button class="ghost" @click="refreshTasks">刷新</button></div>
          <div v-if="!tasks.length" class="empty">还没有识别任务</div>
          <div v-for="task in tasks" :key="task.id" class="task-row" :class="{ selected: activeTask?.id === task.id }" @click="openTask(task)">
            <span class="file-type">{{ task.fileType.toUpperCase() }}</span>
            <div class="task-main"><strong>{{ task.originalFilename }}</strong><small>{{ new Date(task.createdAt).toLocaleString() }}</small></div>
            <span class="status" :class="task.status.toLowerCase()">{{ statusLabel(task.status) }}</span>
            <button class="delete" title="删除" @click.stop="removeTask(task)">×</button>
          </div>
        </article>
      </section>

      <section class="right-column">
        <article v-if="!activeTask" class="card result-placeholder">
          <div class="placeholder-icon">文</div>
          <h2>选择任务查看结果</h2>
          <p>识别完成后可下载带公式、可编辑、带条件标色的人工复核Excel。</p>
        </article>

        <article v-else class="card result-card">
          <div class="result-head">
            <div><span class="eyebrow">任务详情</span><h2>{{ activeTask.originalFilename }}</h2></div>
            <span class="status large" :class="activeTask.status.toLowerCase()">{{ statusLabel(activeTask.status) }}</span>
          </div>

          <div v-if="!isFinished" class="progress-panel">
            <div class="progress-track"><span :style="{ width: `${activeTask.progress}%` }"></span></div>
            <p v-if="activeTask.status !== 'FAILED'">正在进行文档分流和多模型识别，请稍候……</p>
            <p v-else class="error">{{ activeTask.errorMessage }}</p>
          </div>

          <template v-if="result">
            <div class="summary-grid">
              <div><span>解析片段</span><strong>{{ result.summary?.sectionCount || 0 }}</strong></div>
              <div><span>待人工复核</span><strong :class="{ danger: reviewCount }">{{ reviewCount }}</strong></div>
              <div><span>标准流水</span><strong>{{ transactions.length }}</strong></div>
              <div><span>校验问题</span><strong :class="{ danger: transactionIssueCount }">{{ transactionIssueCount }}</strong></div>
            </div>

            <div class="download-bar">
              <button class="excel" @click="download('xlsx')">下载人工复核 Excel</button>
              <button class="secondary" @click="download('json')">JSON</button>
              <button class="secondary" @click="download('txt')">TXT</button>
            </div>

            <section v-if="result.statement" class="statement-panel">
              <div class="panel-title">
                <div><span class="eyebrow">统一主体信息</span><h3>账户与文件归属</h3></div>
                <span class="validation-state" :class="result.validation?.status?.toLowerCase()">
                  {{ result.validation?.status === 'PASS' ? '校验通过' : '需要复核' }}
                </span>
              </div>
              <div class="metadata-form">
                <label><span>主体名称</span><input v-model="result.statement.entityName" placeholder="待补充" /></label>
                <label><span>银行</span><input v-model="result.statement.bankName" placeholder="待识别" /></label>
                <label><span>账号</span><input v-model="result.statement.accountNumber" placeholder="待识别" /></label>
                <label><span>账户类型</span><select v-model="result.statement.accountType"><option>对公</option><option>对私</option><option>未知</option></select></label>
              </div>
              <div v-if="result.validation?.issues?.length" class="validation-list">
                <span v-for="issue in result.validation.issues" :key="issue.code">{{ issue.message }}</span>
              </div>
            </section>

            <section class="transaction-panel">
              <div class="panel-title">
                <div><span class="eyebrow">标准化结果</span><h3>结构化银行流水</h3></div>
                <div class="panel-actions"><button class="ghost" @click="addTransaction">新增一行</button><button class="primary compact-button" :disabled="saving" @click="saveResult">{{ saving ? '保存中…' : '保存修订' }}</button></div>
              </div>
              <p v-if="saved" class="save-success">修订结果已保存</p>
              <div v-if="!transactions.length" class="empty compact-empty">未找到标准流水表头，可在此人工新增，或查看下方原始识别结果。</div>
              <div v-else class="transaction-table-wrap">
                <table class="transaction-table">
                  <thead><tr><th>交易日期</th><th>交易方</th><th>对手方</th><th>交易性质</th><th>金额</th><th>备注</th><th>自动分类</th><th>校验</th><th></th></tr></thead>
                  <tbody>
                    <tr v-for="(item, index) in transactions" :key="item.id" :class="{ 'needs-review': item.manualReviewRequired }">
                      <td><input v-model="item.transactionDate" type="date" /></td>
                      <td><input v-model="item.party" /></td>
                      <td><input v-model="item.counterparty" /></td>
                      <td><input v-model="item.transactionNature" /></td>
                      <td><input v-model.number="item.amount" type="number" step="0.01" /></td>
                      <td><input v-model="item.remarks" /></td>
                      <td><select v-model="item.category"><option v-for="name in ['工资薪酬','税费','采购付款','销售回款','费用报销','银行费用','利息','内部转账','融资','其他']" :key="name">{{ name }}</option></select></td>
                      <td><span class="row-validation" :class="{ pass: !item.validations?.length }" :title="issueText(item)">{{ issueText(item) }}</span></td>
                      <td><button class="delete row-delete" title="删除流水" @click="removeTransaction(index)">×</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <div v-if="result.warnings?.length" class="warning-box">
              <strong>处理警告</strong><span v-for="warning in result.warnings" :key="warning">{{ warning }}</span>
            </div>

            <ClassifyPanel :task-id="activeTask.id" />

            <DbViewPanel :task-id="activeTask.id" />

            <div class="section-list">
              <details v-for="(item, index) in result.sections" :key="`${item.source}-${index}`" :open="index === 0">
                <summary>
                  <span>{{ item.source }}</span>
                  <span class="method">{{ item.method }}</span>
                  <span v-if="item.metadata?.confidence != null" class="confidence">{{ confidence(item.metadata.confidence) }}</span>
                  <span v-if="item.metadata?.manualReviewRequired" class="review-tag">需复核</span>
                </summary>
                <pre>{{ item.text || '（无文本）' }}</pre>
                <details v-if="item.metadata?.candidates?.length" class="candidate-details">
                  <summary>查看多模型候选</summary>
                  <div v-for="candidate in item.metadata.candidates" :key="candidate.engine" class="candidate">
                    <strong>{{ candidate.engine }} · {{ confidence(candidate.confidence) }}</strong>
                    <pre>{{ candidate.text }}</pre>
                  </div>
                </details>
              </details>
            </div>
          </template>
        </article>
      </section>
    </main>
  </div>
</template>
