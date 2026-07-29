<template>
  <div class="page">
    <h2>AI 模型配置</h2>
    <p class="subtitle">MiniMax 负责文字、图像和中文播报，DeepSeek 仅在文字服务不可用时备用</p>

    <!-- Provider 配置卡片 -->
    <div class="provider-cards">
      <!-- DeepSeek -->
      <div class="config-card">
        <div class="card-header">
          <h3>DeepSeek</h3>
          <span class="badge">备用文字</span>
        </div>
        <el-form :model="deepseekForm" label-position="top" size="default">
          <el-form-item label="API Key">
            <el-input v-model="deepseekForm.api_key" type="password" show-password :placeholder="savedKeys.deepseek ? '已保存，留空表示不修改' : 'sk-...'" />
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
          <span class="badge">文字 · 生图 · 播报</span>
        </div>
        <el-form :model="minimaxForm" label-position="top" size="default">
          <el-form-item label="API Key">
            <el-input v-model="minimaxForm.api_key" type="password" show-password :placeholder="savedKeys.minimax ? '已保存，留空表示不修改' : 'eyJ...'" />
          </el-form-item>
          <el-form-item label="Endpoint">
            <el-input v-model="minimaxForm.api_base" placeholder="https://api.minimaxi.com" />
          </el-form-item>
          <el-form-item label="文本模型">
            <el-input v-model="minimaxForm.text_model" placeholder="MiniMax-M3" />
          </el-form-item>
          <el-form-item label="生图模型">
            <el-input v-model="minimaxForm.image_model" placeholder="image-01" />
          </el-form-item>
          <el-form-item label="语音模型">
            <el-input v-model="minimaxForm.speech_model" placeholder="speech-2.8-turbo" />
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
          <el-switch v-model="flags.example_enabled" @change="saveFlags" />
        </div>
        <div class="toggle-item">
          <div class="toggle-info">
            <span class="toggle-label">视觉词卡</span>
            <span class="toggle-desc">MiniMax 生成单词意境图，强化视觉记忆</span>
          </div>
          <el-switch v-model="flags.image_enabled" @change="saveFlags" />
        </div>
        <div class="toggle-item">
          <div class="toggle-info">
            <span class="toggle-label">记忆锚点</span>
            <span class="toggle-desc">优先使用直接语义或自然场景，不强行编造谐音和词源</span>
          </div>
          <el-switch v-model="flags.mnemonic_enabled" @change="saveFlags" />
        </div>
        <div class="toggle-item">
          <div class="toggle-info">
            <span class="toggle-label">错题分析</span>
            <span class="toggle-desc">学习结束后 AI 分析拼写错误模式</span>
          </div>
          <el-switch v-model="flags.error_analysis_enabled" @change="saveFlags" />
        </div>
        <div class="toggle-item">
          <div class="toggle-info">
            <span class="toggle-label">微故事</span>
            <span class="toggle-desc">将当天错词编织成叙事短文，辅助语境记忆</span>
          </div>
          <el-switch v-model="flags.story_enabled" @change="saveFlags" />
        </div>
      </div>
    </div>

    <div class="section">
      <h3>静默资源调度</h3>
      <p class="section-desc">学习不等待生成任务；额度达到保留线后后台会自动暂停普通补全。</p>
      <div class="worker-panel">
        <div class="worker-stat">
          <span>运行状态</span>
          <strong>{{ workerStateText() }}</strong>
        </div>
        <div class="worker-stat">
          <span>MiniMax 剩余</span>
          <strong>{{ quotaText() }}</strong>
        </div>
        <div class="worker-stat">
          <span>当前请求 / 后台步骤</span>
          <strong>{{ jobCountsText() }}</strong>
        </div>
        <div class="worker-stat">
          <span>当前任务</span>
          <strong>{{ currentJobText() }}</strong>
        </div>
        <el-button :type="worker.paused ? 'primary' : 'default'" :disabled="!dashboardLoaded" @click="toggleWorker">
          {{ worker.paused ? '恢复' : '暂停' }}
        </el-button>
      </div>
      <div class="worker-meta">
        <span>{{ dashboardError || `状态时间：${snapshotText()}` }}</span>
        <span>最近任务：{{ lastActivityText() }}</span>
        <span v-if="jobs.failed">失败待检查：{{ jobs.failed }}</span>
      </div>
      <div class="reserve-row">
        <span>普通任务保留额度</span>
        <el-input-number v-model="worker.quota_reserve_percent" :min="0" :max="95" :step="5" @change="saveWorker" />
        <span>反馈任务保留额度</span>
        <el-input-number v-model="worker.feedback_reserve_percent" :min="0" :max="95" :step="5" @change="saveWorker" />
      </div>
    </div>

    <div class="section">
      <div class="preprocess-header">
        <div>
          <h3>词库进化进度</h3>
          <p class="section-desc">图文就绪包含记忆点与图片，完整就绪再包含中文播报。</p>
        </div>
      </div>
      <div v-if="!dashboardLoaded" class="empty">{{ dashboardError || '正在加载后台状态' }}</div>
      <div v-else-if="banks.length === 0" class="empty">暂无词库</div>
      <div v-for="bank in banks" :key="bank.id" class="bank-row">
        <div class="bank-info">
          <span class="bank-name">{{ bank.name }}</span>
          <span class="bank-count">{{ bank.word_count }} 词</span>
        </div>
        <div class="bank-status">
          <div class="status-line">
            <span class="status-label">文字</span>
            <el-progress :percentage="coverage[bank.id]?.text_ready_percent || 0" :stroke-width="4" :show-text="false" style="width:100px" />
            <span class="status-text">{{ coverage[bank.id]?.text_ready || 0 }}/{{ coverage[bank.id]?.total || bank.word_count }}</span>
          </div>
          <div class="status-line">
            <span class="status-label">图文</span>
            <el-progress :percentage="coverage[bank.id]?.visual_ready_percent || 0" :stroke-width="4" :show-text="false" style="width:100px" />
            <span class="status-text">{{ coverage[bank.id]?.visual_ready || 0 }}/{{ coverage[bank.id]?.total || bank.word_count }}</span>
          </div>
          <div class="status-line">
            <span class="status-label">完整</span>
            <el-progress :percentage="coverage[bank.id]?.complete_ready_percent || 0" :stroke-width="4" :show-text="false" style="width:100px" />
            <span class="status-text">{{ coverage[bank.id]?.complete_ready || 0 }}/{{ coverage[bank.id]?.total || bank.word_count }}</span>
          </div>
        </div>
        <el-button
          v-if="isAdmin"
          size="small"
          text
          :loading="reprocessingBank[bank.id] || bankIsProcessing(bank.id)"
          :disabled="!dashboardLoaded || bankIsProcessing(bank.id)"
          @click="reprocessBank(bank.id)"
        >
          {{ bankActionText(bank.id) }}
        </el-button>
      </div>
    </div>

    <div class="section">
      <h3>素材反馈</h3>
      <p class="section-desc">待更新和人工检查的素材会保留当前版本，直到替代版确认启用。</p>
      <div v-if="feedbackItems.length === 0" class="empty">暂无待处理反馈</div>
      <div v-for="item in feedbackItems" :key="item.id" class="feedback-row">
        <div class="feedback-copy">
          <strong>{{ item.word }}</strong>
          <span>{{ item.component === 'image' ? '图片' : '记忆点' }} · {{ item.reason }}</span>
          <small v-if="item.detail">{{ item.detail }}</small>
        </div>
        <el-tag size="small" :type="item.status === 'manual_review' ? 'warning' : 'info'">
          {{ item.status === 'manual_review' ? '人工检查' : item.status === 'generating' ? '生成中' : '待更新' }}
        </el-tag>
        <el-button size="small" @click="openVersions(item)">查看版本</el-button>
      </div>
    </div>

    <el-dialog v-model="showVersions" :title="selectedFeedback ? `${selectedFeedback.word} · 记忆版本` : '记忆版本'" :width="isMobile ? '94%' : '720px'">
      <div v-loading="versionsLoading" class="version-list">
        <div v-for="version in versions" :key="version.id" class="version-row">
          <div class="version-media">
            <img v-if="versionImage(version)" :src="versionImage(version)" :alt="selectedFeedback?.word || ''" />
            <div v-else class="version-placeholder">图片生成中</div>
          </div>
          <div class="version-copy">
            <div class="version-title">
              <strong>版本 {{ version.version }}</strong>
              <el-tag v-if="version.id === activeBundleId" size="small" type="success">当前启用</el-tag>
              <el-tag v-else size="small">{{ version.status }}</el-tag>
            </div>
            <p>{{ version.memory_anchor || '暂无记忆点' }}</p>
            <small>{{ version.narration_text }}</small>
            <div class="version-actions">
              <el-button size="small" @click="beginEdit(version)">编辑为新版本</el-button>
              <el-button v-if="version.id !== activeBundleId" size="small" type="primary" :disabled="!versionReady(version)" @click="activateVersion(version.id)">
                {{ version.status === 'archived' ? '回滚到此版本' : '启用' }}
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <el-form v-if="editingBundleId" label-position="top" class="version-editor">
        <el-form-item label="中文记忆点">
          <el-input v-model="bundleEdit.memory_anchor" maxlength="45" show-word-limit />
        </el-form-item>
        <el-form-item label="图片提示词">
          <el-input v-model="bundleEdit.image_prompt" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="中文播报脚本">
          <el-input v-model="bundleEdit.narration_text" maxlength="64" show-word-limit />
        </el-form-item>
        <div class="editor-actions">
          <el-button @click="editingBundleId = null">取消</el-button>
          <el-button type="primary" :loading="savingBundle" @click="saveBundleEdit">生成草稿</el-button>
        </div>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { settingsAPI, aiAPI } from '../api'
