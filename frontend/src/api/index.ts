import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      // 只在不是登录请求时才跳转
      const isLoginRequest = error.config?.url?.includes('/auth/login')
      if (!isLoginRequest) {
        localStorage.removeItem('token')
        localStorage.removeItem('role')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export const authAPI = {
  login: (credentials: { username: string; password: string }) => api.post('/auth/login', credentials),
  register: (credentials: { username: string; password: string }) => api.post('/auth/register', credentials),
  me: () => api.get('/auth/me')
}

export const systemAPI = {
  health: () => api.get('/health')
}

export const bankAPI = {
  getAll: () => api.get('/banks'),
  upload: (file: File, name: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name)
    return api.post('/banks', formData, {
      headers: { 
        'Content-Type': 'multipart/form-data',
        'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
      }
    })
  },
  delete: (id: number, expectedRevision: number) => api.delete(`/banks/${id}`, { params: { expected_revision: expectedRevision } })
}

export const groupAPI = {
  getAll: () => api.get('/groups'),
  getById: (id: number) => api.get(`/groups/${id}`),
  getReviewProgress: (id: number) => api.get(`/groups/${id}/review-progress`),
  create: (data: { bank_id: number; start_seq: number; end_seq: number }) => api.post('/groups', data),
  update: (id: number, data: { name: string }) => api.put(`/groups/${id}`, data),
  delete: (id: number) => api.delete(`/groups/${id}`)
}

export const studyAPI = {
  startStudy: (groupId: number, isReview: boolean = false, isEnhance: boolean = false, planId?: number) => {
    let url = `/study/start/${groupId}?is_review=${isReview}&is_enhance=${isEnhance}`
    if (planId) url += `&plan_id=${planId}`
    return api.post(url)
  },
  getWord: (wordId: number) => api.get(`/study/word/${wordId}`),
  checkAnswer: (data: { group_id: number; word_id: number; user_input: string; round: number; study_type: string; plan_id?: number }) => api.post('/study/check', data),
  getRoundStats: (groupId: number, currentRound?: number, studyType?: string, planId?: number) => {
    let url = `/study/round/${groupId}?study_type=${studyType || 'new'}`
    if (currentRound) url += `&current_round=${currentRound}`
    if (planId) url += `&plan_id=${planId}`
    return api.get(url)
  },
  getEnhanceStats: (groupId: number, currentRound?: number) => 
    api.get(`/study/round/${groupId}?study_type=enhance${currentRound ? `&current_round=${currentRound}` : ''}`),
  completeStudy: (groupId: number, isEnhance: boolean, studyType: string, planId?: number) => {
    const params = new URLSearchParams({ 
      is_enhance: String(isEnhance), 
      study_type: studyType 
    })
    if (planId) params.append('plan_id', String(planId))
    return api.post(`/study/complete/${groupId}?${params.toString()}`)
  }
}

export const reviewAPI = {
  getToday: () => api.get('/review/today'),
  getTodayPlans: () => api.get('/review/today'),
  getAllPlans: () => api.get('/review/all'),
  getGroupPlans: (groupId: number) => api.get(`/review/group/${groupId}`),
  startReview: (planId: number) => api.post(`/review/start/${planId}`),
  completeReview: (planId: number) => api.post(`/review/complete/${planId}`)
}

export const testAPI = {
  getClock: () => api.get('/test/clock'),
  setClock: (now: string) => api.put('/test/clock', { now }),
  advanceClock: (days: number = 0, minutes: number = 0) =>
    api.post('/test/clock/advance', { days, minutes }),
  resetClock: () => api.delete('/test/clock'),
  loadScenario: (scenario: 'fresh' | 'partial-round' | 'completed-day0' | 'overdue-backlog' | 'ten-word-review') =>
    api.post(`/test/scenarios/${scenario}`)
}

export const backupAPI = {
  export: () => api.post('/backup/export'),
  exportData: () => api.post('/backup/export'),
  exportFull: () => api.post('/backup/export-full', undefined, { responseType: 'blob' }),
  import: (data: any) => api.post('/backup/import', data),
  importFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/backup/import', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
}

