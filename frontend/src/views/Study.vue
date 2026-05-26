<template>
  <div class="study-container">
    <!-- 顶部进度条 -->
    <div class="study-header animate-fade-in">
      <div class="header-top">
        <el-button @click="showQuitConfirm = true" circle class="back-btn">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <div class="title-section">
          <h2>{{ studyModeTitle }}</h2>
          <span class="round-badge" v-if="currentRound > 1">第 {{ currentRound }} 轮</span>
        </div>
        <div class="progress-info">
          <span class="progress-text">{{ currentWordIndex }} / {{ totalWords }}</span>
        </div>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
    </div>

    <!-- 单词卡片 -->
    <div class="word-card animate-fade-in-up delay-1">
      <div class="card-decoration">
        <div class="deco-circle"></div>
        <div class="deco-circle"></div>
      </div>

      <div class="word-display">
        <div class="meaning-text">{{ currentWord?.meaning }}</div>
        <div class="phonetic-text" v-if="currentWord?.phonetic">
          <span class="phonetic-label">音标</span>
          <span class="phonetic-value">{{ currentWord.phonetic }}</span>
        </div>
      </div>

      <div class="pronunciation-section">
        <button
          class="sound-btn"
          :class="{ playing: isPlaying }"
          @click="playPronunciation"
        >
          <el-icon :size="28"><VideoPlay /></el-icon>
          <span class="sound-wave" v-if="isPlaying"></span>
          <span class="sound-wave delay-1" v-if="isPlaying"></span>
          <span class="sound-wave delay-2" v-if="isPlaying"></span>
        </button>
        <span class="sound-hint">点击播放发音</span>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-section animate-fade-in-up delay-2">
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
          size="large"
          @click="handleSubmit"
          :loading="submitting"
          :disabled="!userInput.trim()"
          class="submit-btn"
        >
          提交答案
        </el-button>
      </div>

      <!-- 结果区域 -->
      <div v-if="answerSubmitted" class="result-area">
        <div :class="['result-box', lastResult?.correct ? 'correct' : 'wrong']">
          <div class="result-icon">
            <el-icon :size="40" v-if="lastResult?.correct"><CircleCheck /></el-icon>
            <el-icon :size="40" v-else><CircleClose /></el-icon>
          </div>
          <div class="result-text">
            {{ lastResult?.correct ? '回答正确!' : '回答错误' }}
          </div>

          <div class="answer-comparison">
            <div class="answer-row">
              <span class="answer-label">你的答案</span>
              <span :class="['answer-value', 'user-answer', lastResult?.correct ? 'correct' : 'wrong']">
                {{ lastResult?.user_answer || '-' }}
              </span>
            </div>
            <div class="answer-row">
              <span class="answer-label">正确答案</span>
              <span class="answer-value correct">{{ lastResult?.correct_answer }}</span>
            </div>
          </div>
        </div>

        <el-button
          type="primary"
          size="large"
          @click="handleNext"
          autofocus
          class="next-btn"
        >
          {{ isLastWord ? '查看结果' : '下一个' }}
          <el-icon><ArrowRight /></el-icon>
        </el-button>

        <div class="keyboard-hint" v-if="!isMobile">
          <span class="key"><span class="key-label">Enter</span> 继续</span>
          <span class="key-divider"></span>
          <span class="key"><span class="key-label">Space</span> 重播发音</span>
        </div>
      </div>
    </div>

    <!-- 轮次结束对话框 -->
    <el-dialog
      v-model="showRoundResult"
      :title="roundResultTitle"
      :width="isMobile ? '90%' : '420px'"
      :close-on-click-modal="false"
      :show-close="false"
      class="round-dialog"
    >
      <div class="round-result">
        <div :class="['result-icon-large', roundResultIconClass]">
          <el-icon :size="48"><component :is="roundResultIcon" /></el-icon>
        </div>
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
        <el-button
          v-if="nextStep === 'continue'"
          type="primary"
          size="large"
          @click="continueStudy"
          autofocus
          class="dialog-btn"
        >
          {{ nextStepButtonText }}
        </el-button>
        <el-button
          v-else-if="nextStep === 'enhance'"
          type="warning"
          size="large"
          @click="startEnhance"
          autofocus
          class="dialog-btn"
        >
          开始强化听写
        </el-button>
        <el-button
          v-else
          type="success"
          size="large"
          @click="finishStudy"
          autofocus
          class="dialog-btn"
        >
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
      <p class="quit-message">确定要退出学习吗？当前进度将不会保存。</p>
      <template #footer>
        <el-button @click="showQuitConfirm = false" size="large">继续学习</el-button>
        <el-button type="danger" @click="quitStudy" size="large">退出</el-button>
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
  Check,
  Warning
} from '@element-plus/icons-vue'

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
      console.log(`Local audio not found for "${word}", falling back to TTS`)
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

  private cleanMeaningForTTS(meaning: string): string {
    if (!meaning) return ''
    let cleaned = meaning.replace(/\b(n|v|adj|adv|prep|conj|vt|vi|art|num|int)\.\s*/gi, '')
    const segments = cleaned.split(/[；。;]/)
    let selectedSegments = segments.slice(0, 2)
    selectedSegments = selectedSegments.map(segment => {
      const parts = segment.split(/[，,]/)
      return parts[0].trim()
    })
    let result = selectedSegments.join('、')
    if (result.length > 20) {
      result = result.substring(0, 20) + '...'
    }
    result = result.replace(/\s+/g, ' ').trim()
    return result
  }

  private playChineseTTS(meaning: string): void {
    if ('speechSynthesis' in window) {
      const cleanedMeaning = this.cleanMeaningForTTS(meaning)
      const utterance = new SpeechSynthesisUtterance(cleanedMeaning)
      utterance.lang = 'zh-CN'
      utterance.rate = 1.0
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

  preload(word: string): void {
    if (this.cache.has(word)) return
    const audioPath = this.getAudioPath(word)
    const audio = new Audio(audioPath)
    audio.preload = 'auto'
    audio.oncanplaythrough = () => {
      this.cache.set(word, audio)
    }
    audio.load()
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
      setTimeout(() => {
        playPronunciation()
      }, 500)
    }
  } else {
    currentIndex.value++
    if (currentIndex.value >= words.value.length) {
      checkRoundResult()
    } else {
      focusInput()
      setTimeout(() => {
        playPronunciation()
      }, 500)
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
        roundResultIcon.value = 'Check'
        roundResultIconClass.value = 'success'
        nextStep.value = 'finish'
      } else {
        roundResultTitle.value = '本轮完成!'
        roundMessage.value = `恭喜你，本轮 ${currentStats.total} 个单词全部答对！`
        roundResultIcon.value = 'Check'
        roundResultIconClass.value = 'success'
        nextStep.value = 'enhance'
      }
    } else {
      roundResultTitle.value = '本轮结果'
      roundMessage.value = `学习组共 ${data.total_words} 个单词，本轮听写 ${currentStats.total} 个单词，答对 ${currentStats.correct} 个，答错 ${currentStats.wrong} 个。`
      roundResultIcon.value = 'Warning'
      roundResultIconClass.value = 'warning'
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
      roundResultIcon.value = 'Check'
      roundResultIconClass.value = 'success'
      nextStep.value = 'finish'
    } else {
      roundResultTitle.value = '强化结果'
      roundMessage.value = `本轮听写 ${currentStats.total} 个单词，答对 ${currentStats.correct} 个，答错 ${currentStats.wrong} 个。`
      roundResultIcon.value = 'Warning'
      roundResultIconClass.value = 'warning'
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
      setTimeout(() => {
        playPronunciation()
      }, 500)
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
      setTimeout(() => {
        playPronunciation()
      }, 500)
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
    setTimeout(() => {
      playPronunciation()
    }, 500)
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
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
  min-height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

/* 顶部进度区域 */
.study-header {
  background: var(--color-bg-paper);
  border-radius: var(--radius-xl);
  padding: 20px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-md);
  border: 1px solid var(--color-border-light);
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.back-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-muted);
  color: var(--color-text-secondary);

  &:hover {
    background: var(--color-bg-base);
    color: var(--color-text-primary);
  }
}

