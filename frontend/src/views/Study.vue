<template>
  <div class="study-page" @click="focusInput">
    <!-- 顶栏：极简 -->
    <header class="top-bar">
      <button class="back-btn" @click.stop="showQuitConfirm = true">
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <div class="progress-wrap">
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>
        <span class="progress-num">{{ currentWordIndex }}/{{ totalWords }}</span>
      </div>
      <div class="top-right">
        <button class="phonetic-toggle" :class="{ active: showPhonetic }" @click.stop="togglePhonetic">
          <el-icon><ChatDotRound /></el-icon>
        </button>
        <button v-if="featureFlags.image_enabled && hasVisual" class="visual-toggle" :class="{ active: visualMode }" @click.stop="toggleVisualMode" title="视觉模式：看图识词">
          <el-icon><Picture /></el-icon>
        </button>
        <span class="round-badge" v-if="currentRound > 1">R{{ currentRound }}</span>
      </div>
    </header>

    <!-- 未提交：输入态 -->
    <main v-if="!answerSubmitted" class="study-main">
      <div class="word-zone">
        <!-- 视觉模式：看图识词 -->
        <template v-if="visualMode && canUseVisual">
          <div class="visual-study-img-wrap">
            <VisualWordCard :src="learningContent.image_url" :alt="currentWord.word" />
          </div>
          <p class="visual-study-hint">看图拼写单词</p>
        </template>
        <template v-else>
          <p class="meaning">{{ displayMeaning }}</p>
        </template>
        <p v-if="isStubborn" class="stubborn-badge">需强化 · 已错 {{ currentStubbornCount }} 次</p>
        <p class="phonetic" v-if="currentWord?.phonetic && showPhonetic">{{ currentWord.phonetic }}</p>

        <button class="play-btn" :class="{ playing: isPlaying }" @click.stop="playPronunciation">
          <el-icon :size="20"><VideoPlay /></el-icon>
        </button>
      </div>

      <div class="type-zone">
        <p v-if="featureFlags.example_enabled && isStubborn && currentWord?.example_l1" class="stubborn-hint">{{ currentWord.example_l1 }}</p>
        <p v-else-if="!userInput" class="type-hint">输入单词，按 Enter 提交</p>

        <div v-if="userInput" class="word-display" :key="'input-'+currentWordIndex">
          <span class="typed-text">{{ userInput }}</span>
          <span class="caret"></span>
        </div>

        <div class="type-underline"></div>

        <input
          ref="inputRef"
          v-model="userInput"
          type="text"
          class="ghost-input"
          @keyup.enter="handleSubmit"
          :disabled="answerSubmitted"
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
          spellcheck="false"
          enterkeyhint="done"
          inputmode="text"
        />
      </div>
    </main>

    <!-- 已提交：结果态 -->
    <main v-else class="study-main result-mode">
      <div class="word-zone dimmed">
        <p class="meaning">{{ displayMeaning }}</p>
      </div>

      <div class="result-area">
        <!-- 对/错大图标 -->
        <div class="verdict" :class="lastResult?.correct ? 'hit' : 'miss'">
          <span class="verdict-icon">{{ lastResult?.correct ? '✓' : '✗' }}</span>
        </div>

        <!-- 答案对比 -->
        <div class="compare">
          <div class="compare-row">
            <span class="compare-label">你的</span>
            <span class="compare-word" :class="lastResult?.correct ? 'green' : 'red'">{{ lastResult?.user_answer || '-' }}</span>
          </div>
          <div v-if="!lastResult?.correct" class="compare-row correct-row">
            <span class="compare-label">正确</span>
            <span class="compare-word green">{{ lastResult?.correct_answer }}</span>
          </div>
        </div>

        <!-- L2 语境卡：答对后展示例句 -->
        <div v-if="featureFlags.example_enabled && lastResult?.correct && currentWord?.example_l2" class="context-card">
          <p class="context-label">例句</p>
          <p class="context-example">{{ currentWord.example_l2 }}</p>
          <p v-if="currentWord.example_l1" class="context-l1">{{ currentWord.example_l1 }}</p>
        </div>

        <div v-if="featureFlags.mnemonic_enabled && learningContent.memory_anchor" class="deep-card">
          <div class="deep-section">
            <p class="deep-label">记忆锚点</p>
            <p class="deep-text">{{ learningContent.memory_anchor }}</p>
          </div>
        </div>

        <template v-if="featureFlags.image_enabled">
          <VisualWordCard v-if="learningContent.image_url" :src="learningContent.image_url" :alt="currentWord.word" />
          <div v-else class="memory-placeholder">
            <el-icon :size="28"><Picture /></el-icon>
            <span>图像正在后台准备</span>
          </div>
        </template>

        <div v-if="learningContent.bundle_id" class="resource-actions">
          <span v-if="learningContent.feedback_status === 'pending'" class="feedback-pending">素材待更新</span>
          <el-button v-else text size="small" @click.stop="openFeedback">
            <el-icon><ChatLineRound /></el-icon>
            反馈素材
          </el-button>
        </div>

        <!-- 提示 -->
        <p class="next-hint">
          <span class="hint-key">Enter</span> {{ isLastWord ? '查看结果' : '下一个单词' }}
          <span class="hint-sep"></span>
          <span class="hint-key">Space</span> 重播发音
        </p>
      </div>
    </main>

    <!-- 学习报告 -->
    <el-dialog
      v-model="showSessionReport"
      title=""
      :width="isMobile ? '90%' : '500px'"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <SessionReport :errors="sessionErrors" @done="closeSessionReport" />
      <template #footer>
        <el-button type="primary" @click="closeSessionReport" class="dialog-btn">返回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showFeedback" title="反馈记忆素材" :width="isMobile ? '90%' : '380px'" @click.stop>
      <el-form label-position="top">
        <el-form-item label="需要更新">
          <el-segmented v-model="feedbackForm.component" :options="feedbackComponents" />
        </el-form-item>
        <el-form-item label="原因">
          <el-select v-model="feedbackForm.reason" style="width: 100%">
            <el-option v-for="reason in feedbackReasons" :key="reason" :label="reason" :value="reason" />
          </el-select>
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="feedbackForm.detail" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFeedback = false">取消</el-button>
        <el-button type="primary" :loading="submittingFeedback" @click="submitFeedback">提交</el-button>
      </template>
    </el-dialog>

    <!-- 退出确认（保持原样） -->
    <el-dialog v-model="showQuitConfirm" title="确认退出" :width="isMobile ? '85%' : '340px'">
      <p style="text-align:center;color:var(--color-text-muted);">确定要退出学习吗？当前进度将不会保存。</p>
      <template #footer>
        <el-button @click="showQuitConfirm = false">继续学习</el-button>
        <el-button type="danger" @click="quitStudy">退出</el-button>
      </template>
    </el-dialog>

    <!-- 轮次结束对话框（保持原样） -->
    <el-dialog
      v-model="showRoundResult"
      :title="roundResultTitle"
      :width="isMobile ? '90%' : '400px'"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <div class="round-end">
        <div class="round-end-icon" :class="roundResultIconClass">
          <el-icon :size="48"><component :is="roundResultIcon" /></el-icon>
        </div>
        <p class="round-end-msg">{{ roundMessage }}</p>
        <div v-if="roundStats" class="round-stats">
          <div class="round-stat"><strong>{{ roundStats.totalWords }}</strong><small>总单词</small></div>
          <div class="round-stat"><strong>{{ roundStats.total }}</strong><small>本轮</small></div>
          <div class="round-stat green"><strong>{{ roundStats.correct }}</strong><small>正确</small></div>
          <div class="round-stat red"><strong>{{ roundStats.wrong }}</strong><small>错误</small></div>
        </div>
      </div>
      <template #footer>
        <el-button v-if="nextStep === 'continue'" type="primary" @click="continueStudy" class="dialog-btn">{{ nextStepButtonText }}</el-button>
        <el-button v-else-if="nextStep === 'enhance'" type="warning" @click="startEnhance" class="dialog-btn">开始强化听写</el-button>
        <el-button v-else type="success" @click="finishStudy" class="dialog-btn">完成学习</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onActivated, onDeactivated, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { studyAPI, aiAPI, settingsAPI } from '../api'