import { useAuth } from '../composables/useAuth'

// --- Provider 表单 ---
const deepseekForm = reactive({ provider: 'deepseek', api_key: '', api_base: 'https://api.deepseek.com', text_model: 'deepseek-chat', image_model: '', speech_model: '', is_enabled: true })
const minimaxForm = reactive({ provider: 'minimax', api_key: '', api_base: 'https://api.minimaxi.com', text_model: 'MiniMax-M3', image_model: 'image-01', speech_model: 'speech-2.8-turbo', is_enabled: true })
const savedKeys = reactive({ deepseek: false, minimax: false })

const savingDeepseek = ref(false)
const savingMinimax = ref(false)
const testingDeepseek = ref(false)
const testingMinimax = ref(false)

// --- 功能开关 ---
const flags = reactive({
  example_enabled: true,
  image_enabled: true,
  mnemonic_enabled: true,
  error_analysis_enabled: true,
  story_enabled: false,
})

const saveFlags = async () => {
  try {
    await settingsAPI.updateFeatureFlags({ ...flags })
  } catch { /* ignore */ }
}

// --- 预处理 ---
const banks = ref<any[]>([])
const coverage = reactive<Record<number, any>>({})
const reprocessingBank = reactive<Record<number, boolean>>({})
const quota = reactive<{ remaining_percent: number | null; status: string }>({ remaining_percent: null, status: 'unknown' })
const jobs = reactive<Record<string, number>>({})
const worker = reactive({
  paused: false,
  state: 'loading',
  quota_reserve_percent: 30,
  feedback_reserve_percent: 20,
  priority_bank_id: null as number | null,
  queue: null as any,
  runtime: null as any,
})
const dashboardLoaded = ref(false)
const dashboardError = ref('')
const observedAt = ref<string | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null
let pollInFlight = false
let viewActive = false
let mounted = false

