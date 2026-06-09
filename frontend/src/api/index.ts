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
  delete: (id: number) => api.delete(`/banks/${id}`)
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

export const backupAPI = {
  export: () => api.post('/backup/export'),
  exportData: () => api.post('/backup/export'),
  import: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/backup/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

export const settingsAPI = {
  getConfigs: () => api.get('/settings/ai-configs'),
  saveConfig: (data: any) => api.post('/settings/ai-configs', data),
  updateConfig: (id: number, data: any) => api.put(`/settings/ai-configs/${id}`, data),
  deleteConfig: (id: number) => api.delete(`/settings/ai-configs/${id}`),
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
}