import { useResponsive } from '../composables/useResponsive'
import SessionReport from '../components/SessionReport.vue'
import VisualWordCard from '../components/VisualWordCard.vue'
import { ArrowLeft, VideoPlay, ChatDotRound, ChatLineRound, Picture } from '@element-plus/icons-vue'

defineOptions({ name: 'Study' })

const router = useRouter()
const route = useRoute()
const { isMobile } = useResponsive()

const groupId = ref<number>(0)
const isPlaying = ref(false)
const userInput = ref('')
const answerSubmitted = ref(false)
const submitting = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

const words = ref<any[]>([])
const wordIds = ref<number[]>([])
const currentIndex = ref(0)

const enhanceMode = ref(false)
const enhanceWords = ref<any[]>([])
const enhanceWordIds = ref<number[]>([])
const enhanceIndex = ref(0)

const lastResult = ref<{ correct: boolean; correct_answer: string; user_answer?: string } | null>(null)
const sessionErrors = ref<Array<{ word: string; correct: string; user: string; meaning?: string }>>([])
const stubbornCount = reactive<Record<number, number>>({})

const currentStubbornCount = computed(() => currentWord.value ? stubbornCount[currentWord.value.id] || 0 : 0)
const isStubborn = computed(() => currentStubbornCount.value >= 2)