const jobKindText: Record<string, string> = {
  bundle_text: '整理记忆方案',
  bundle_refresh: '升级记忆方案',
  feedback_bundle: '处理用户反馈',
  image: '生成图片',
  audio: '生成播报',
}

const workerStateText = () => {
  if (!dashboardLoaded.value) return '加载中'
  if (worker.paused) return '已暂停'
  if (worker.state === 'running') return '正在生成'
  if (worker.state === 'queued') return '等待调度'
  if (worker.state === 'waiting_quota') return '等待额度'
  if (worker.state === 'waiting_rate_limit') return '限流退避'
  if (worker.state === 'stalled') return '执行器失联'
  if (worker.state === 'attention') return '需要检查'
  return '空闲'
}

const quotaText = () => {
  if (!dashboardLoaded.value) return '加载中'
  return quota.remaining_percent == null ? '无法解析' : `${quota.remaining_percent}%`
}

const jobCountsText = () => {
  if (!dashboardLoaded.value) return '- / -'
  return `${jobs.running || 0} / ${jobs.pending || 0}`
}

const currentJobText = () => {
  if (!dashboardLoaded.value) return '加载中'
  const current = worker.queue?.current_job
  if (current) return jobKindText[current.kind] || current.kind
  const next = worker.queue?.next_job
  if (next) return `等待：${jobKindText[next.kind] || next.kind}`
  return '无'
}

