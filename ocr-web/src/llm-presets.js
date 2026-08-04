/** 主流大模型预设配置 */
export const LLM_PROVIDERS = {
  openai: {
    name: 'OpenAI',
    apiUrl: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o3-mini'],
    requiresKey: true,
  },
  claude: {
    name: 'Claude (Anthropic)',
    apiUrl: 'https://api.anthropic.com/v1',
    models: ['claude-sonnet-5', 'claude-fable-5', 'claude-opus-5', 'claude-haiku-4-5'],
    requiresKey: true,
  },
  ollama: {
    name: 'Ollama (本地)',
    apiUrl: 'http://localhost:11434/v1',
    models: [],
    requiresKey: false,
    keyPlaceholder: 'ollama（可留空）',
  },
  deepseek: {
    name: 'DeepSeek',
    apiUrl: 'https://api.deepseek.com/v1',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    requiresKey: true,
  },
  qwen: {
    name: '通义千问',
    apiUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-plus', 'qwen-max', 'qwen-turbo'],
    requiresKey: true,
  },
  custom: {
    name: '自定义',
    apiUrl: '',
    models: [],
    requiresKey: true,
  },
}

export function loadLlmSettings() {
  try {
    const raw = localStorage.getItem('ocr_llm_settings')
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return { apiUrl: '', apiKey: '', model: '', provider: 'custom' }
}

export function saveLlmSettings(settings) {
  localStorage.setItem('ocr_llm_settings', JSON.stringify(settings))
}