const roundStats = ref<{ correct: number; wrong: number; total: number; totalWords: number } | null>(null)
const currentRound = ref(1)
const showRoundResult = ref(false)
const roundResultTitle = ref('')
const roundMessage = ref('')
const roundResultIcon = ref('CircleCheck')
const roundResultIconClass = ref('success')
const nextStep = ref('')
const showQuitConfirm = ref(false)
const showSessionReport = ref(false)
const showFeedback = ref(false)
const submittingFeedback = ref(false)
const feedbackComponents = [
  { label: '图片', value: 'image' },
  { label: '记忆点', value: 'memory_anchor' },
]
const feedbackReasons = ['联系不强', '词义不准', '记忆点牵强', '图片过于普通', '图片质量差', '内容不适', '其他说明']
const feedbackForm = reactive({ component: 'image', reason: '联系不强', detail: '' })

const studyType = ref('new')
const planId = ref<number | null>(null)
const showPhonetic = ref(true)

const featureFlags = reactive({
  example_enabled: true,
  image_enabled: true,
  mnemonic_enabled: true,
  error_analysis_enabled: true,
  story_enabled: false,
})

const loadFeatureFlags = async () => {
  try {
    const { data } = await settingsAPI.getFeatureFlags()
    Object.assign(featureFlags, data)
  } catch { /* use defaults */ }
}

const loadPhoneticSetting = () => {
  const stored = localStorage.getItem('showPhonetic')
  if (stored !== null) showPhonetic.value = stored === 'true'
}
const togglePhonetic = () => {
  showPhonetic.value = !showPhonetic.value
  localStorage.setItem('showPhonetic', String(showPhonetic.value))
}

const visualMode = ref(false)
const hasVisual = computed(() => {
  const wordsList = enhanceMode.value ? enhanceWords.value : words.value
  return wordsList.some((w: any) => w?.learning_content?.image_url || w?.image_url)
})

const currentWord = computed(() => enhanceMode.value
  ? enhanceWords.value[enhanceIndex.value]
  : words.value[currentIndex.value])
const learningContent = computed(() => currentWord.value?.learning_content || {
  bundle_id: null,
  display_meaning: currentWord.value?.meaning || '',
  memory_anchor: currentWord.value?.mnemonic || null,
  image_url: currentWord.value?.image_url || null,
  narration_text: currentWord.value?.meaning || '',
  narration_audio_url: currentWord.value?.context_audio || null,
  feedback_status: 'none',
})
const displayMeaning = computed(() => learningContent.value.display_meaning || currentWord.value?.meaning || '')
const canUseVisual = computed(() => hasVisual.value && learningContent.value.image_url)
const toggleVisualMode = () => {
  if (!hasVisual.value) { ElMessage.info('当前学习组的图像仍在后台准备'); return }
  visualMode.value = !visualMode.value
}

const currentWordIndex = computed(() => (enhanceMode.value ? enhanceIndex.value : currentIndex.value) + 1)
const totalWords = computed(() => enhanceMode.value ? enhanceWords.value.length : words.value.length)
const progressPercent = computed(() => (currentWordIndex.value / totalWords.value) * 100)

const isLastWord = computed(() => (enhanceMode.value ? enhanceIndex.value : currentIndex.value) >= totalWords.value - 1)

const nextStepButtonText = computed(() => {
  if (enhanceMode.value) return '继续强化'
  if (studyType.value === 'review') return '继续复习'
  return '继续学习'
})

// --- Audio ---
class AudioManager {
  private cache = new Map<string, HTMLAudioElement>()
  private current: HTMLAudioElement | null = null
  private ttsTimer: number | null = null
  private sequence = 0
  private settlePending: ((value: boolean) => void) | null = null

  stop() {
    this.sequence++
    this.settlePending?.(false)
    this.settlePending = null
    this.current?.pause(); this.current = null
    if ('speechSynthesis' in window) speechSynthesis.cancel()
    if (this.ttsTimer) { clearTimeout(this.ttsTimer); this.ttsTimer = null }
  }

  private async delay(ms: number, sequence: number) {
    return new Promise<boolean>(resolve => {
      this.settlePending = resolve
      this.ttsTimer = window.setTimeout(() => {
        this.settlePending = null
        this.ttsTimer = null
        resolve(sequence === this.sequence)
      }, ms)
    })
  }

  private async playElement(audio: HTMLAudioElement, sequence: number) {
    this.current = audio
    audio.currentTime = 0
    return new Promise<boolean>(resolve => {
      const finish = (played: boolean) => {
        if (this.settlePending !== finish) return
        this.settlePending = null
        audio.onended = null
        audio.onerror = null
        resolve(played && sequence === this.sequence)
      }
      this.settlePending = finish
      audio.onended = () => finish(true)
      audio.onerror = () => finish(false)
      audio.play().catch(() => finish(false))
    })
  }

