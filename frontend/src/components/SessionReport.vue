<template>
  <div class="session-report">
    <div class="report-header">
      <el-icon :size="36" color="var(--color-primary)"><DataAnalysis /></el-icon>
      <h3>学习报告</h3>
      <p class="report-sub">共 {{ errors.length }} 个错词</p>
    </div>

    <!-- 错词列表 -->
    <div v-if="errors.length > 0" class="error-list">
      <h4>错词回顾</h4>
      <div v-for="(e, i) in errors" :key="i" class="error-item">
        <div class="error-word-row">
          <span class="error-correct">{{ e.correct }}</span>
          <span class="error-arrow">←</span>
          <span class="error-user">{{ e.user }}</span>
        </div>
        <span v-if="e.meaning" class="error-meaning">{{ e.meaning }}</span>
      </div>
    </div>

    <!-- AI 错题分析 -->
    <div v-if="analysis" class="analysis-section">
      <h4>AI 错题分析</h4>
      <div class="analysis-content">{{ renderedAnalysis }}</div>
    </div>
    <div v-else-if="analyzing" class="analysis-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>AI 正在分析错题模式...</span>
    </div>
    <div v-else-if="analysisError" class="generation-error">{{ analysisError }}</div>
    <el-button v-if="!analysis && !analyzing && errors.length > 0 && analysisFailed" text type="primary" :loading="analyzing" @click="runAnalysis">
      <el-icon><MagicStick /></el-icon> 重试 AI 分析
    </el-button>

    <!-- AI 微故事 -->
    <div v-if="story" class="story-section">
      <h4>错词微故事</h4>
      <p class="story-text">{{ story }}</p>
    </div>
    <div v-else-if="generatingStory" class="analysis-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>AI 正在生成微故事...</span>
    </div>
    <div v-else-if="storyError" class="generation-error">{{ storyError }}</div>
    <el-button v-if="!story && !generatingStory && storyWords.length >= 3 && storyFailed" text type="primary" :loading="generatingStory" @click="runStory" class="story-btn">
      <el-icon><MagicStick /></el-icon> 重试生成微故事
    </el-button>

    <!-- 无错词 -->
    <div v-if="errors.length === 0" class="perfect">
      <span class="perfect-icon">🎯</span>
      <p>全部正确，完美！</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { aiAPI, settingsAPI } from '../api'
import { DataAnalysis, Loading, MagicStick } from '@element-plus/icons-vue'

const props = defineProps<{
  errors: Array<{ word: string; correct: string; user: string; meaning?: string }>
}>()

const emit = defineEmits(['done'])

const analyzing = ref(false)
const analysis = ref('')
const analysisFailed = ref(false)
const analysisError = ref('')
const generatingStory = ref(false)
const story = ref('')
const storyFailed = ref(false)
const storyError = ref('')

const storyWords = computed(() => Array.from(new Set(
  props.errors.map(error => error.correct.trim()).filter(Boolean)
)))

const renderedAnalysis = computed(() => {
  return analysis.value
})

onMounted(async () => {
  if (props.errors.length === 0) return
  try {
    const { data } = await settingsAPI.getFeatureFlags()
    if (data.error_analysis_enabled) await runAnalysis()
    if (data.story_enabled && storyWords.value.length >= 3) await runStory()
  } catch {
    await runAnalysis()
    if (storyWords.value.length >= 3) await runStory()
  }
})

const apiErrorMessage = (error: any, fallback: string) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail.message === 'string') return detail.message
  return fallback
}

const runAnalysis = async () => {
  if (props.errors.length === 0) return
  analyzing.value = true
  analysisFailed.value = false
  analysisError.value = ''
  analysis.value = ''
  try {
    const { data } = await aiAPI.analyzeErrors(props.errors)
    if (data.status === 'disabled') return
    // summary 优先；如果为空或缺失，从 patterns 构建可读文本
    if (data.summary) {
      analysis.value = data.summary
    } else if (Array.isArray(data.patterns) && data.patterns.length > 0) {
      analysis.value = data.patterns.map((p: any) => `【${p.name}】${p.explanation || ''}`).join('\n\n')
    } else {
      analysis.value = '未发现明显拼写模式，继续加油！'
    }
  } catch (error) {
    analysisFailed.value = true
    analysisError.value = apiErrorMessage(error, 'AI 分析暂时不可用，请稍后重试')
  } finally {
    analyzing.value = false
  }
}

