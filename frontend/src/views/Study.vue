<template>
  <div class="study-container">
    <!-- 顶部进度条 -->
    <div class="study-header">
      <div class="header-left">
        <el-button @click="showQuitConfirm = true" circle size="small">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
      </div>
      <div class="header-center">
        <h2>{{ studyModeTitle }}</h2>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>
        <p class="progress-text">{{ currentWordIndex }} / {{ totalWords }}</p>
      </div>
      <div class="header-right">
        <span class="round-badge" v-if="currentRound > 1">第 {{ currentRound }} 轮</span>
        <button
          class="phonetic-toggle"
          :class="{ active: showPhonetic }"
          @click="togglePhonetic"
          :title="showPhonetic ? '隐藏音标' : '显示音标'"
        >
          <el-icon><ChatDotRound /></el-icon>
        </button>
      </div>
    </div>

    <!-- 单词卡片 -->
    <div class="word-card">
      <div class="word-display">
        <h3 class="meaning">{{ currentWord?.meaning }}</h3>
        <p class="phonetic" v-if="currentWord?.phonetic && showPhonetic">
          {{ currentWord.phonetic }}
        </p>
      </div>

      <div class="pronunciation-section">
        <button
          class="sound-btn"
          :class="{ playing: isPlaying }"
          @click="playPronunciation"
        >
          <el-icon :size="24"><VideoPlay /></el-icon>
        </button>
        <span class="sound-hint">点击播放发音</span>
      </div>

      <!-- 输入区域 -->
      <div class="input-section">
        <div v-if="!answerSubmitted" class="input-area">
          <div class="input-wrapper">
            <input
              ref="inputRef"
              v-model="userInput"
              type="text"
              class="word-input"
              @keyup.enter="handleSubmit"
              :disabled="answerSubmitted"
              autocomplete="off"
              autocorrect="off"
              autocapitalize="off"
              spellcheck="false"
              enterkeyhint="done"
              inputmode="text"
              placeholder="输入单词..."
            />
            <button
              v-if="userInput"
              class="clear-btn"
              @click="clearInput"
              type="button"
            >
              <el-icon><CircleClose /></el-icon>
            </button>
          </div>

          <el-button
            type="primary"
            @click="handleSubmit"
            :loading="submitting"
            :disabled="!userInput.trim()"
            class="submit-btn"
          >
            提交
          </el-button>
        </div>

        <!-- 结果区域 -->
        <div v-if="answerSubmitted" class="result-area">
          <div :class="['result-box', lastResult?.correct ? 'correct' : 'wrong']">
            <div class="result-icon">
              <el-icon v-if="lastResult?.correct"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
            </div>
            <span class="result-text">{{ lastResult?.correct ? '回答正确!' : '回答错误' }}</span>

            <div class="answer-comparison">
              <div class="answer-row">
                <span class="answer-label">你的答案</span>
                <span :class="['answer-value', lastResult?.correct ? 'correct' : 'wrong']">
                  {{ lastResult?.user_answer || '-' }}
                </span>
              </div>
              <div class="answer-row">
                <span class="answer-label">正确答案</span>
                <span class="answer-value correct">{{ lastResult?.correct_answer }}</span>
              </div>
            </div>
          </div>

          <el-button type="primary" @click="handleNext" class="next-btn">
            {{ isLastWord ? '查看结果' : '下一个' }}
            <el-icon><ArrowRight /></el-icon>
          </el-button>

          <p class="keyboard-hint" v-if="!isMobile">
            <span class="key"><span class="key-label">Enter</span> 继续</span>
            <span class="key-divider">|</span>
            <span class="key"><span class="key-label">Space</span> 重播</span>
          </p>
        </div>
      </div>
    </div>

    <!-- 轮次结束对话框 -->
    <el-dialog
      v-model="showRoundResult"
      :title="roundResultTitle"
      :width="isMobile ? '90%' : '400px'"
      :close-on-click-modal="false"
      :show-close="false"
      class="round-dialog"
    >
      <div class="round-result">
        <el-icon :size="48" :class="roundResultIconClass">
          <component :is="roundResultIcon" />
        </el-icon>
        <p class="result-message">{{ roundMessage }}</p>
        <div v-if="roundStats" class="round-stats">
          <div class="stat-item">
            <span class="stat-num">{{ roundStats.totalWords }}</span>
            <span class="stat-label">总单词</span>
          </div>
          <div class="stat-item">
            <span class="stat-num">{{ roundStats.total }}</span>
            <span class="stat-label">本轮</span>
          </div>
          <div class="stat-item success">
            <span class="stat-num">{{ roundStats.correct }}</span>
            <span class="stat-label">正确</span>
          </div>
          <div class="stat-item danger">
            <span class="stat-num">{{ roundStats.wrong }}</span>
            <span class="stat-label">错误</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button v-if="nextStep === 'continue'" type="primary" @click="continueStudy" class="dialog-btn">
          {{ nextStepButtonText }}
        </el-button>
        <el-button v-else-if="nextStep === 'enhance'" type="warning" @click="startEnhance" class="dialog-btn">
          开始强化听写
        </el-button>
        <el-button v-else type="success" @click="finishStudy" class="dialog-btn">
          完成学习
        </el-button>
      </template>
    </el-dialog>

    <!-- 退出确认对话框 -->
    <el-dialog
      v-model="showQuitConfirm"
      title="确认退出"
      :width="isMobile ? '85%' : '350px'"
    >
      <p>确定要退出学习吗？当前进度将不会保存。</p>
      <template #footer>
        <el-button @click="showQuitConfirm = false">继续学习</el-button>
        <el-button type="danger" @click="quitStudy">退出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { studyAPI } from '../api'
