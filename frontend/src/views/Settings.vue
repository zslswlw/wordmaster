<template>
  <div class="page">
    <h2>AI 模型配置</h2>
    <p class="subtitle">配置 DeepSeek 和 MiniMax API，启用 AI 增强学习功能</p>

    <!-- Provider 配置卡片 -->
    <div class="provider-cards">
      <!-- DeepSeek -->
      <div class="config-card">
        <div class="card-header">
          <h3>DeepSeek</h3>
          <span class="badge">文本推理 · 视觉理解</span>
        </div>
        <el-form :model="deepseekForm" label-position="top" size="default">
          <el-form-item label="API Key">
            <el-input v-model="deepseekForm.api_key" type="password" show-password placeholder="sk-..." />
          </el-form-item>
          <el-form-item label="Endpoint">
            <el-input v-model="deepseekForm.api_base" placeholder="https://api.deepseek.com" />
          </el-form-item>
          <el-form-item label="文本模型">
            <el-input v-model="deepseekForm.text_model" placeholder="deepseek-chat" />
          </el-form-item>
          <el-form-item label="视觉模型">
            <el-input v-model="deepseekForm.image_model" placeholder="deepseek-v4-flash" />
          </el-form-item>
        </el-form>
        <div class="card-actions">
          <el-button :loading="testingDeepseek" @click="testConnection('deepseek')">测试连接</el-button>
          <el-button type="primary" :loading="savingDeepseek" @click="saveConfig('deepseek')">保存</el-button>
        </div>
      </div>

      <!-- MiniMax -->
      <div class="config-card">
        <div class="card-header">
          <h3>MiniMax</h3>
          <span class="badge">生图 · TTS</span>
        </div>
        <el-form :model="minimaxForm" label-position="top" size="default">
          <el-form-item label="API Key">
            <el-input v-model="minimaxForm.api_key" type="password" show-password placeholder="eyJ..." />
          </el-form-item>
          <el-form-item label="Endpoint">
            <el-input v-model="minimaxForm.api_base" placeholder="https://api.minimax.chat" />
          </el-form-item>
          <el-form-item label="文本模型">
            <el-input v-model="minimaxForm.text_model" placeholder="minimax-m2.7" />
          </el-form-item>
          <el-form-item label="生图模型">
            <el-input v-model="minimaxForm.image_model" placeholder="image-01" />
          </el-form-item>
          <el-form-item label="语音模型">
            <el-input v-model="minimaxForm.speech_model" placeholder="speech-02" />
          </el-form-item>
        </el-form>
        <div class="card-actions">
          <el-button :loading="testingMinimax" @click="testConnection('minimax')">测试连接</el-button>
          <el-button type="primary" :loading="savingMinimax" @click="saveConfig('minimax')">保存</el-button>
        </div>
      </div>
    </div>

    <!-- AI 功能开关 -->
    <div class="section">
      <h3>AI 功能开关</h3>
      <div class="toggle-list">
        <div class="toggle-item">
          <div class="toggle-info">
            <span class="toggle-label">例句生成</span>
            <span class="toggle-desc">为每个单词生成三级难度例句 (L1填空/L2完整/L3高级)</span>
          </div>
          <el-switch v-model="features.example" />
        </div>
        <div class="toggle-item">
          <div class="toggle-info">
            <span class="toggle-label">视觉词卡</span>
            <span class="toggle-desc">MiniMax 生成单词意境图，强化视觉记忆 (需配置 MiniMax)</span>
          </div>
          <el-switch v-model="features.image" />
        </div>
        <div class="toggle-item">
          <div class="toggle-info">
            <span class="toggle-label">记忆锚点</span>
            <span class="toggle-desc">DeepSeek 生成中文谐音/场景联想，辅助快速编码</span>
          </div>
          <el-switch v-model="features.mnemonic" />
        </div>
        <div class="toggle-item">
          <div class="toggle-info">
            <span class="toggle-label">错题分析</span>
            <span class="toggle-desc">学习结束后 AI 分析拼写错误模式</span>
          </div>
          <el-switch v-model="features.errorAnalysis" />
        </div>
        <div class="toggle-item">
          <div class="toggle-info">
            <span class="toggle-label">微故事</span>
            <span class="toggle-desc">将当天错词编织成叙事短文，辅助语境记忆</span>
          </div>
          <el-switch v-model="features.story" />
        </div>
      </div>
    </div>

    <!-- 预处理管理 -->
    <div class="section">
      <h3>预处理管理</h3>
      <p class="section-desc">导入词库后可批量预处理单词的 AI 增强数据，学习时零延迟加载</p>
      <div v-if="banks.length === 0" class="empty">暂无词库</div>
      <div v-for="bank in banks" :key="bank.id" class="bank-row">
        <div class="bank-info">
          <span class="bank-name">{{ bank.name }}</span>
          <span class="bank-count">{{ bank.word_count }} 词</span>
        </div>
        <div class="bank-status">
          <!-- 文本增强进度 -->
          <div class="status-line">
            <span class="status-label">文本</span>
            <template v-if="enrichStatus[bank.id]?.status === 'running'">
              <el-progress :percentage="Math.round((enrichStatus[bank.id].progress / enrichStatus[bank.id].total) * 100)" :stroke-width="4" :show-text="false" style="width:80px" />
              <span class="status-text">{{ enrichStatus[bank.id].progress }}/{{ enrichStatus[bank.id].total }}</span>
            </template>
            <template v-else-if="enrichStatus[bank.id]?.enriched !== undefined">
              <el-progress :percentage="Math.round((enrichStatus[bank.id].enriched / enrichStatus[bank.id].total) * 100)" :stroke-width="4" :show-text="false" style="width:80px" />
              <span class="status-text">{{ enrichStatus[bank.id].enriched }}/{{ enrichStatus[bank.id].total }}</span>
            </template>
            <span v-else class="status-text text-muted">未开始</span>
          </div>
          <!-- 图片生成进度 -->
          <div class="status-line">
            <span class="status-label">图片</span>
            <template v-if="imageStatus[bank.id]?.status === 'running'">
              <el-progress :percentage="Math.round((imageStatus[bank.id].progress / imageStatus[bank.id].total) * 100)" :stroke-width="4" :show-text="false" style="width:80px" />
              <span class="status-text">{{ imageStatus[bank.id].progress }}/{{ imageStatus[bank.id].total }}</span>
            </template>
            <template v-else-if="imageStatus[bank.id]?.total !== undefined">
              <el-progress :percentage="Math.round(((imageStatus[bank.id].success || 0) / imageStatus[bank.id].total) * 100)" :stroke-width="4" :show-text="false" style="width:80px" />
              <span class="status-text">{{ imageStatus[bank.id].success || 0 }}/{{ imageStatus[bank.id].total }}</span>
            </template>
            <span v-else class="status-text text-muted">未生成</span>
          </div>
        </div>
        <div class="bank-actions">
          <el-button size="small" :loading="enrichLoading[bank.id]" @click="startEnrich(bank.id)">文本增强</el-button>
          <el-button size="small" :loading="imageLoading[bank.id]" :disabled="!enrichStatus[bank.id]?.enriched || enrichStatus[bank.id].enriched === 0" @click="startImageGen(bank.id)">生成图片</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { settingsAPI, aiAPI, bankAPI } from '../api'

