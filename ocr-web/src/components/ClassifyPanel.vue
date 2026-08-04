<script setup>
import { computed, onMounted, ref } from 'vue'
import { classifyTransactions, testLlmConnection } from '../api'
import { LLM_PROVIDERS, loadLlmSettings, saveLlmSettings } from '../llm-presets'

const props = defineProps({
  taskId: { type: String, required: true },
})

// --------------- LLM 设置 ---------------
const showSettings = ref(false)
const selectedProvider = ref('custom')
const llmSettings = ref({ apiUrl: '', apiKey: '', model: '' })
const testStatus = ref(null)

// 状态
const loading = ref(false)
const error = ref('')
const classifyResult = ref(null)

// 恢复保存的设置
onMounted(() => {
  const saved = loadLlmSettings()
  if (saved) {
    Object.assign(llmSettings.value, saved)
    selectedProvider.value = saved.provider || 'custom'
  }
})

const currentProvider = computed(() => LLM_PROVIDERS[selectedProvider.value] || LLM_PROVIDERS.custom)

// --------------- 方法 ---------------

function selectProvider(key) {
  selectedProvider.value = key
  const p = LLM_PROVIDERS[key]
  llmSettings.value.apiUrl = p.apiUrl
  if (p.models.length > 0) llmSettings.value.model = p.models[0]
  testStatus.value = null
  saveState()
}

function saveState() {
  saveLlmSettings({ ...llmSettings.value, provider: selectedProvider.value })
}

function showApiKey() {
  const el = document.getElementById('classify-api-key')
  if (el) el.type = el.type === 'password' ? 'text' : 'password'
}

async function testConnection() {
  testStatus.value = null
  saveState()
  try {
    const res = await testLlmConnection(llmSettings.value)
    testStatus.value = { ok: res.success, message: res.message }
  } catch (e) {
    testStatus.value = { ok: false, message: e?.response?.data?.message || e.message || '测试失败' }
  }
}

async function startClassify() {
  if (!llmSettings.value.apiUrl || !llmSettings.value.model) {
    error.value = '请先配置 API 地址和模型名称'
    return
  }
  saveState()
  loading.value = true
  error.value = ''
  classifyResult.value = null
  try {
    const res = await classifyTransactions(props.taskId, { llm: llmSettings.value })
    classifyResult.value = res
  } catch (e) {
    error.value = e?.response?.data?.message || e.message || '分类失败'
  } finally {
    loading.value = false
  }
}

// 分类统计
const categoryStats = computed(() => {
  if (!classifyResult.value?.results) return []
  const map = {}
  for (const r of classifyResult.value.results) {
    const cat = r.category || '其他'
    map[cat] = (map[cat] || 0) + 1
  }
  return Object.entries(map).sort((a, b) => b[1] - a[1])
})
</script>

<template>
  <div class="classify-panel">
    <!-- ====== 标题栏 ====== -->
    <div class="cp-titlebar">
      <div>
        <span class="eyebrow">LLM 分类</span>
        <h3>🤖 AI 自动分类</h3>
      </div>
      <button class="ghost sm" @click="showSettings = !showSettings">
        模型设置 {{ showSettings ? '▲' : '▼' }}
      </button>
    </div>

    <!-- ====== 模型设置区 ====== -->
    <div v-if="showSettings" class="cp-settings">
      <div class="cp-presets">
        <span class="cp-presets-label">快速选择:</span>
        <button
          v-for="(provider, key) in LLM_PROVIDERS" :key="key"
          class="ghost sm" :class="{ 'cp-pill-on': selectedProvider === key }"
          @click="selectProvider(key)"
        >{{ provider.name }}</button>
      </div>

      <div class="cp-form">
        <label>
          <span>API 地址</span>
          <input v-model="llmSettings.apiUrl" type="text" placeholder="https://api.openai.com/v1" @change="saveState" />
        </label>
        <label>
          <span>API Key</span>
          <div class="cp-key-row">
            <input id="classify-api-key" v-model="llmSettings.apiKey" type="password"
              :placeholder="currentProvider.keyPlaceholder || 'sk-xxxx'" @change="saveState" />
            <button type="button" class="ghost sm" @click="showApiKey">显示</button>
          </div>
        </label>
        <label>
          <span>模型名称</span>
          <input v-model="llmSettings.model" type="text" list="classify-model-list"
            :placeholder="currentProvider.models.length ? '选择或输入模型' : '输入模型名'" @change="saveState" />
          <datalist id="classify-model-list">
            <option v-for="m in currentProvider.models" :key="m" :value="m" />
          </datalist>
        </label>
      </div>

      <div class="cp-test">
        <button class="secondary sm" @click="testConnection">测试连接</button>
        <span v-if="testStatus" class="cp-test-result" :class="{ ok: testStatus.ok, fail: !testStatus.ok }">
          {{ testStatus.ok ? '✅' : '❌' }} {{ testStatus.message }}
        </span>
      </div>
    </div>

    <!-- ====== 操作栏 ====== -->
    <div class="cp-actions">
      <p class="cp-hint">使用大模型自动给每笔交易打上分类标签和对手方类型，结果写入数据库后可在交易表中手动修正。</p>
      <button class="primary" :disabled="loading || !llmSettings.apiUrl || !llmSettings.model" @click="startClassify">
        {{ loading ? '分类中...' : '开始 AI 自动分类' }}
      </button>
    </div>

    <p v-if="error" class="error" style="margin: 0 18px 12px;">{{ error }}</p>

    <!-- ====== 加载中 ====== -->
    <div v-if="loading" class="progress-panel">
      <div class="progress-track"><span style="width: 100%; animation: cp-progress 2s ease-in-out infinite;"></span></div>
      <p>正在调用 {{ llmSettings.model }} 分析 {{ classifyResult?.total || '...' }} 条交易……</p>
    </div>

    <!-- ====== 分类结果 ====== -->
    <div v-if="classifyResult?.success" class="cp-result">
      <div class="cp-result-head">
        <span class="status completed">✅ 分类完成</span>
        <span class="cp-meta">已分类 {{ classifyResult.classified }}/{{ classifyResult.total }} 条</span>
        <span class="cp-meta">模型: {{ classifyResult.modelUsed }}</span>
        <span class="cp-meta">耗时: {{ (classifyResult.processingTimeMs / 1000).toFixed(1) }}s</span>
      </div>
      <div v-if="categoryStats.length" class="cp-stats">
        <span v-for="[cat, count] in categoryStats" :key="cat" class="cp-tag">
          {{ cat }} ×{{ count }}
        </span>
      </div>
    </div>

    <!-- ====== 失败 ====== -->
    <div v-if="classifyResult && !classifyResult.success" class="error" style="margin: 14px 18px;">
      ❌ 分类失败: {{ classifyResult.message }}
    </div>
  </div>