  private async speak(text: string, lang: string, rate: number, sequence: number) {
    if (!('speechSynthesis' in window)) return false
    return new Promise<boolean>(resolve => {
      const utterance = new SpeechSynthesisUtterance(text)
      const finish = (played: boolean) => {
        if (this.settlePending !== finish) return
        this.settlePending = null
        resolve(played && sequence === this.sequence)
      }
      this.settlePending = finish
      utterance.lang = lang
      utterance.rate = rate
      utterance.onend = () => finish(true)
      utterance.onerror = () => finish(false)
      speechSynthesis.speak(utterance)
    })
  }

  async playEnglish(word: string, sequence: number) {
    if (this.cache.has(word)) {
      const played = await this.playElement(this.cache.get(word)!, sequence)
      if (played) return true
    }
    try {
      const a = new Audio(`/audio/${word[0].toLowerCase()}/${word.toLowerCase()}.mp3`)
      a.preload = 'auto'
      this.cache.set(word, a)
      const played = await this.playElement(a, sequence)
      if (played) return true
    } catch {
      // Browser speech is the final English fallback.
    }
    return this.speak(word, 'en-US', 0.8, sequence)
  }

  async playWithMeaning(word: string, narration: string, narrationAudio?: string) {
    this.stop()
    const sequence = this.sequence
    await this.playEnglish(word, sequence)
    if (sequence !== this.sequence || !await this.delay(350, sequence)) return
    if (narrationAudio) {
      const played = await this.playElement(new Audio(narrationAudio), sequence)
      if (played) return
    }
    await this.speak(narration, 'zh-CN', 1.0, sequence)
  }
}

const audio = new AudioManager()

const playPronunciation = async () => {
  if (!currentWord.value) return
  isPlaying.value = true
  try {
    await audio.playWithMeaning(
      currentWord.value.word,
      learningContent.value.narration_text,
      learningContent.value.narration_audio_url,
    )
  } catch {}
  isPlaying.value = false
}

// --- 核心流程 ---
const focusInput = () => { nextTick(() => inputRef.value?.focus()) }

const handleSubmit = async () => {
  if (!userInput.value.trim() || submitting.value) return
  submitting.value = true
  try {
    const res = await studyAPI.checkAnswer({
      group_id: groupId.value,
      word_id: currentWord.value.id,
      user_input: userInput.value.trim(),
      round: currentRound.value,
      study_type: studyType.value,
      plan_id: planId.value || undefined
    })
    lastResult.value = { correct: res.data.correct, correct_answer: res.data.correct_answer, user_answer: userInput.value.trim() }
    answerSubmitted.value = true
    aiAPI.recordExposure({
      word_id: currentWord.value.id,
      bundle_id: learningContent.value.bundle_id,
      group_id: groupId.value,
      plan_id: planId.value || undefined,
      study_type: studyType.value,
    }).catch(() => {})
    if (!lastResult.value.correct) {
      const wid = currentWord.value.id
      stubbornCount[wid] = (stubbornCount[wid] || 0) + 1
      sessionErrors.value.push({
        word: currentWord.value.word,
        correct: res.data.correct_answer,
        user: userInput.value.trim(),
        meaning: displayMeaning.value
      })
    }
    if (lastResult.value.correct) { setTimeout(() => playPronunciation(), 1000) }
  } catch { ElMessage.error('提交失败') }
  finally { submitting.value = false }
}

const openFeedback = () => {
  feedbackForm.component = learningContent.value.image_url ? 'image' : 'memory_anchor'
  feedbackForm.reason = '联系不强'
  feedbackForm.detail = ''
  showFeedback.value = true
}

const submitFeedback = async () => {
  if (!currentWord.value || !learningContent.value.bundle_id) return
  submittingFeedback.value = true
  try {
    await aiAPI.submitFeedback({
      word_id: currentWord.value.id,
      bundle_id: learningContent.value.bundle_id,
      ...feedbackForm,
    })
    currentWord.value.learning_content.feedback_status = 'pending'
    showFeedback.value = false
    ElMessage.success('已提交，替代版完成前继续使用当前素材')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '反馈提交失败')
  } finally {
    submittingFeedback.value = false
  }
}

const handleNext = () => {
  audio.stop(); isPlaying.value = false
  userInput.value = ''; answerSubmitted.value = false; lastResult.value = null
  if (enhanceMode.value) {
    enhanceIndex.value++
    enhanceIndex.value >= enhanceWords.value.length ? checkEnhanceResult() : (focusInput(), setTimeout(() => playPronunciation(), 500))
  } else {
    currentIndex.value++
    currentIndex.value >= words.value.length ? checkRoundResult() : (focusInput(), setTimeout(() => playPronunciation(), 500))
  }
}