import { useResponsive } from '../composables/useResponsive'
import {
  ArrowLeft,
  VideoPlay,
  CircleCheck,
  CircleClose,
  ArrowRight,
  ChatDotRound
} from '@element-plus/icons-vue'

// 音标显示开关 - 使用 localStorage
const showPhonetic = ref(true)
const loadPhoneticSetting = () => {
  const stored = localStorage.getItem('showPhonetic')
  if (stored !== null) {
    showPhonetic.value = stored === 'true'
  }
}
const togglePhonetic = () => {
  showPhonetic.value = !showPhonetic.value
  localStorage.setItem('showPhonetic', String(showPhonetic.value))
}

const clearInput = () => {
  userInput.value = ''
  focusInput()
}

const handleBackButton = (e: PopStateEvent) => {
  if (!showRoundResult.value && !showQuitConfirm.value) {
    e.preventDefault()
    showQuitConfirm.value = true
    history.pushState(null, '', location.href)
  }
}

const router = useRouter()
const route = useRoute()
const { isMobile } = useResponsive()
const groupId = ref<number>(0)
const isPlaying = ref(false)

const initGroupId = () => {
  const id = route.params.id
  if (id && !isNaN(Number(id))) {
    groupId.value = Number(id)
    return true
  }
  const queryId = route.query.groupId
  if (queryId && !isNaN(Number(queryId))) {
    groupId.value = Number(queryId)
    return true
  }
  return false
}

const words = ref<any[]>([])
const wordIds = ref<number[]>([])
const currentIndex = ref(0)
const userInput = ref('')
const answerSubmitted = ref(false)
const lastResult = ref<{ correct: boolean; correct_answer: string; user_answer?: string } | null>(null)
const submitting = ref(false)

const enhanceMode = ref(false)
const enhanceWords = ref<any[]>([])
const enhanceWordIds = ref<number[]>([])
const enhanceIndex = ref(0)

const roundStats = ref<{ correct: number; wrong: number; total: number; totalWords: number } | null>(null)
const currentRound = ref(1)
const showRoundResult = ref(false)
const roundResultTitle = ref('')
const roundMessage = ref('')
const roundResultIcon = ref('')
const roundResultIconClass = ref('')
const nextStep = ref('')

const showQuitConfirm = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

const nextStepButtonText = computed(() => {
  if (enhanceMode.value) return '继续强化'
  if (studyType.value === 'review') return '继续复习'
  return '继续学习'
})

const currentWord = computed(() => {
  if (enhanceMode.value) return enhanceWords.value[enhanceIndex.value]
  return words.value[currentIndex.value]
})