const snapshotText = () => {
  if (!observedAt.value) return '暂无'
  const parsed = new Date(observedAt.value)
  return Number.isNaN(parsed.getTime()) ? '暂无' : parsed.toLocaleString('zh-CN')
}

const lastActivityText = () => {
  const value = worker.queue?.last_activity_at
  if (!value) return '暂无'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '暂无' : parsed.toLocaleString('zh-CN')
}

const bankIsProcessing = (bankId: number) =>
  Number(coverage[bankId]?.queue?.active_jobs || 0) > 0

const bankActionText = (bankId: number) => {
  const queue = coverage[bankId]?.queue
  if (queue?.active_jobs && worker.state === 'waiting_quota') return '等待额度'
  if (queue?.active_jobs && worker.state === 'waiting_rate_limit') return '限流等待'
  if (queue?.active_jobs && worker.state === 'stalled') return '执行器失联'
  if (queue?.state === 'running') return `处理中 (${queue.active_jobs})`
  if (queue?.state === 'queued') return `排队中 (${queue.active_jobs})`
  if (queue?.state === 'attention') return '重试'
  return '补全'
}

const loadFeedback = async () => {
  try {
    const { data } = await aiAPI.feedback()
    feedbackItems.value = (data || []).filter(
      (item: any) => ['pending', 'generating', 'manual_review'].includes(item.status),
    )
  } catch { /* dashboard remains usable when feedback loading fails */ }
}

const scheduleDashboardPoll = () => {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
  if (!viewActive) return
  const activeStates = new Set([
    'running',
    'queued',
    'waiting_quota',
    'waiting_rate_limit',
    'stalled',
  ])
  const delay = activeStates.has(worker.state) ? 5000 : 15000
  pollTimer = setTimeout(loadDashboard, delay)
}

const loadDashboard = async () => {
  if (pollInFlight) return
  pollInFlight = true
  try {
    const { data } = await aiAPI.dashboard()
    banks.value = data.banks || []
    for (const bank of banks.value) coverage[bank.id] = bank
    Object.assign(quota, data.quota || {})
    Object.keys(jobs).forEach(key => delete jobs[key])
    Object.assign(jobs, data.jobs || {})
    Object.assign(worker, data.worker || {})
    observedAt.value = data.observed_at || null
    dashboardLoaded.value = true
    dashboardError.value = ''
    void loadFeedback()
    if (showVersions.value) await loadVersions()
  } catch (e: any) {
    dashboardError.value = e.response?.data?.detail || '后台状态更新失败，继续显示上次数据'
  } finally {
    pollInFlight = false
    scheduleDashboardPoll()
  }
}

const reprocessBank = async (bankId: number) => {
  reprocessingBank[bankId] = true
  try {
    await aiAPI.seedBank(bankId)
    ElMessage.success('缺失资源已加入后台队列')
    await loadDashboard()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '启动失败')
  } finally {
    reprocessingBank[bankId] = false
  }
}