.title-section {
  text-align: center;

  h2 {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }
}

.round-badge {
  display: inline-block;
  margin-top: 4px;
  padding: 2px 10px;
  background: linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.1) 0%, rgba(var(--color-primary-rgb), 0.05) 100%);
  color: var(--color-primary);
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: var(--radius-full);
}

.progress-info {
  text-align: right;
}

.progress-text {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--color-text-muted);
}

.progress-bar {
  height: 6px;
  background: var(--color-bg-muted);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border-radius: var(--radius-full);
  transition: width 0.4s ease;
}

/* 单词卡片 */
.word-card {
  background: var(--color-bg-paper);
  border-radius: var(--radius-xl);
  padding: 40px 32px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--color-border-light);
  position: relative;
  overflow: hidden;
  text-align: center;
}

.card-decoration {
  position: absolute;
  top: -30px;
  right: -30px;
  pointer-events: none;

  .deco-circle {
    position: absolute;
    width: 120px;
    height: 120px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.05) 0%, transparent 70%);

    &:last-child {
      top: 40px;
      right: 40px;
      width: 80px;
      height: 80px;
    }
  }
}

.word-display {
  position: relative;
  z-index: 1;
  margin-bottom: 32px;
}

.meaning-text {
  font-family: var(--font-display);
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.4;
  margin-bottom: 16px;
}