const currentWordIndex = computed(() => {
  if (enhanceMode.value) return enhanceIndex.value + 1
  return currentIndex.value + 1
})

const totalWords = computed(() => {
  if (enhanceMode.value) return enhanceWords.value.length
  return words.value.length
})

const progressPercent = computed(() => {
  return (currentWordIndex.value / totalWords.value) * 100
})

const studyModeTitle = computed(() => {
  if (enhanceMode.value) return '强化听写'
  if (studyType.value === 'review') return '单词复习'
  return '单词学习'
})

const isLastWord = computed(() => {
  if (enhanceMode.value) return enhanceIndex.value >= enhanceWords.value.length - 1
  return currentIndex.value >= words.value.length - 1
})

const studyType = ref('new')
const planId = ref<number | null>(null)

const initStudy = async () => {
  if (!initGroupId()) {
    ElMessage.error('无效的学习组ID')
    router.push('/groups')
    return
  }

  try {
    const queryPlanId = route.query.planId
    const queryIsReview = route.query.isReview === 'true'
    let isReview = false

    if (queryPlanId && queryIsReview) {
      studyType.value = 'review'
      planId.value = Number(queryPlanId)
      isReview = true
    } else {
      const reviewPlanId = localStorage.getItem('reviewPlanId')
      isReview = !!reviewPlanId
      if (reviewPlanId) {
        studyType.value = 'review'
        planId.value = Number(reviewPlanId)
        localStorage.removeItem('reviewPlanId')
      }
    }

    let response = await studyAPI.startStudy(groupId.value, isReview, false, planId.value || undefined)
    let isEnhanceMode = false

    if (response.data.is_completed) {
      await finishStudy()
      return
    }

    if (response.data.word_ids.length === 0 && !isReview) {
      response = await studyAPI.startStudy(groupId.value, false, true, planId.value || undefined)
      if (response.data.word_ids.length > 0) {
        isEnhanceMode = true
        enhanceMode.value = true
        studyType.value = 'enhance'
      }
    }

    currentRound.value = response.data.current_round

    if (isEnhanceMode) {
      enhanceWordIds.value = response.data.word_ids
      enhanceWords.value = []
      enhanceIndex.value = 0
      for (const id of enhanceWordIds.value) {
        try {
          const wordResponse = await studyAPI.getWord(id)
          enhanceWords.value.push(wordResponse.data)
        } catch (error) {
          console.error(`获取单词 ${id} 详情失败`, error)
        }
      }
      if (enhanceWords.value.length === 0) {
        ElMessage.error('没有可学习的单词')
        router.push('/groups')
        return
      }
    } else {
      wordIds.value = response.data.word_ids
      words.value = []
      currentIndex.value = 0
      for (const id of wordIds.value) {
        try {
          const wordResponse = await studyAPI.getWord(id)
          words.value.push(wordResponse.data)
        } catch (error) {
          console.error(`获取单词 ${id} 详情失败`, error)
        }
      }
      if (words.value.length === 0) {
        ElMessage.error('没有可学习的单词')
        router.push('/groups')
        return
      }
    }

    setTimeout(() => {
      playPronunciation()
    }, 500)
  } catch (error) {
    ElMessage.error('加载单词失败')
    router.push('/groups')
  }
}

class AudioManager {
  private cache: Map<string, HTMLAudioElement> = new Map()
  private currentAudio: HTMLAudioElement | null = null
  private ttsTimeout: number | null = null

  private getAudioPath(word: string): string {
    const firstLetter = word[0].toLowerCase()
    return `/audio/${firstLetter}/${word.toLowerCase()}.mp3`
  }

  stop(): void {
    if (this.currentAudio) {
      this.currentAudio.pause()
      this.currentAudio.currentTime = 0
      this.currentAudio = null
    }
    if ('speechSynthesis' in window) {
      speechSynthesis.cancel()
    }
    if (this.ttsTimeout) {
      clearTimeout(this.ttsTimeout)
      this.ttsTimeout = null
    }
  }

