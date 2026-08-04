<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { createTask, deleteTask, downloadUrl, getResult, getTask, listTasks } from './api'

const selectedFile = ref(null)
const mode = ref('auto')
const uploading = ref(false)
const uploadProgress = ref(0)
const tasks = ref([])
const activeTask = ref(null)
const result = ref(null)
const error = ref('')
const dragActive = ref(false)
let pollTimer = null

const isFinished = computed(() => activeTask.value?.status === 'COMPLETED')
const reviewCount = computed(() => result.value?.summary?.manualReviewCount || 0)

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
              <div><span>主要模型</span><strong>PaddleOCR</strong></div>
            </div>

            <div class="download-bar">
              <button class="excel" @click="download('xlsx')">下载人工复核 Excel</button>
              <button class="secondary" @click="download('json')">JSON</button>
              <button class="secondary" @click="download('txt')">TXT</button>
            </div>

            <div v-if="result.warnings?.length" class="warning-box">
              <strong>处理警告</strong><span v-for="warning in result.warnings" :key="warning">{{ warning }}</span>
            </div>

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