// --- 统计 & 轮次 ---
const checkRoundResult = async () => {
  try {
    const res = await studyAPI.getRoundStats(groupId.value, currentRound.value, studyType.value, planId.value || undefined)
    const d = res.data; const s = d.current_round_stats || { correct: 0, wrong: 0, total: 0 }
    roundStats.value = { correct: s.correct, wrong: s.wrong, total: s.total, totalWords: d.total_words }
    if (s.wrong === 0 && (s.remaining || 0) === 0) {
      if (studyType.value === 'review') {
        roundResultTitle.value = '复习完成!'; roundMessage.value = `全部答对！复习完成！`; nextStep.value = 'finish'
      } else { roundResultTitle.value = '本轮完成!'; roundMessage.value = `全部答对！`; nextStep.value = 'enhance' }
      roundResultIcon.value = 'CircleCheck'; roundResultIconClass.value = 'success'
    } else {
      roundResultTitle.value = '本轮结果'; roundMessage.value = `共 ${d.total_words} 词，本轮 ${s.total} 词，对 ${s.correct} 错 ${s.wrong}`
      roundResultIcon.value = 'Warning'; roundResultIconClass.value = 'warning'; nextStep.value = 'continue'
    }
    showRoundResult.value = true
  } catch { ElMessage.error('获取统计失败') }
}

const checkEnhanceResult = async () => {
  try {
    const res = await studyAPI.getEnhanceStats(groupId.value, currentRound.value)
    const d = res.data; const s = d.current_round_stats || { correct: 0, wrong: 0, total: 0 }
    roundStats.value = { correct: s.correct, wrong: s.wrong, total: s.total, totalWords: d.total_words }
    if (s.wrong === 0 && (s.remaining || 0) === 0) {
      roundResultTitle.value = '学习完成!'; roundMessage.value = `全部答对！学习完成！`; nextStep.value = 'finish'
      roundResultIcon.value = 'CircleCheck'; roundResultIconClass.value = 'success'
    } else {
      roundResultTitle.value = '强化结果'; roundMessage.value = `本轮 ${s.total} 词，对 ${s.correct} 错 ${s.wrong}`
      roundResultIcon.value = 'Warning'; roundResultIconClass.value = 'warning'; nextStep.value = 'continue'
    }
    showRoundResult.value = true
  } catch { ElMessage.error('获取统计失败') }
}

const continueStudy = async () => {
  showRoundResult.value = false
  try {
    if (enhanceMode.value) {
      const res = await studyAPI.startStudy(groupId.value, false, true)
      if (res.data.is_completed) { await finishStudy(); return }
      enhanceWordIds.value = res.data.word_ids; currentRound.value = res.data.current_round; studyType.value = 'enhance'
      const arr = await Promise.all(enhanceWordIds.value.map(id => studyAPI.getWord(id)))
      enhanceWords.value = arr.map(r => r.data); enhanceIndex.value = 0
    } else {
      const isR = studyType.value === 'review'
      const res = await studyAPI.startStudy(groupId.value, isR, false, planId.value || undefined)
      if (res.data.is_completed) { await finishStudy(); return }
      wordIds.value = res.data.word_ids; currentRound.value = res.data.current_round
      const arr = await Promise.all(wordIds.value.map(id => studyAPI.getWord(id).catch(() => null)))
      words.value = arr.filter(Boolean).map(r => (r as any).data)
      if (!words.value.length) { if (isR) { await finishStudy(); return }; ElMessage.error('没有可学的单词'); return }
      currentIndex.value = 0
    }
    focusInput(); setTimeout(() => playPronunciation(), 500)
  } catch { ElMessage.error('加载失败') }
}

const startEnhance = async () => {
  showRoundResult.value = false; enhanceMode.value = true; studyType.value = 'enhance'
  try {
    const res = await studyAPI.startStudy(groupId.value, false, true)
    if (res.data.is_completed) { await finishStudy(); return }
    enhanceWordIds.value = res.data.word_ids; currentRound.value = res.data.current_round
    const arr = await Promise.all(enhanceWordIds.value.map(id => studyAPI.getWord(id)))
    enhanceWords.value = arr.map(r => r.data); enhanceIndex.value = 0
    if (!enhanceWords.value.length) { ElMessage.error('没有可学的单词'); return }
    focusInput(); setTimeout(() => playPronunciation(), 500)
  } catch { ElMessage.error('加载失败') }
}

const finishStudy = async () => {
  showRoundResult.value = false
  try {
    const { data } = await studyAPI.completeStudy(groupId.value, enhanceMode.value, studyType.value, planId.value ?? undefined)
    if (data.next_step === 'enhance') {
      await startEnhance()
      return
    }
    if (data.next_step === 'continue') {
      ElMessage.warning(`本轮还有 ${data.remaining_count || 0} 个单词未完成`)
      await continueStudy()
      return
    }
    showSessionReport.value = true
  } catch { ElMessage.error('保存失败') }
}

const closeSessionReport = () => {
  showSessionReport.value = false
  router.push('/groups')
}

