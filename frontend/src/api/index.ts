import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
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
    console.log('API 响应:', response.config.url, response.status)
    return response
  },
  (error) => {
    console.log('API 错误:', error.config?.url, error.response?.status, error.message)
    if (error.response?.status === 401) {
      // 只在不是登录请求时才跳转
      const isLoginRequest = error.config?.url?.includes('/auth/login')
      console.log('401 错误, 是否登录请求:', isLoginRequest)
      if (!isLoginRequest) {
        localStorage.removeItem('token')
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
  create: (data: { name: string; bank_id: number; start_seq: number; end_seq: number }) => api.post('/groups', data),
  update: (id: number, data: { name: string }) => api.put(`/groups/${id}`, data),
  delete: (id: number) => api.delete(`/groups/${id}`)
}

export const studyAPI = {
  startStudy: (groupId: number, isReview: boolean = false, isEnhance: boolean = false) => 
    api.post(`/study/start/${groupId}?is_review=${isReview}&is_enhance=${isEnhance}`),
  getWord: (wordId: number) => api.get(`/study/word/${wordId}`),
  checkAnswer: (data: { group_id: number; word_id: number; user_input: string; round: number; study_type: string; plan_id?: number }) => api.post('/study/check', data),
  getRoundStats: (groupId: number, currentRound?: number, studyType?: string) => 
    api.get(`/study/round/${groupId}?study_type=${studyType || 'new'}${currentRound ? `&current_round=${currentRound}` : ''}`),
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