// --- Provider 表单 ---
const deepseekForm = reactive({ provider: 'deepseek', api_key: '', api_base: 'https://api.deepseek.com', text_model: 'deepseek-chat', image_model: '', speech_model: '', is_enabled: true })
const minimaxForm = reactive({ provider: 'minimax', api_key: '', api_base: 'https://api.minimax.chat', text_model: 'minimax-m2.7', image_model: 'image-01', speech_model: 'speech-02', is_enabled: true })

const savingDeepseek = ref(false)
const savingMinimax = ref(false)
const testingDeepseek = ref(false)
const testingMinimax = ref(false)

// --- 功能开关 ---
const features = reactive({
  example: true,
  image: true,
  mnemonic: true,
  errorAnalysis: true,
  story: false,
})

// --- 预处理 ---
const banks = ref<any[]>([])
const enrichLoading = reactive<Record<number, boolean>>({})
const enrichStatus = reactive<Record<number, any>>({})

onMounted(async () => {
  try {
    const { data } = await settingsAPI.getConfigs()
    for (const c of data) {
      const form = c.provider === 'deepseek' ? deepseekForm : minimaxForm
      form.api_key = localStorage.getItem(`api_key_${c.provider}`) || ''
      form.api_base = c.api_base
      form.text_model = c.text_model
      form.image_model = c.image_model
      form.speech_model = c.speech_model
    }
  } catch { /* ignore */ }

  try {
    const { data } = await bankAPI.getAll()
    banks.value = data
    for (const bank of data) {
      try {
        const s = await aiAPI.enrichBankStatus(bank.id)
        enrichStatus[bank.id] = s.data
      } catch { /* ignore */ }
      try {
        const s = await aiAPI.enrichBankStatus(bank.id)
        imageStatus[bank.id] = { total: s.data.enriched || 0, success: 0, status: 'unknown' }
      } catch { /* ignore */ }
    }
  } catch { /* ignore */ }
})