.phonetic-text {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: var(--color-bg-muted);
  border-radius: var(--radius-full);
}

.phonetic-label {
  font-size: 0.6875rem;
  color: var(--color-text-light);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.phonetic-value {
  font-family: var(--font-mono);
  font-size: 0.9375rem;
  color: var(--color-text-secondary);
}

/* 发音按钮 */
.pronunciation-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  position: relative;
  z-index: 1;
}

.sound-btn {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: all var(--transition-base);
  box-shadow: 0 8px 24px rgba(var(--color-primary-rgb), 0.35);

  &:hover {
    transform: scale(1.05);
    box-shadow: 0 12px 32px rgba(var(--color-primary-rgb), 0.45);
  }

  &:active {
    transform: scale(0.98);
  }

  &.playing {
    background: linear-gradient(135deg, var(--color-success) 0%, #3dd477 100%);
    box-shadow: 0 8px 24px rgba(45, 138, 94, 0.35);
    animation: pulse 1s infinite;
  }
}

.sound-wave {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid currentColor;
  opacity: 0;
  animation: soundWave 1.5s ease-out infinite;

  &.delay-1 {
    animation-delay: 0.3s;
  }

  &.delay-2 {
    animation-delay: 0.6s;
  }
}

@keyframes soundWave {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  100% {
    transform: scale(1.8);
    opacity: 0;
  }
}

.sound-hint {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}

/* 输入区域 */
.input-section {
  flex: 1;
}

.input-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.input-wrapper {
  position: relative;
}

.word-input {
  width: 100%;
  min-height: 60px;
  padding: 16px 50px 16px 20px;
  background: var(--color-bg-paper);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 500;
  color: var(--color-text-primary);
  text-align: center;
  letter-spacing: 0.1em;
  transition: all var(--transition-fast);
  box-sizing: border-box;

  &:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 4px rgba(var(--color-primary-rgb), 0.1);
  }

  &::placeholder {
    color: var(--color-text-light);
    font-weight: 400;
    letter-spacing: normal;
  }
}

.clear-btn {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  border: none;
  background: var(--color-bg-muted);
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  transition: all var(--transition-fast);

  &:hover {
    background: var(--color-border);
    color: var(--color-text-primary);
  }

  .el-icon {
    font-size: 14px;
  }
}

.submit-btn {
  width: 100%;
  height: 52px;
  font-size: 1rem;
  font-weight: 600;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border: none;
  box-shadow: 0 4px 16px rgba(var(--color-primary-rgb), 0.3);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(var(--color-primary-rgb), 0.4);
  }
}

/* 结果区域 */
.result-area {
  text-align: center;
}

.result-box {
  background: var(--color-bg-paper);
  border-radius: var(--radius-xl);
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-md);
  border: 1px solid var(--color-border-light);
  animation: fadeInUp 0.3s ease;

  &.correct {
    border-color: rgba(45, 138, 94, 0.2);
    background: linear-gradient(135deg, rgba(45, 138, 94, 0.03) 0%, rgba(45, 138, 94, 0.08) 100%);
  }

  &.wrong {
    border-color: rgba(196, 84, 74, 0.2);
    background: linear-gradient(135deg, rgba(196, 84, 74, 0.03) 0%, rgba(196, 84, 74, 0.08) 100%);
  }
}