  async play(word: string): Promise<void> {
    this.stop()

    if (this.cache.has(word)) {
      const audio = this.cache.get(word)!
      audio.currentTime = 0
      this.currentAudio = audio
      await audio.play()
      return
    }

    try {
      const audioPath = this.getAudioPath(word)
      const audio = new Audio(audioPath)
      await new Promise<void>((resolve, reject) => {
        audio.oncanplaythrough = () => resolve()
        audio.onerror = () => reject(new Error('Audio load failed'))
        audio.load()
      })
      this.cache.set(word, audio)
      this.currentAudio = audio
      await audio.play()
      return
    } catch (e) {
      console.log(`TTS fallback for "${word}"`)
    }

    this.playTTS(word)
  }

  private playTTS(word: string): void {
    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(word)
      utterance.lang = 'en-US'
      utterance.rate = 0.8
      speechSynthesis.speak(utterance)
    }
  }

  async playWithMeaning(word: string, meaning: string): Promise<void> {
    this.stop()
    await this.play(word)
    await new Promise(resolve => {
      this.ttsTimeout = window.setTimeout(resolve, 2000)
    })
    this.playChineseTTS(meaning)
  }

  private playChineseTTS(meaning: string): void {
    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(meaning)
      utterance.lang = 'zh-CN'
      utterance.rate = 1.0
      speechSynthesis.speak(utterance)
    }
  }
}

const audioManager = new AudioManager()

const playPronunciation = async () => {
  if (!currentWord.value) return
  isPlaying.value = true
  try {
    await audioManager.playWithMeaning(currentWord.value.word, currentWord.value.meaning)
  } catch (error) {
    console.error('Play audio failed:', error)
  } finally {
    setTimeout(() => {
      isPlaying.value = false
    }, 3000)
  }
}