// --- 保存配置 ---
const saveConfig = async (provider: string) => {
  const form = provider === 'deepseek' ? deepseekForm : minimaxForm
  const saving = provider === 'deepseek' ? savingDeepseek : savingMinimax
  saving.value = true
  try {
    await settingsAPI.saveConfig({ ...form })
    localStorage.setItem(`api_key_${provider}`, form.api_key)
    ElMessage.success(`${provider} 配置已保存`)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// --- 测试连接 ---
const testConnection = async (provider: string) => {
  const form = provider === 'deepseek' ? deepseekForm : minimaxForm
  const testing = provider === 'deepseek' ? testingDeepseek : testingMinimax
  if (!form.api_key) { ElMessage.warning('请先填写 API Key'); return }
  testing.value = true
  try {
    const { data } = await settingsAPI.testConnection({ ...form })
    ElMessage[data.success ? 'success' : 'error'](data.message)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '测试失败')
  } finally {
    testing.value = false
  }
}

// --- 预处理 ---
const startEnrich = async (bankId: number) => {
  enrichLoading[bankId] = true
  try {
    const { data } = await aiAPI.enrichBank(bankId)
    if (data.task_id) {
      enrichStatus[bankId] = { progress: 0, total: data.total, status: 'running' }
      pollTaskStatus(bankId, data.task_id, 'enrich')
    } else {
      ElMessage.success(data.message || '预处理完成')
      loadEnrichStatus(bankId)
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '预处理失败')
  } finally {
    enrichLoading[bankId] = false
  }
}

const imageLoading = reactive<Record<number, boolean>>({})
const imageStatus = reactive<Record<number, any>>({})

const startImageGen = async (bankId: number) => {
  imageLoading[bankId] = true
  try {
    const { data } = await aiAPI.generateBankImages(bankId)
    if (data.task_id) {
      imageStatus[bankId] = { progress: 0, total: data.total, status: 'running' }
      pollTaskStatus(bankId, data.task_id, 'image')
    } else {
      ElMessage.success(data.message || '图片生成完成')
      loadImageStatus(bankId)
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '图片生成失败')
  } finally {
    imageLoading[bankId] = false
  }
}

const pollTaskStatus = (bankId: number, taskId: string, type: 'enrich' | 'image') => {
  const target = type === 'enrich' ? enrichStatus : imageStatus
  const label = type === 'enrich' ? '文本增强' : '图片生成'
  const timer = setInterval(async () => {
    try {
      const { data } = await aiAPI.enrichStatus(taskId)
      if (data.status === 'done') {
        target[bankId] = data
        ElMessage.success(`${label}完成: ${data.success}/${data.total} 成功`)
        clearInterval(timer)
      } else if (data.status === 'error') {
        ElMessage.error(`${label}出错: ` + (data.error || '未知错误'))
        clearInterval(timer)
      } else {
        target[bankId] = data
      }
    } catch {
      clearInterval(timer)
    }
  }, 2000)
}

const loadEnrichStatus = async (bankId: number) => {
  try {
    const { data } = await aiAPI.enrichBankStatus(bankId)
    enrichStatus[bankId] = data
  } catch { /* ignore */ }
}

const loadImageStatus = async (bankId: number) => {
  try {
    const { data } = await aiAPI.enrichBankStatus(bankId)
    imageStatus[bankId] = { total: data.enriched || 0, success: 0, status: 'unknown' }
  } catch { /* ignore */ }
}
</script>

<style scoped lang="scss">
.page {
  max-width: 720px;
  margin: 0 auto;
  h2 { font-size: 1.125rem; font-weight: 700; color: var(--color-text-primary); margin: 0 0 4px; }
}
.subtitle { font-size: 0.8125rem; color: var(--color-text-muted); margin: 0 0 28px; }

// provider cards
.provider-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 36px;
}