const runStory = async () => {
  if (storyWords.value.length < 3) return
  generatingStory.value = true
  storyFailed.value = false
  storyError.value = ''
  story.value = ''
  try {
    const { data } = await aiAPI.generateStory(storyWords.value)
    if (data.status === 'disabled') return
    story.value = data.story || ''
    if (!data.story) {
      storyFailed.value = true
      storyError.value = '微故事没有生成完整，请重试'
    }
  } catch (error) {
    storyFailed.value = true
    storyError.value = apiErrorMessage(error, '微故事暂时无法生成，请稍后重试')
  } finally {
    generatingStory.value = false
  }
}
</script>

<style scoped lang="scss">
.session-report {
  text-align: center;
  padding: 8px 0;
}

.report-header {
  margin-bottom: 20px;
  h3 { font-size: 1.125rem; font-weight: 700; color: var(--color-text-primary); margin: 12px 0 4px; }
}
.report-sub { font-size: 0.8125rem; color: var(--color-text-muted); margin: 0; }

// error list
.error-list {
  text-align: left;
  margin-bottom: 20px;
  h4 { font-size: 0.8125rem; font-weight: 600; color: var(--color-text-muted); margin: 0 0 8px; text-transform: uppercase; letter-spacing: 0.05em; }
}

.error-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px;
  background: var(--color-bg-muted);
  border-radius: var(--radius-sm);
  & + & { margin-top: 4px; }
}

.error-word-row { display: flex; align-items: center; gap: 8px; }
.error-correct { font-family: var(--font-mono); font-weight: 600; color: var(--color-success); font-size: 0.9375rem; }
.error-arrow { color: var(--color-text-light); font-size: 0.75rem; }
.error-user { font-family: var(--font-mono); color: var(--color-danger); font-size: 0.9375rem; text-decoration: line-through; text-decoration-color: rgba(var(--color-danger-rgb), 0.3); }
.error-meaning { font-size: 0.75rem; color: var(--color-text-muted); }

// analysis
.analysis-section {
  text-align: left;
  margin-bottom: 20px;
  h4 { font-size: 0.8125rem; font-weight: 600; color: var(--color-text-muted); margin: 0 0 8px; text-transform: uppercase; letter-spacing: 0.05em; }
}

.analysis-content {
  font-size: 0.875rem; color: var(--color-text-secondary); line-height: 1.7;
  white-space: pre-line;
  padding: 12px 16px;
  background: rgba(var(--color-primary-rgb), 0.03);
  border: 1px solid rgba(var(--color-primary-rgb), 0.08);
  border-radius: var(--radius-sm);
}

.analysis-loading {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 16px; color: var(--color-text-muted); font-size: 0.8125rem;
}

.generation-error {
  margin: 8px 0 2px;
  color: var(--color-danger);
  font-size: 0.8125rem;
  line-height: 1.6;
}

// story
.story-section {
  text-align: left;
  margin-bottom: 20px;
  h4 { font-size: 0.8125rem; font-weight: 600; color: var(--color-text-muted); margin: 0 0 8px; text-transform: uppercase; letter-spacing: 0.05em; }
}

.story-text {
  font-size: 0.9375rem; color: var(--color-text-primary); line-height: 1.8;
  padding: 14px 16px;
  background: rgba(var(--color-primary-rgb), 0.03);
  border: 1px solid rgba(var(--color-primary-rgb), 0.08);
  border-radius: var(--radius-sm);
  font-style: italic;
  margin: 0;
}

.story-btn { margin-top: 8px; }

// perfect
.perfect {
  padding: 24px 0;
  .perfect-icon { font-size: 2.5rem; }
  p { font-size: 1rem; color: var(--color-success); font-weight: 500; margin: 8px 0 0; }
}
</style>