const handleSubmit = async () => {
  if (!userInput.value.trim()) return
  submitting.value = true

  try {
    const response = await studyAPI.checkAnswer({
      group_id: groupId.value,
      word_id: currentWord.value.id,
      user_input: userInput.value.trim(),
      round: currentRound.value,
      study_type: studyType.value,
      plan_id: planId.value || undefined
    })

    lastResult.value = {
      correct: response.data.correct,
      correct_answer: response.data.correct_answer,
      user_answer: userInput.value.trim()
    }
    answerSubmitted.value = true

    if (lastResult.value.correct) {
      setTimeout(() => {
        playPronunciation()
      }, 1000)
    }
  } catch (error) {
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

const handleNext = () => {
  audioManager.stop()
  isPlaying.value = false
  userInput.value = ''
  answerSubmitted.value = false
  lastResult.value = null

  if (enhanceMode.value) {
    enhanceIndex.value++
    if (enhanceIndex.value >= enhanceWords.value.length) {
      checkEnhanceResult()
    } else {
      focusInput()
      setTimeout(() => playPronunciation(), 500)
    }
  } else {
    currentIndex.value++
    if (currentIndex.value >= words.value.length) {
      checkRoundResult()
    } else {
      focusInput()
      setTimeout(() => playPronunciation(), 500)
    }
  }
}

const focusInput = () => {
  setTimeout(() => {
    inputRef.value?.focus()
  }, 100)
}

const checkRoundResult = async () => {
  try {
    const response = await studyAPI.getRoundStats(groupId.value, currentRound.value, studyType.value, planId.value || undefined)
    const data = response.data
    const currentStats = data.current_round_stats || { correct: 0, wrong: 0, total: 0 }
    roundStats.value = {
      correct: currentStats.correct,
      wrong: currentStats.wrong,
      total: currentStats.total,
      totalWords: data.total_words
    }

    if (currentStats.wrong === 0) {
      if (studyType.value === 'review') {
        roundResultTitle.value = '复习完成!'
        roundMessage.value = `恭喜你，本轮 ${currentStats.total} 个单词全部答对！复习完成！`
        roundResultIcon.value = 'CircleCheck'
        roundResultIconClass.value = 'correct-icon'
        nextStep.value = 'finish'
      } else {
        roundResultTitle.value = '本轮完成!'
        roundMessage.value = `恭喜你，本轮 ${currentStats.total} 个单词全部答对！`
        roundResultIcon.value = 'CircleCheck'
        roundResultIconClass.value = 'correct-icon'
        nextStep.value = 'enhance'
      }
    } else {
      roundResultTitle.value = '本轮结果'
      roundMessage.value = `学习组共 ${data.total_words} 个单词，本轮听写 ${currentStats.total} 个单词，答对 ${currentStats.correct} 个，答错 ${currentStats.wrong} 个。`
      roundResultIcon.value = 'Warning'
      roundResultIconClass.value = 'warning-icon'
      nextStep.value = 'continue'
    }

    showRoundResult.value = true
  } catch (error) {
    ElMessage.error('获取统计结果失败')
  }
}

const checkEnhanceResult = async () => {
  try {
    const response = await studyAPI.getEnhanceStats(groupId.value, currentRound.value)
    const data = response.data
    const currentStats = data.current_round_stats || { correct: 0, wrong: 0, total: 0 }
    roundStats.value = {
      correct: currentStats.correct,
      wrong: currentStats.wrong,
      total: currentStats.total,
      totalWords: data.total_words
    }

    if (currentStats.wrong === 0) {
      roundResultTitle.value = '学习完成!'
      roundMessage.value = `恭喜你，强化听写 ${currentStats.total} 个单词全部答对，学习完成！`
      roundResultIcon.value = 'CircleCheck'
      roundResultIconClass.value = 'correct-icon'
      nextStep.value = 'finish'
    } else {
      roundResultTitle.value = '强化结果'
      roundMessage.value = `本轮听写 ${currentStats.total} 个单词，答对 ${currentStats.correct} 个，答错 ${currentStats.wrong} 个。`
      roundResultIcon.value = 'Warning'
      roundResultIconClass.value = 'warning-icon'
      nextStep.value = 'continue'
    }

    showRoundResult.value = true
  } catch (error) {
    ElMessage.error('获取统计结果失败')
  }
}

const continueStudy = async () => {
  showRoundResult.value = false

  if (enhanceMode.value) {
    try {
      const response = await studyAPI.startStudy(groupId.value, false, true)
      enhanceWordIds.value = response.data.word_ids
      currentRound.value = response.data.current_round
      studyType.value = 'enhance'

      if (response.data.is_completed) {
        await finishStudy()
        return
      }

      const wordPromises = enhanceWordIds.value.map(id => studyAPI.getWord(id))
      const wordResponses = await Promise.all(wordPromises)
      enhanceWords.value = wordResponses.map(r => r.data)
      enhanceIndex.value = 0
      focusInput()
      setTimeout(() => playPronunciation(), 500)
    } catch (error) {
      ElMessage.error('加载强化听写单词失败')
    }
  } else {
    try {
      const isReview = studyType.value === 'review'
      const response = await studyAPI.startStudy(groupId.value, isReview, false, planId.value || undefined)
      wordIds.value = response.data.word_ids
      currentRound.value = response.data.current_round

      if (response.data.is_completed) {
        await finishStudy()
        return
      }

      words.value = []
      for (const id of wordIds.value) {
        try {
          const wordResponse = await studyAPI.getWord(id)
          words.value.push(wordResponse.data)
        } catch (error) {
          console.error(`获取单词 ${id} 详情失败`, error)
        }
      }

      if (words.value.length === 0) {
        if (isReview) {
          await finishStudy()
          return
        }
        ElMessage.error('没有可学习的单词')
        return
      }

      currentIndex.value = 0
      focusInput()
      setTimeout(() => playPronunciation(), 500)
    } catch (error) {
      ElMessage.error('加载单词失败')
    }
  }
}

const startEnhance = async () => {
  showRoundResult.value = false
  enhanceMode.value = true
  studyType.value = 'enhance'

  try {
    const response = await studyAPI.startStudy(groupId.value, false, true)
    enhanceWordIds.value = response.data.word_ids
    currentRound.value = response.data.current_round

    if (response.data.is_completed) {
      await finishStudy()
      return
    }

    enhanceWords.value = []
    for (const id of enhanceWordIds.value) {
      try {
        const wordResponse = await studyAPI.getWord(id)
        enhanceWords.value.push(wordResponse.data)
      } catch (error) {
        console.error(`获取单词 ${id} 详情失败`, error)
      }
    }

    if (enhanceWords.value.length === 0) {
      ElMessage.error('没有可学习的单词')
      return
    }

    enhanceIndex.value = 0
    focusInput()
    setTimeout(() => playPronunciation(), 500)
  } catch (error) {
    ElMessage.error('加载强化听写单词失败')
  }
}

const finishStudy = async () => {
  showRoundResult.value = false

  try {
    await studyAPI.completeStudy(groupId.value, enhanceMode.value, studyType.value, planId.value)
    let successMessage = '学习完成！'
    if (enhanceMode.value) {
      successMessage = '强化听写完成！'
    } else if (studyType.value === 'review') {
      successMessage = '单词复习完成！'
    }
    ElMessage.success(successMessage)
    router.push('/groups')
  } catch (error) {
    ElMessage.error('保存学习记录失败')
  }
}

const quitStudy = () => {
  showQuitConfirm.value = false
  router.push('/groups')
}

onMounted(() => {
  loadPhoneticSetting()
  initStudy()
  focusInput()

  history.pushState(null, '', location.href)
  window.addEventListener('popstate', handleBackButton)

  window.addEventListener('keydown', (e) => {
    if (e.key === ' ') {
      if (answerSubmitted.value && !showRoundResult.value) {
        e.preventDefault()
        playPronunciation()
        return
      }
      e.preventDefault()
      return
    }

    if (e.key === 'Enter') {
      if (showRoundResult.value) {
        if (nextStep.value === 'continue') {
          continueStudy()
        } else if (nextStep.value === 'enhance') {
          startEnhance()
        } else if (nextStep.value === 'finish') {
          finishStudy()
        }
      } else if (answerSubmitted.value) {
        handleNext()
      }
    }
  })
})

watch(userInput, () => {
  if (!answerSubmitted.value) {
    focusInput()
  }
})
</script>

<style scoped lang="scss">
.study-container {
  padding: 12px;
  min-height: 100vh;
  box-sizing: border-box;
}

/* 顶部进度条 */
.study-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 0 4px;
}

.header-left, .header-right {
  width: 60px;
}

.header-center {
  flex: 1;
  text-align: center;

  h2 {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin: 0 0 8px 0;
  }
}

.progress-bar {
  height: 4px;
  background: #e4e7ed;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 4px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: #909399;
  margin: 0;
}

.round-badge {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
  font-size: 11px;
  border-radius: 10px;
}

.phonetic-toggle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: #f5f7fa;
  color: #909399;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  padding: 0;

  &:hover {
    background: #e4e7ed;
    color: #667eea;
  }

  &.active {
    background: rgba(102, 126, 234, 0.1);
    color: #667eea;
  }

  .el-icon {
    font-size: 14px;
  }
}