.result-icon {
  margin-bottom: 8px;

  .el-icon {
    color: var(--color-success);
  }

  .wrong & .el-icon {
    color: var(--color-danger);
  }
}

.result-text {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 16px;

  .correct & {
    color: var(--color-success);
  }

  .wrong & {
    color: var(--color-danger);
  }
}

.answer-comparison {
  background: var(--color-bg-muted);
  border-radius: var(--radius-lg);
  padding: 16px;
}

.answer-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 8px 0;

  &:not(:last-child) {
    border-bottom: 1px solid var(--color-border-light);
  }
}

.answer-label {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  min-width: 70px;
  text-align: right;
}

.answer-value {
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 600;
  padding: 4px 16px;
  border-radius: var(--radius-md);
  background: var(--color-bg-paper);
  min-width: 120px;

  &.correct {
    color: var(--color-success);
  }

  &.wrong {
    color: var(--color-danger);
  }
}

.next-btn {
  width: 100%;
  height: 52px;
  font-size: 1rem;
  font-weight: 600;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border: none;
  box-shadow: 0 4px 16px rgba(var(--color-primary-rgb), 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(var(--color-primary-rgb), 0.4);
  }
}

.keyboard-hint {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  color: var(--color-text-muted);
  font-size: 0.8125rem;
}

.key {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.key-label {
  display: inline-block;
  padding: 2px 8px;
  background: var(--color-bg-muted);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  font-weight: 500;
  color: var(--color-text-secondary);
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.05);
}

.key-divider {
  width: 1px;
  height: 16px;
  background: var(--color-border);
}

/* 对话框 */
.round-result {
  text-align: center;
  padding: 16px 0;
}

.result-icon-large {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;

  &.success {
    background: linear-gradient(135deg, rgba(45, 138, 94, 0.1) 0%, rgba(45, 138, 94, 0.2) 100%);
    color: var(--color-success);
  }

  &.warning {
    background: linear-gradient(135deg, rgba(212, 134, 12, 0.1) 0%, rgba(212, 134, 12, 0.2) 100%);
    color: var(--color-warning);
  }
}

.result-message {
  font-size: 0.9375rem;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: 24px;
}

.round-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-item {
  text-align: center;
  padding: 12px 8px;
  background: var(--color-bg-muted);
  border-radius: var(--radius-md);

  .stat-num {
    display: block;
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
  }

  .stat-label {
    display: block;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    margin-top: 2px;
  }

  &.success .stat-num {
    color: var(--color-success);
  }

  &.danger .stat-num {
    color: var(--color-danger);
  }
}

.dialog-btn {
  width: 100%;
  height: 48px;
  font-weight: 600;
  border-radius: var(--radius-lg);
}

.quit-message {
  color: var(--color-text-secondary);
  text-align: center;
  font-size: 0.9375rem;
  line-height: 1.6;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .study-container {
    padding: 16px;
    padding-bottom: 100px;
  }

  .study-header {
    padding: 16px;
    margin-bottom: 16px;
  }

  .header-top {
    margin-bottom: 12px;
  }

  .title-section h2 {
    font-size: 1.125rem;
  }

  .word-card {
    padding: 32px 20px;
    margin-bottom: 20px;
  }

  .meaning-text {
    font-size: 1.375rem;
  }

  .phonetic-text {
    padding: 4px 12px;
  }

  .sound-btn {
    width: 64px;
    height: 64px;
  }

  .word-input {
    min-height: 56px;
    font-size: 1.125rem;
    padding: 14px 44px 14px 16px;
  }

  .submit-btn,
  .next-btn {
    height: 48px;
    font-size: 0.9375rem;
  }

  .result-box {
    padding: 20px 16px;
  }

  .result-text {
    font-size: 1.125rem;
  }

  .answer-value {
    font-size: 1.125rem;
    min-width: 100px;
  }

  .round-stats {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .stat-item .stat-num {
    font-size: 1.25rem;
  }
}

/* 横屏优化 */
@media (orientation: landscape) and (max-width: 1024px) {
  .study-container {
    padding: 12px;
    padding-bottom: 70px;
  }

  .word-card {
    padding: 24px 20px;
  }

  .meaning-text {
    font-size: 1.25rem;
  }

  .sound-btn {
    width: 56px;
    height: 56px;
  }

  .round-stats {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
