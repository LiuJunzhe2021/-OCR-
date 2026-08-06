<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  classifyTransactions, auditTransactions, correctTransactions,
  fillTransactions, testLlmConnection,
} from '../api'
import { LLM_PROVIDERS, loadLlmSettings, saveLlmSettings } from '../llm-presets'

const props = defineProps({
  taskId: { type: String, required: true },
  transactionCount: { type: Number, default: 0 },
})
const emit = defineEmits(['completed'])

// 模式
const modes = [
  { key: 'classify', label: '自动分类', desc: '给每笔交易打上分类标签（经营收入/人力成本…）', icon: '🏷' },
  { key: 'audit', label: '智能审核', desc: '扫描所有交易，标记金额异常、重复、夜间转账等风险', icon: '🔍' },
  { key: 'correct', label: 'OCR纠错', desc: '对比原文发现识别错误（形近字、小数点错位…）并修正', icon: '✏️' },
  { key: 'fill', label: '缺失补全', desc: '对空字段（摘要/方向）根据上下文推断补全', icon: '📝' },
]
const activeMode = ref('classify')

// LLM 设置
const showSettings = ref(false)
const selectedProvider = ref('deepseek')
const llmSettings = ref({ apiUrl: '', apiKey: '', model: '' })
const testStatus = ref(null)

// 状态
const loading = ref(false)
const error = ref('')
const analyzeResult = ref(null)

onMounted(() => {
  const saved = loadLlmSettings()
  if (saved) {
    Object.assign(llmSettings.value, saved)
    selectedProvider.value = saved.provider || 'deepseek'
  }
})

const currentProvider = computed(() => LLM_PROVIDERS[selectedProvider.value] || LLM_PROVIDERS.custom)

function selectProvider(key) {
  selectedProvider.value = key
  const p = LLM_PROVIDERS[key]
  llmSettings.value.apiUrl = p.apiUrl
  if (p.models.length > 0) llmSettings.value.model = p.models[0]
  testStatus.value = null
  saveState()
}
function saveState() { saveLlmSettings({ ...llmSettings.value, provider: selectedProvider.value }) }
function showApiKey() {
  const el = document.getElementById('classify-api-key')
  if (el) el.type = el.type === 'password' ? 'text' : 'password'
}
async function testConnection() {
  testStatus.value = null; saveState()
  try {
    const res = await testLlmConnection(llmSettings.value)
    testStatus.value = { ok: res.success, message: res.message }
  } catch (e) {
    testStatus.value = { ok: false, message: e?.response?.data?.message || e.message || '测试失败' }
  }
}

const modeActions = {
  classify: classifyTransactions,
  audit: auditTransactions,
  correct: correctTransactions,
  fill: fillTransactions,
}

async function startAnalyze() {
  if (!props.transactionCount) {
    error.value = '当前文件只有汇总分析表，没有逐笔交易；LLM 分类、审核和纠错需要上传原始银行流水明细。'; return
  }
  if (!llmSettings.value.apiUrl || !llmSettings.value.model) {
    error.value = '请先配置 API 地址和模型名称'; return
  }
  saveState()
  loading.value = true; error.value = ''; analyzeResult.value = null
  try {
    const fn = modeActions[activeMode.value]
    analyzeResult.value = await fn(props.taskId, { llm: llmSettings.value })
    if (analyzeResult.value?.success) emit('completed')
  } catch (e) {
    error.value = e?.response?.data?.message || e.message || '分析失败'
  } finally { loading.value = false }
}

const currentMode = computed(() => modes.find(m => m.key === activeMode.value))
</script>