/* 单词卡片 */
.word-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.word-display {
  text-align: center;
  margin-bottom: 20px;
}

.meaning {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
  line-height: 1.4;
}

.phonetic {
  font-size: 14px;
  color: #909399;
  margin: 0;
  font-family: 'Times New Roman', serif;
}

/* 发音按钮 */
.pronunciation-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.sound-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;

  &:active {
    transform: scale(0.95);
  }

  &.playing {
    background: linear-gradient(135deg, #67c23a, #85ce61);
  }
}

.sound-hint {
  font-size: 12px;
  color: #909399;
}

/* 输入区域 */
.input-section {
  margin-top: 16px;
}

.input-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-wrapper {
  position: relative;
}

.word-input {
  width: 100%;
  padding: 12px 40px 12px 12px;
  background: #f5f7fa;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  font-size: 18px;
  font-family: 'Courier New', monospace;
  text-align: center;
  box-sizing: border-box;
  transition: all 0.2s;

  &:focus {
    outline: none;
    border-color: #667eea;
    background: #fff;
  }

  &::placeholder {
    color: #c0c4cc;
    font-size: 14px;
  }
}

.clear-btn {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 24px;
  border: none;
  background: #dcdfe6;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  padding: 0;

  .el-icon {
    font-size: 12px;
  }
}