const saveWorker = async () => {
  try {
    const { data } = await aiAPI.updateWorker({
      quota_reserve_percent: worker.quota_reserve_percent,
      feedback_reserve_percent: worker.feedback_reserve_percent,
      priority_bank_id: worker.priority_bank_id,
    })
    Object.assign(worker, data)
    await loadDashboard()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '调度设置保存失败')
  }
}

const toggleWorker = async () => {
  try {
    const { data } = await aiAPI.updateWorker({ paused: !worker.paused })
    Object.assign(worker, data)
    await loadDashboard()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '状态更新失败')
  }
}

const router = useRouter()
const { isAdmin } = useAuth()
const isMobile = ref(window.innerWidth <= 640)
const feedbackItems = ref<any[]>([])
const showVersions = ref(false)
const selectedFeedback = ref<any | null>(null)
const versions = ref<any[]>([])
const activeBundleId = ref<number | null>(null)
const versionsLoading = ref(false)
const editingBundleId = ref<number | null>(null)
const savingBundle = ref(false)
const bundleEdit = reactive({ memory_anchor: '', image_prompt: '', narration_text: '' })

const loadVersions = async () => {
  if (!selectedFeedback.value) return
  versionsLoading.value = true
  try {
    const { data } = await aiAPI.wordVersions(selectedFeedback.value.word_id)
    versions.value = data.items || []
    activeBundleId.value = data.active_bundle_id
  } catch {
    ElMessage.error('版本加载失败')
  } finally {
    versionsLoading.value = false
  }
}

const openVersions = async (item: any) => {
  selectedFeedback.value = item
  editingBundleId.value = null
  showVersions.value = true
  await loadVersions()
}

const versionImage = (version: any) =>
  version.assets?.find((asset: any) => asset.type === 'image' && asset.status === 'ready')?.url || ''

const versionReady = (version: any) => {
  const ready = new Set(
    (version.assets || [])
      .filter((asset: any) => asset.status === 'ready')
      .map((asset: any) => asset.type),
  )
  return ready.has('image') && ready.has('audio')
}

const beginEdit = (version: any) => {
  editingBundleId.value = version.id
  bundleEdit.memory_anchor = version.memory_anchor || ''
  bundleEdit.image_prompt = version.image_prompt || ''
  bundleEdit.narration_text = version.narration_text || ''
}

const saveBundleEdit = async () => {
  if (!editingBundleId.value) return
  savingBundle.value = true
  try {
    await aiAPI.editBundle(editingBundleId.value, { ...bundleEdit })
    editingBundleId.value = null
    ElMessage.success('草稿已创建，变更素材会在后台生成')
    await loadVersions()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '草稿创建失败')
  } finally {
    savingBundle.value = false
  }
}

const activateVersion = async (bundleId: number) => {
  if (!selectedFeedback.value) return
  try {
    await aiAPI.activateBundle(selectedFeedback.value.word_id, bundleId)
    ElMessage.success('版本已启用')
    await Promise.all([loadVersions(), loadDashboard()])
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '版本尚未就绪')
  }
}

onMounted(async () => {
  if (!isAdmin.value) { router.replace('/dashboard'); return }
  try {
    const { data } = await settingsAPI.getFeatureFlags()
    Object.assign(flags, data)
  } catch { /* ignore */ }
  try {
    const { data } = await settingsAPI.getConfigs()
    for (const c of data) {
      const form = c.provider === 'deepseek' ? deepseekForm : minimaxForm
      savedKeys[c.provider as 'deepseek' | 'minimax'] = Boolean(c.has_api_key)
      form.api_key = ''
      form.api_base = c.api_base
      form.text_model = c.text_model
      form.image_model = c.image_model
      form.speech_model = c.speech_model
    }
  } catch { /* ignore */ }

  mounted = true
  viewActive = true
  await loadDashboard()
})

onActivated(() => {
  viewActive = true
  if (mounted) void loadDashboard()
})

onDeactivated(() => {
  viewActive = false
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
})

onBeforeUnmount(() => {
  viewActive = false
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
})