.config-card {
  background: var(--color-bg-paper);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 20px;
}

.card-header {
  display: flex; align-items: center; gap: 10px; margin-bottom: 16px;
  h3 { font-size: 0.9375rem; font-weight: 600; color: var(--color-text-primary); margin: 0; }
  .badge { font-size: 0.6875rem; color: var(--color-text-muted); background: var(--color-bg-muted); padding: 2px 8px; border-radius: 4px; }
}

.card-actions {
  display: flex; gap: 8px; margin-top: 4px;
}

// feature toggles
.section {
  margin-bottom: 36px;
  h3 { font-size: 0.9375rem; font-weight: 600; color: var(--color-text-primary); margin: 0 0 4px; }
}
.section-desc { font-size: 0.8125rem; color: var(--color-text-muted); margin: 0 0 16px; }

.toggle-list {
  background: var(--color-bg-paper);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}
.toggle-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px;
  & + & { border-top: 1px solid var(--color-border-light); }
}
.toggle-label { font-size: 0.875rem; font-weight: 500; color: var(--color-text-primary); display: block; }
.toggle-desc { font-size: 0.75rem; color: var(--color-text-muted); display: block; margin-top: 2px; max-width: 420px; }

// bank rows
.empty { font-size: 0.8125rem; color: var(--color-text-muted); padding: 24px 0; text-align: center; }
.bank-row {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px;
  background: var(--color-bg-paper);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  & + & { margin-top: 8px; }
}
.bank-info { flex: 0 0 140px; min-width: 0; }
.bank-name { font-size: 0.875rem; font-weight: 500; color: var(--color-text-primary); display: block; }
.bank-count { font-size: 0.6875rem; color: var(--color-text-muted); }
.bank-status { flex: 1; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.status-line { display: flex; align-items: center; gap: 6px; }
.status-label { font-size: 0.6875rem; color: var(--color-text-muted); width: 28px; flex-shrink: 0; }
.status-text { font-size: 0.6875rem; color: var(--color-text-secondary); white-space: nowrap; }
.text-muted { color: var(--color-text-muted); }
.bank-actions { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }

:deep(.el-form-item) { margin-bottom: 12px; }
:deep(.el-form-item__label) { font-size: 0.75rem; color: var(--color-text-muted); padding-bottom: 2px; }

@media (max-width: 640px) {
  .provider-cards { grid-template-columns: 1fr; }
  .toggle-desc { max-width: 220px; }
}
</style>