.submit-btn {
  width: 100%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  color: #fff;
}

/* 结果区域 */
.result-area {
  margin-top: 16px;
  text-align: center;
}

.result-box {
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;

  &.correct {
    background: #f0f9eb;
    border: 1px solid #b3e19d;
  }

  &.wrong {
    background: #fef0f0;
    border: 1px solid #fbc4c4;
  }
}

.result-icon {
  margin-bottom: 8px;

  .el-icon {
    color: #67c23a;
  }

  .wrong & .el-icon {
    color: #f56c6c;
  }
}

.result-text {
  display: block;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;

  .correct & {
    color: #67c23a;
  }

  .wrong & {
    color: #f56c6c;
  }
}

.answer-comparison {
  padding: 12px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 6px;
}

.answer-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 6px 0;

  &:not(:last-child) {
    border-bottom: 1px solid #ebeef5;
  }
}

.answer-label {
  font-size: 12px;
  color: #909399;
}

.answer-value {
  font-family: 'Courier New', monospace;
  font-size: 16px;
  font-weight: 600;
  padding: 4px 12px;
  background: #fff;
  border-radius: 4px;

  &.correct {
    color: #67c23a;
  }

  &.wrong {
    color: #f56c6c;
  }
}

.next-btn {
  width: 100%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  color: #fff;
}

.keyboard-hint {
  margin-top: 12px;
  color: #909399;
  font-size: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
}

.key {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.key-label {
  padding: 2px 6px;
  background: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 11px;
  font-family: monospace;
}

.key-divider {
  color: #c0c4cc;
}

/* 轮次结果对话框 */
.round-result {
  text-align: center;
  padding: 16px 0;

  .el-icon {
    margin-bottom: 12px;
  }
}

.correct-icon {
  color: #67c23a;
}

.warning-icon {
  color: #e6a23c;
}

.result-message {
  font-size: 14px;
  color: #606266;
  margin-bottom: 20px;
  line-height: 1.5;
}

.round-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-item {
  text-align: center;
  padding: 12px 8px;
  background: #f5f7fa;
  border-radius: 8px;

  .stat-num {
    display: block;
    font-size: 20px;
    font-weight: 700;
    color: #303133;
  }

  .stat-label {
    display: block;
    font-size: 11px;
    color: #909399;
    margin-top: 2px;
  }

  &.success .stat-num {
    color: #67c23a;
  }

  &.danger .stat-num {
    color: #f56c6c;
  }
}

.dialog-btn {
  width: 100%;
}

/* 移动端适配 */
@media (max-width: 480px) {
  .study-container {
    padding: 8px;
  }

  .word-card {
    padding: 16px 12px;
  }

  .meaning {
    font-size: 18px;
  }

  .phonetic {
    font-size: 13px;
  }

  .sound-btn {
    width: 44px;
    height: 44px;
  }

  .word-input {
    font-size: 16px;
    padding: 10px 36px 10px 10px;
  }

  .answer-value {
    font-size: 14px;
    min-width: 80px;
  }

  .round-stats {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }

  .stat-item .stat-num {
    font-size: 18px;
  }
}

/* 桌面端样式 */
@media (min-width: 768px) {
  .study-container {
    padding: 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: calc(100vh - 48px);
  }

  .study-header {
    max-width: 500px;
    width: 100%;
    margin-bottom: 20px;
  }

  .word-card {
    max-width: 500px;
    width: 100%;
    padding: 32px 24px;
  }

  .header-center h2 {
    font-size: 18px;
  }

  .meaning {
    font-size: 24px;
    margin-bottom: 12px;
  }

  .phonetic {
    font-size: 16px;
    margin-bottom: 24px;
  }

  .sound-btn {
    width: 56px;
    height: 56px;
  }

  .input-area {
    flex-direction: row;
    align-items: center;
  }

  .word-input {
    font-size: 20px;
  }

  .submit-btn {
    width: auto;
    min-width: 100px;
    height: 44px;
  }

  .next-btn {
    width: auto;
    min-width: 120px;
  }
}
</style>