// --- 保存配置 ---
const saveConfig = async (provider: string) => {
  const form = provider === 'deepseek' ? deepseekForm : minimaxForm
  const saving = provider === 'deepseek' ? savingDeepseek : savingMinimax
  saving.value = true
  try {
    await settingsAPI.saveConfig({ ...form })
    savedKeys[provider as 'deepseek' | 'minimax'] = Boolean(form.api_key) || savedKeys[provider as 'deepseek' | 'minimax']
    form.api_key = ''
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
  if (!form.api_key && !savedKeys[provider as 'deepseek' | 'minimax']) { ElMessage.warning('请先填写 API Key'); return }
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

.section {
  margin-bottom: 36px;
  h3 { font-size: 0.9375rem; font-weight: 600; color: var(--color-text-primary); margin: 0 0 4px; }
}
.section-desc { font-size: 0.8125rem; color: var(--color-text-muted); margin: 0 0 16px; }

.worker-panel {
  min-height: 64px;
  padding: 12px 16px;
  background: var(--color-bg-paper);
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  display: grid;
  grid-template-columns: repeat(4, 1fr) auto;
  align-items: center;
  gap: 16px;
}

.worker-stat {
  min-width: 0;
  span { display: block; font-size: 0.6875rem; color: var(--color-text-muted); }
  strong { display: block; margin-top: 2px; font-size: 0.875rem; color: var(--color-text-primary); }
}

.worker-meta {
  min-height: 26px;
  padding-top: 6px;
  display: flex;
  justify-content: flex-end;
  gap: 16px;
  color: var(--color-text-muted);
  font-size: 0.6875rem;
}

.reserve-row {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr auto 1fr auto;
  align-items: center;
  gap: 10px;
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.preprocess-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  .section-desc { margin-bottom: 12px; }
}

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

.feedback-row {
  min-height: 64px;
  padding: 10px 12px;
  background: var(--color-bg-paper);
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  & + & { margin-top: 8px; }
}

.feedback-copy {
  min-width: 0;
  strong { display: block; font-size: 0.875rem; color: var(--color-text-primary); }
  span { display: block; font-size: 0.75rem; color: var(--color-text-secondary); }
  small { display: block; margin-top: 2px; color: var(--color-text-muted); overflow-wrap: anywhere; }
}

.version-list {
  min-height: 120px;
  max-height: 52vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.version-row {
  padding: 10px;
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  gap: 14px;
}

.version-media {
  width: 104px;
  aspect-ratio: 1 / 1;
  border-radius: 6px;
  overflow: hidden;
  background: var(--color-bg-muted);
  img { width: 100%; height: 100%; object-fit: cover; display: block; }
}

.version-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-light);
  font-size: 0.6875rem;
}

.version-copy {
  min-width: 0;
  p { margin: 8px 0 4px; color: var(--color-text-secondary); font-size: 0.8125rem; line-height: 1.5; }
  small { color: var(--color-text-muted); }
}

.version-title, .version-actions, .editor-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-title { justify-content: space-between; }
.version-actions { margin-top: 10px; }
.version-editor { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--color-border-light); }
.editor-actions { justify-content: flex-end; }
:deep(.el-form-item) { margin-bottom: 12px; }
:deep(.el-form-item__label) { font-size: 0.75rem; color: var(--color-text-muted); padding-bottom: 2px; }

@media (max-width: 640px) {
  .provider-cards { grid-template-columns: 1fr; }
  .toggle-desc { max-width: 220px; }
  .worker-panel { grid-template-columns: 1fr 1fr; }
  .reserve-row { grid-template-columns: 1fr auto; }
  .bank-info { flex-basis: 90px; }
  .feedback-row { grid-template-columns: minmax(0, 1fr) auto; }
  .feedback-row > .el-button { grid-column: 1 / -1; width: 100%; }
  .version-row { grid-template-columns: 76px minmax(0, 1fr); }
  .version-media { width: 76px; }
  .version-actions { flex-direction: column; align-items: stretch; }
}
</style>