<template>
  <div class="classify-panel">
    <!-- ====== 标题栏 ====== -->
    <div class="cp-titlebar">
      <div>
        <span class="eyebrow">AI 辅助</span>
        <h3>🤖 智能分析</h3>
      </div>
      <button class="ghost sm" @click="showSettings = !showSettings">
        模型设置 {{ showSettings ? '▲' : '▼' }}
      </button>
    </div>

    <!-- ====== 模型设置 ====== -->
    <div v-if="showSettings" class="cp-settings">
      <div class="cp-presets">
        <span class="cp-presets-label">模型:</span>
        <button v-for="(prov, key) in LLM_PROVIDERS" :key="key"
          class="ghost sm" :class="{ 'cp-pill-on': selectedProvider === key }"
          @click="selectProvider(key)">{{ prov.name }}</button>
      </div>
      <div class="cp-form">
        <label><span>API 地址</span><input v-model="llmSettings.apiUrl" type="text" placeholder="https://api.deepseek.com/v1" @change="saveState" /></label>
        <label><span>API Key</span><div class="cp-key-row">
          <input id="classify-api-key" v-model="llmSettings.apiKey" type="password"
            :placeholder="currentProvider.keyPlaceholder || 'sk-xxxx'" @change="saveState" />
          <button type="button" class="ghost sm" @click="showApiKey">显示</button>
        </div></label>
        <label><span>模型名称</span><input v-model="llmSettings.model" type="text" list="classify-model-list"
          :placeholder="currentProvider.models.length ? '选模型' : '输入模型名'" @change="saveState" />
          <datalist id="classify-model-list"><option v-for="m in currentProvider.models" :key="m" :value="m" /></datalist>
        </label>
      </div>
      <div class="cp-test">
        <button class="secondary sm" @click="testConnection">测试连接</button>
        <span v-if="testStatus" class="cp-test-result" :class="{ ok: testStatus.ok, fail: !testStatus.ok }">
          {{ testStatus.ok ? '✅' : '❌' }} {{ testStatus.message }}</span>
      </div>
    </div>

    <!-- ====== 模式选项卡 ====== -->
    <div class="cp-modes">
      <button v-for="m in modes" :key="m.key"
        class="cp-mode" :class="{ active: activeMode === m.key }"
        @click="activeMode = m.key; analyzeResult = null; error = ''"
      >{{ m.icon }} {{ m.label }}</button>
    </div>
    <p class="cp-mode-desc">{{ currentMode?.desc }}</p>
    <div v-if="!transactionCount" class="cp-audit-tip">
      当前识别结果为汇总报告，没有逐笔交易。你仍可配置并测试模型连接；如需自动分类、审核或纠错，请上传原始银行流水明细。
    </div>

    <!-- ====== 操作 ====== -->
    <div class="cp-actions">
      <button class="primary" :disabled="loading || !transactionCount || !llmSettings.apiUrl || !llmSettings.model" @click="startAnalyze">
        {{ loading ? '分析中...' : `开始${currentMode?.label}` }}
      </button>
    </div>

    <p v-if="error" class="error" style="margin: 0 18px 12px;">{{ error }}</p>

    <!-- ====== 加载 ====== -->
    <div v-if="loading" class="progress-panel">
      <div class="progress-track"><span style="width:100%;animation:cp-progress 2s ease-in-out infinite"></span></div>
      <p>正在调用 {{ llmSettings.model }} 执行{{ currentMode?.label }}，请稍候……</p>
    </div>

    <!-- ====== 结果 ====== -->
    <div v-if="analyzeResult?.success" class="cp-result">
      <div class="cp-result-head">
        <span class="status completed">✅ {{ currentMode?.label }}完成</span>
        <span>已处理 {{ analyzeResult.processed }}/{{ analyzeResult.total }} 条</span>
        <span>模型: {{ analyzeResult.modelUsed }}</span>
        <span>耗时: {{ (analyzeResult.processingTimeMs / 1000).toFixed(1) }}s</span>
      </div>

      <!-- 审核模式显示风险统计 -->
      <div v-if="activeMode === 'audit' && analyzeResult.processed > 0" class="cp-audit-tip">
        ⚠️ 审核发现的风险已写入交易备注和"需复核"标记，请在交易表中查看红色高亮行。
      </div>
      <!-- 纠错/补全提示 -->
      <div v-if="(activeMode === 'correct' || activeMode === 'fill') && analyzeResult.processed > 0" class="cp-audit-tip" style="background:#e8f5e9;border-left-color:#2e7d32;">
        ✅ 已自动修正 {{ analyzeResult.processed }} 条交易，刷新交易表即可看到更新内容。
      </div>
      <!-- 分类统计 -->
      <div v-if="activeMode === 'classify' && analyzeResult.processed > 0" class="cp-audit-tip" style="background:#e3f2fd;border-left-color:#1565c0;">
        🏷 已为 {{ analyzeResult.processed }} 条交易打上分类标签，刷新交易表即可查看。
      </div>
    </div>

    <div v-if="analyzeResult && !analyzeResult.success" class="error" style="margin:14px 18px;">
      ❌ 分析失败: {{ analyzeResult.message }}
    </div>
  </div>