const quitStudy = () => { showQuitConfirm.value = false; router.push('/groups') }

// --- 初始化 ---
// 用路由参数组合成唯一 key，避免同一组件重复初始化或不同 session 串了
const initKey = ref('')
const getInitKey = () => `${route.params.id || ''}-${route.query.planId || ''}-${route.query.isReview || ''}`

const initStudy = async (force = false) => {
  const key = getInitKey()
  if (!force && initKey.value === key) return  // 同一 session 已初始化过，不重跑
  initKey.value = key
  const id = route.params.id; const qId = route.query.groupId
  groupId.value = (id && !isNaN(Number(id))) ? Number(id) : (qId && !isNaN(Number(qId)) ? Number(qId) : 0)
  if (!groupId.value) { ElMessage.error('无效的学习组ID'); router.push('/groups'); return }
  studyType.value = 'new'
  planId.value = null
  enhanceMode.value = false

  try {
    const qPlanId = route.query.planId; const qIsReview = route.query.isReview === 'true'; let isReview = false
    if (qPlanId && qIsReview) { studyType.value = 'review'; planId.value = Number(qPlanId); isReview = true }
    else { const rid = localStorage.getItem('reviewPlanId'); if (rid) { studyType.value = 'review'; planId.value = Number(rid); isReview = true; localStorage.removeItem('reviewPlanId') } }

    let res = await studyAPI.startStudy(groupId.value, isReview, false, planId.value || undefined)
    if (res.data.is_completed) {
      if (isReview) await finishStudy()
      else await startEnhance()
      return
    }
    let isEnhanceMode = false
    if (res.data.word_ids.length === 0 && !isReview) {
      res = await studyAPI.startStudy(groupId.value, false, true, planId.value || undefined)
      if (res.data.word_ids.length > 0) { isEnhanceMode = true; enhanceMode.value = true; studyType.value = 'enhance' }
    }
    currentRound.value = res.data.current_round
    if (isEnhanceMode) {
      enhanceWordIds.value = res.data.word_ids; enhanceIndex.value = 0
      const arr = await Promise.all(enhanceWordIds.value.map(id => studyAPI.getWord(id).catch(() => null)))
      enhanceWords.value = arr.filter(Boolean).map(r => (r as any).data)
      if (!enhanceWords.value.length) { ElMessage.error('没有可学的单词'); router.push('/groups'); return }
    } else {
      wordIds.value = res.data.word_ids; currentIndex.value = 0
      const arr = await Promise.all(wordIds.value.map(id => studyAPI.getWord(id).catch(() => null)))
      words.value = arr.filter(Boolean).map(r => (r as any).data)
      if (!words.value.length) { ElMessage.error('没有可学的单词'); router.push('/groups'); return }
    }
    setTimeout(() => playPronunciation(), 500)
  } catch { ElMessage.error('加载单词失败'); router.push('/groups') }
}

onMounted(() => {
  loadPhoneticSetting(); loadFeatureFlags(); initStudy(); focusInput()
  history.pushState(history.state, '', location.href)
  window.addEventListener('popstate', (e: PopStateEvent) => {
    if (!showRoundResult.value && !showQuitConfirm.value) { e.preventDefault(); showQuitConfirm.value = true; history.pushState(history.state, '', location.href) }
  })
  window.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === ' ') {
      if (answerSubmitted.value && !showRoundResult.value) { e.preventDefault(); playPronunciation() }
      else { e.preventDefault() }
      return
    }
    if (e.key === 'Enter') {
      if (showSessionReport.value) {
        closeSessionReport()
      } else if (showRoundResult.value) {
        if (nextStep.value === 'continue') continueStudy()
        else if (nextStep.value === 'enhance') startEnhance()
        else if (nextStep.value === 'finish') finishStudy()
      } else if (answerSubmitted.value) { handleNext() }
    }
  })
})

// 路由离开时不重复初始化；激活时只恢复焦点，不重置进度
onActivated(() => { focusInput() })
onDeactivated(() => { audio.stop() })

// 监听路由变化：切到不同的 study session（不同 groupId / planId）才重新初始化
watch(getInitKey, (newKey, oldKey) => {
  if (newKey && newKey !== oldKey && newKey !== initKey.value) {
    // 显式重置状态再重跑 init
    currentIndex.value = 0; words.value = []; wordIds.value = []
    enhanceIndex.value = 0; enhanceWords.value = []; enhanceWordIds.value = []
    enhanceMode.value = false; studyType.value = 'new'; planId.value = null
    userInput.value = ''; answerSubmitted.value = false; lastResult.value = null
    sessionErrors.value = []; Object.keys(stubbornCount).forEach(k => delete stubbornCount[Number(k)])
    showRoundResult.value = false; showSessionReport.value = false
    initStudy(true)
  }
})

watch(userInput, () => { if (!answerSubmitted.value) focusInput() })
</script>