</template>

<style scoped>
.classify-panel {
  margin-top: 20px;
  border: 1px solid #dfe7ee;
  border-radius: 18px;
  background: white;
  box-shadow: 0 9px 28px rgba(31, 61, 88, .07);
  overflow: hidden;
}

.cp-titlebar {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  padding: 24px 24px 18px;
}
.cp-titlebar .eyebrow {
  color: #5b7188; font-size: 11px; font-weight: 800;
  letter-spacing: .16em; text-transform: uppercase;
}
.cp-titlebar h3 { margin: 5px 0 0; font-size: 18px; color: #162235; font-weight: 750; }

/* 复用全局按钮样式 */
.ghost.sm, .secondary.sm {
  padding: 6px 13px; font-size: 12px; border-radius: 10px; font-weight: 800; border: 0;
}
.ghost.sm { color: #31516d; background: #edf3f7; }
.ghost.sm:hover { background: #dfe6ee; }
.secondary.sm { color: #34516b; background: #edf2f6; }
.secondary.sm:hover { background: #dfe6ee; }
.cp-pill-on { background: #0a6572 !important; color: white !important; }

/* 设置区 */
.cp-settings {
  padding: 14px 24px 18px;
  border-top: 1px solid #e6ecf1; border-bottom: 1px solid #e6ecf1;
  background: #f8fafc;
}
.cp-presets { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
.cp-presets-label { font-size: 12px; color: #5b7188; font-weight: 700; }
.cp-form { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
.cp-form label { display: flex; flex-direction: column; gap: 4px; }
.cp-form label > span { font-size: 12px; font-weight: 700; color: #51677d; }
.cp-form input {
  height: 39px; padding: 0 10px;
  border: 1px solid #cdd8e2; border-radius: 10px;
  font-size: 13px; color: #24384c; background: white; width: 100%;
}
.cp-form input:focus { outline: none; border-color: #0a6572; }
.cp-key-row { display: flex; gap: 4px; }
.cp-key-row input { flex: 1; }

.cp-test { margin-top: 14px; display: flex; align-items: center; gap: 12px; }
.cp-test-result { font-size: 13px; }
.cp-test-result.ok { color: #08755b; }
.cp-test-result.fail { color: #a22b36; }

/* 操作栏 */
.cp-actions {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 24px; gap: 12px;
}
.cp-hint { color: #73869a; font-size: 12px; max-width: 420px; margin: 0; }

/* 结果 */
.cp-result { border-top: 1px solid #e6ecf1; }
.cp-result-head {
  display: flex; align-items: center; gap: 14px; padding: 12px 24px;
  background: #dcf6eb; flex-wrap: wrap;
}
.cp-result-head .status {
  font-weight: 800; font-size: 11px; padding: 5px 10px; border-radius: 999px;
}
.cp-meta { font-size: 11px; color: #41637e; }
.cp-stats { padding: 12px 24px; display: flex; gap: 6px; flex-wrap: wrap; }
.cp-tag {
  padding: 3px 10px; border-radius: 999px;
  background: #edf3f7; color: #31516d; font-size: 11px; font-weight: 700;
}

@keyframes cp-progress {
  0% { width: 20%; } 50% { width: 90%; } 100% { width: 20%; }
}

@media (max-width: 768px) {
  .cp-form { grid-template-columns: 1fr; }
  .cp-actions { flex-direction: column; align-items: flex-start; }
}
</style>