</template>

<style scoped>
.classify-panel {
  margin-top: 20px; border: 1px solid #dfe7ee; border-radius: 18px;
  background: white; box-shadow: 0 9px 28px rgba(31,61,88,.07); overflow: hidden;
}
.cp-titlebar {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  padding: 24px 24px 18px;
}
.cp-titlebar .eyebrow { color: #5b7188; font-size: 11px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
.cp-titlebar h3 { margin: 5px 0 0; font-size: 18px; color: #162235; font-weight: 750; }

.ghost.sm, .secondary.sm { padding: 6px 13px; font-size: 12px; border-radius: 10px; font-weight: 800; border: 0; }
.ghost.sm { color: #31516d; background: #edf3f7; }
.ghost.sm:hover { background: #dfe6ee; }
.secondary.sm { color: #34516b; background: #edf2f6; }
.secondary.sm:hover { background: #dfe6ee; }
.cp-pill-on { background: #0a6572 !important; color: white !important; }

.cp-settings { padding: 14px 24px 18px; border-top: 1px solid #e6ecf1; border-bottom: 1px solid #e6ecf1; background: #f8fafc; }
.cp-presets { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
.cp-presets-label { font-size: 12px; color: #5b7188; font-weight: 700; }
.cp-form { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
.cp-form label { display: flex; flex-direction: column; gap: 4px; }
.cp-form label > span { font-size: 12px; font-weight: 700; color: #51677d; }
.cp-form input { height: 39px; padding: 0 10px; border: 1px solid #cdd8e2; border-radius: 10px; font-size: 13px; color: #24384c; background: white; width: 100%; }
.cp-form input:focus { outline: none; border-color: #0a6572; }
.cp-key-row { display: flex; gap: 4px; }
.cp-key-row input { flex: 1; }
.cp-test { margin-top: 14px; display: flex; align-items: center; gap: 12px; }
.cp-test-result { font-size: 13px; }
.cp-test-result.ok { color: #08755b; }
.cp-test-result.fail { color: #a22b36; }

/* 模式选项卡 */
.cp-modes { display: flex; gap: 4px; padding: 16px 24px 0; }
.cp-mode { padding: 8px 16px; border: 1px solid #cdd8e2; border-bottom: none; border-radius: 10px 10px 0 0; background: #edf2f6; color: #51677d; font-size: 13px; font-weight: 700; cursor: pointer; transition: .15s; }
.cp-mode.active { background: white; color: #0a6572; border-color: #dfe7ee; }
.cp-mode:hover:not(.active) { background: #dfe6ee; }
.cp-mode-desc { padding: 8px 24px 0; color: #73869a; font-size: 12px; margin: 0; }

.cp-actions { padding: 12px 24px 16px; }

.cp-result { border-top: 1px solid #e6ecf1; }
.cp-result-head {
  display: flex; align-items: center; gap: 14px; padding: 12px 24px;
  background: #dcf6eb; flex-wrap: wrap; font-size: 12px; color: #41637e;
}
.cp-result-head .status { font-weight: 800; font-size: 11px; padding: 5px 10px; border-radius: 999px; color: white; background: #08755b; }
.cp-audit-tip { margin: 12px 24px; padding: 12px; border-left: 4px solid #db9c25; background: #fff8e8; color: #80580b; font-size: 13px; border-radius: 0 8px 8px 0; }

@keyframes cp-progress { 0%{width:20%} 50%{width:90%} 100%{width:20%} }
@media (max-width:768px) { .cp-form{grid-template-columns:1fr} .cp-modes{flex-wrap:wrap} }
</style>