<style scoped lang="scss">
// ============================================
// 去表单化 · 极简输入体验
// ============================================

.study-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-base);
  outline: none;
}

// --- 顶栏 ---
.top-bar {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  gap: 12px;
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--color-bg-base);
}

.back-btn {
  width: 36px; height: 36px; border-radius: 50%;
  border: none; background: transparent;
  color: var(--color-text-muted); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  &:hover { background: var(--color-bg-muted); color: var(--color-text-primary); }
}

.progress-wrap {
  flex: 1; display: flex; align-items: center; gap: 10px; min-width: 0;
}

.progress-track {
  flex: 1; height: 3px; background: var(--color-border); border-radius: 3px; overflow: hidden;
}

.progress-fill {
  height: 100%; background: var(--color-text-primary);
  border-radius: 3px; transition: width 0.4s ease;
}

.progress-num {
  font-size: 0.75rem; color: var(--color-text-muted);
  font-variant-numeric: tabular-nums; flex-shrink: 0;
}

.top-right {
  display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}

.phonetic-toggle {
  width: 30px; height: 30px; border-radius: 50%; border: none;
  background: transparent; color: var(--color-text-light); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  &:hover { background: var(--color-bg-muted); }
  &.active { color: var(--color-primary); background: rgba(var(--color-primary-rgb), 0.08); }
}

.visual-toggle {
  width: 30px; height: 30px; border-radius: 50%; border: none;
  background: transparent; color: var(--color-text-light); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  &:hover { background: var(--color-bg-muted); }
  &.active { color: var(--color-success); background: rgba(var(--color-success-rgb), 0.08); }
}

.round-badge {
  font-size: 0.6875rem; font-weight: 600; color: var(--color-text-muted);
  padding: 2px 8px; background: var(--color-bg-muted); border-radius: 4px;
}

// --- 主区域 ---
.study-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 20px;
  gap: 48px;
  min-height: 0;
}

// --- 单词展示区 ---
.word-zone {
  text-align: center;
}

.meaning {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1.5;
  margin: 0;
  letter-spacing: 0.02em;
}

.stubborn-badge {
  margin: 8px 0 0 0;
  font-size: 0.75rem; font-weight: 500; color: var(--color-danger);
  padding: 2px 10px;
  background: rgba(var(--color-danger-rgb), 0.06);
  border: 1px solid rgba(var(--color-danger-rgb), 0.15);
  border-radius: 4px;
  display: inline-block;
}

.phonetic {
  font-size: 0.9375rem;
  color: var(--color-text-muted);
  margin: 8px 0 0 0;
  font-family: var(--font-mono);
}

.visual-study-img-wrap {
  max-width: 320px;
  margin: 0 auto;
}

.visual-study-hint {
  margin: 12px 0 0 0;
  font-size: 0.8125rem; color: var(--color-text-muted);
}

.play-btn {
  margin-top: 20px;
  width: 44px; height: 44px; border-radius: 50%;
  border: 1.5px solid var(--color-border);
  background: var(--color-bg-paper);
  color: var(--color-text-secondary);
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all 0.15s;
  &:hover { border-color: var(--color-text-muted); color: var(--color-text-primary); }
  &.playing { border-color: var(--color-success); color: var(--color-success); background: rgba(45,138,94,0.04); }
}

// --- 打字区 ---
.type-zone {
  text-align: center;
  min-height: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  gap: 12px;
}

.type-hint {
  color: var(--color-text-light);
  font-size: 0.9375rem;
  margin: 0;
}

.stubborn-hint {
  color: var(--color-text-secondary);
  font-size: 0.9375rem;
  margin: 0 0 4px;
  font-style: italic;
  max-width: 360px;
  line-height: 1.5;
}

.word-display {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 2px;
  min-height: 48px;
}

.typed-text {
  font-family: var(--font-mono);
  font-size: 2rem;
  font-weight: 400;
  color: var(--color-text-primary);
  letter-spacing: 0.04em;
  line-height: 1.4;
}

.caret {
  display: inline-block;
  width: 2px;
  height: 2rem;
  background: var(--color-primary);
  animation: caretBlink 1.2s step-end infinite;
}

@keyframes caretBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.type-underline {
  width: 240px;
  max-width: 80vw;
  height: 1px;
  background: var(--color-border);
}

.ghost-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  width: 100%;
  height: 100%;
  cursor: text;
  font-size: 16px;
}

// --- 结果态 ---
.result-mode {
  gap: 24px;
}