export const settingsAPI = {
  getConfigs: () => api.get('/settings/ai-configs'),
  saveConfig: (data: any) => api.post('/settings/ai-configs', data),
  updateConfig: (id: number, data: any) => api.put(`/settings/ai-configs/${id}`, data),
  deleteConfig: (id: number, expectedRevision: number) => api.delete(`/settings/ai-configs/${id}`, { params: { expected_revision: expectedRevision } }),
  testConnection: (data: any) => api.post('/settings/ai-configs/test', data),
  getFeatureFlags: () => api.get('/settings/feature-flags'),
  updateFeatureFlags: (data: any) => api.put('/settings/feature-flags', data),
}

export const aiAPI = {
  enrichBank: (bankId: number) => api.post(`/ai/enrich-bank/${bankId}`),
  enrichBankStatus: (bankId: number) => api.get(`/ai/enrich-bank/${bankId}/status`),
  enrichStatus: (taskId: string) => api.get(`/ai/enrich-status/${taskId}`),
  generateBankImages: (bankId: number) => api.post(`/ai/generate-bank-images/${bankId}`),
  generateContextAudio: (bankId: number) => api.post(`/ai/generate-context-audio/${bankId}`),
  bankPipelineStatus: (bankId: number) => api.get(`/ai/bank-pipeline/${bankId}`),
  reprocessBank: (bankId: number) => api.post(`/ai/reprocess-bank/${bankId}`),
  enrichWord: (wordId: number) => api.post(`/ai/enrich-word/${wordId}`),
  generateImage: (wordId: number) => api.post(`/ai/generate-image/${wordId}`),
  analyzeErrors: (errors: Array<{ word: string; correct: string; user: string; meaning?: string }>) => api.post('/ai/analyze-errors', { errors }),
  generateStory: (words: string[]) => api.post('/ai/story', { words }),
  distinguish: (word1: string, word2: string, meaning1?: string, meaning2?: string) => api.post('/ai/distinguish', { word1, meaning1: meaning1 || '', word2, meaning2: meaning2 || '' }),
  submitFeedback: (data: { word_id: number; bundle_id?: number; component: string; reason: string; detail?: string }) =>
    api.post('/ai/evolution/feedback', data),
  feedback: (status?: string) => api.get('/ai/evolution/feedback', { params: { status } }),
  wordVersions: (wordId: number) => api.get(`/ai/evolution/words/${wordId}/versions`),
  recordExposure: (data: { word_id: number; bundle_id?: number; group_id?: number; plan_id?: number; study_type?: string }) =>
    api.post('/ai/evolution/exposures', data),
  bankCoverage: (bankId: number) => api.get(`/ai/evolution/banks/${bankId}/coverage`),
  seedBank: (bankId: number) => api.post(`/ai/evolution/banks/${bankId}/seed`),
  dashboard: () => api.get('/ai/evolution/dashboard'),
  quota: () => api.get('/ai/evolution/quota'),
  jobs: (status?: string) => api.get('/ai/evolution/jobs', { params: { status } }),
  worker: () => api.get('/ai/evolution/worker'),
  updateWorker: (data: any) => api.patch('/ai/evolution/worker', data),
  retryFailedJobs: () => api.post('/ai/evolution/jobs/retry-failed'),
  regenerateWord: (wordId: number) => api.post(`/ai/evolution/words/${wordId}/regenerate`),
  editBundle: (bundleId: number, data: any) => api.put(`/ai/evolution/bundles/${bundleId}`, data),
  activateBundle: (wordId: number, bundleId: number, expectedActiveBundleId: number | null) =>
    api.post(`/ai/evolution/words/${wordId}/activate/${bundleId}`, { expected_active_bundle_id: expectedActiveBundleId }),
  rollbackBundle: (wordId: number, bundleId: number, expectedActiveBundleId: number | null) =>
    api.post(`/ai/evolution/words/${wordId}/rollback/${bundleId}`, { expected_active_bundle_id: expectedActiveBundleId }),
}

export const adminAPI = {
  users: () => api.get('/admin/users'),
  updateRole: (userId: number, role: 'admin' | 'user') => api.patch(`/admin/users/${userId}/role`, { role }),
  auditLogs: (params?: { limit?: number; before_id?: number; action?: string }) => api.get('/admin/audit-logs', { params }),
}
