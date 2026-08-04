import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120000,
})

export const listTasks = () => api.get('/tasks').then(({ data }) => data)
export const getTask = (id) => api.get(`/tasks/${id}`).then(({ data }) => data)
export const getResult = (id) => api.get(`/tasks/${id}/result`).then(({ data }) => data)
export const updateResult = (id, result) => api.put(`/tasks/${id}/result`, result).then(({ data }) => data)
export const deleteTask = (id) => api.delete(`/tasks/${id}`)

export async function createTask(file, mode, onProgress) {
  const form = new FormData()
  form.append('file', file)
  form.append('mode', mode)
  const { data } = await api.post('/tasks', form, {
    onUploadProgress(event) {
      if (event.total) onProgress?.(Math.round((event.loaded / event.total) * 100))
    },
  })
  return data
}

export function downloadUrl(taskId, type) {
  const suffix = type === 'xlsx' ? 'review.xlsx' : `result.${type}`
  return `${api.defaults.baseURL}/tasks/${taskId}/${suffix}`
}

// ===== 关系表 API =====
export const getTransactions = (taskId) =>
  api.get(`/tasks/${taskId}/transactions`).then(({ data }) => data)
export const getAccount = (taskId) =>
  api.get(`/tasks/${taskId}/account`).then(({ data }) => data)
export const updateTransaction = (id, body) =>
  api.patch(`/transactions/${id}`, body).then(({ data }) => data)

// ===== LLM 分类 API =====
export const classifyTransactions = (taskId, body) =>
  api.post(`/tasks/${taskId}/classify`, body).then(({ data }) => data)
export const testLlmConnection = (config) =>
  api.post('/llm/test', config).then(({ data }) => data)

// ===== 关系表 API（结构化数据库表） =====
export const getTransactions = (taskId) =>
  api.get(`/tasks/${taskId}/transactions`).then(({ data }) => data)
export const getAccount = (taskId) =>
  api.get(`/tasks/${taskId}/account`).then(({ data }) => data)
export const updateTransaction = (id, body) =>
  api.patch(`/transactions/${id}`, body).then(({ data }) => data)