.result-area {
  width: min(100%, 440px);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.word-zone.dimmed .meaning {
  color: var(--color-text-muted);
  font-size: 1.25rem;
}

.verdict {
  width: 56px; height: 56px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 20px;
  &.hit { background: rgba(var(--color-success-rgb), 0.06); }
  &.miss { background: rgba(var(--color-danger-rgb), 0.06); }
}

.verdict-icon {
  font-size: 1.75rem; font-weight: 600;
  .hit & { color: var(--color-success); }
  .miss & { color: var(--color-danger); }
}

.compare {
  display: flex; flex-direction: column; gap: 8px;
  align-items: center;
}

.compare-row {
  display: flex; align-items: center; gap: 12px;
}

.compare-label {
  font-size: 0.75rem; color: var(--color-text-muted); min-width: 28px; text-align: right;
}

.compare-word {
  font-family: var(--font-mono); font-size: 1.125rem; font-weight: 500;
  padding: 6px 16px; border-radius: 6px; background: var(--color-bg-muted);
  min-width: 120px; text-align: center;
  &.green { color: var(--color-success); }
  &.red { color: var(--color-danger); }
}

.correct-row { margin-top: 2px; }

// --- L2 语境卡 ---
.context-card {
  margin-top: 20px;
  padding: 14px 18px;
  background: rgba(var(--color-success-rgb), 0.03);
  border: 1px solid rgba(var(--color-success-rgb), 0.1);
  border-radius: var(--radius-md);
  max-width: 420px;
  width: 100%;
  text-align: left;
}

.context-label {
  font-size: 0.6875rem; font-weight: 600; color: var(--color-success);
  text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 6px;
}

.context-example {
  font-size: 0.9375rem; color: var(--color-text-primary); line-height: 1.6; margin: 0;
  font-style: italic;
}

.context-l1 {
  font-size: 0.8125rem; color: var(--color-text-muted); margin: 6px 0 0;
}

// --- L3 深度卡 ---
.deep-card {
  margin-top: 16px;
  padding: 14px 18px;
  background: rgba(var(--color-warning-rgb), 0.04);
  border: 1px solid rgba(var(--color-warning-rgb), 0.12);
  border-radius: var(--radius-md);
  max-width: 420px;
  width: 100%;
  text-align: left;
}

.deep-section {
  & + & { margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(var(--color-warning-rgb), 0.08); }
}

.deep-label {
  font-size: 0.6875rem; font-weight: 600; color: var(--color-warning);
  text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 4px;
}

.deep-text {
  font-size: 0.875rem; color: var(--color-text-secondary); line-height: 1.65; margin: 0;
}

// --- 视觉词卡 ---
:deep(.visual-word-card) {
  margin-top: 16px;
  max-width: 280px;
}

.memory-placeholder {
  width: min(280px, 72vw);
  aspect-ratio: 1 / 1;
  margin-top: 16px;
  border: 1px dashed var(--color-border);
  border-radius: 8px;
  background: var(--color-bg-muted);
  color: var(--color-text-light);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 0.75rem;
}

.resource-actions {
  min-height: 32px;
  margin-top: 6px;
  display: flex;
  align-items: center;
}

.feedback-pending {
  color: var(--color-warning);
  font-size: 0.75rem;
}

.next-hint {
  margin-top: 28px; font-size: 0.75rem; color: var(--color-text-muted);
  display: flex; align-items: center; gap: 6px;

  .hint-key {
    padding: 2px 6px; background: var(--color-bg-muted); border: 1px solid var(--color-border);
    border-radius: 4px; font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-secondary);
  }
  .hint-sep { width: 1px; height: 10px; background: var(--color-border); margin: 0 2px; }
}

// --- 对话框内样式 ---
.round-end { text-align: center; padding: 12px 0; }
.round-end-icon { margin-bottom: 16px; }
.round-end-icon.success { color: var(--color-success); }
.round-end-icon.warning { color: var(--color-warning); }
.round-end-msg { font-size: 0.9375rem; color: var(--color-text-secondary); margin: 0 0 20px; line-height: 1.6; }
.round-stats { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; }
.round-stat {
  text-align: center; padding: 12px 8px; background: var(--color-bg-muted); border-radius: 8px;
  strong { display: block; font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary); line-height: 1.2; }
  small { display: block; font-size: 0.6875rem; color: var(--color-text-muted); margin-top: 2px; }
  &.green strong { color: var(--color-success); }
  &.red strong { color: var(--color-danger); }
}
.dialog-btn { width: 100%; }

// --- 响应式 ---
@media (max-width: 480px) {
  .meaning { font-size: 1.5rem; }
  .typed-text { font-size: 1.5rem; }
  .verdict { width: 48px; height: 48px; }
  .verdict-icon { font-size: 1.5rem; }
  .compare-word { font-size: 1rem; min-width: 100px; }
  .round-stats { grid-template-columns: repeat(2,1fr); gap: 8px; }
  .round-stat strong { font-size: 1.25rem; }
  .type-underline { width: 180px; }
}

@media (min-width: 768px) {
  .study-main { padding: 40px 40px; gap: 64px; }
  .meaning { font-size: 2.5rem; }
  .typed-text { font-size: 2.5rem; }
}
</style>
