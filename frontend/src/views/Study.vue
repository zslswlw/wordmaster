<template>
  <div class="study-container">
    <el-card class="word-card">
      <template #header>
        <div class="header">
          <el-button @click="showQuitConfirm = true" circle size="small">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <div class="title-section">
            <h2>{{ enhanceMode ? '强化听写' : '单词学习' }}</h2>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
            </div>
            <p class="progress-text">{{ currentWordIndex }} / {{ totalWords }}</p>
          </div>
          <div class="placeholder"></div>
        </div>
      </template>

      <div class="word-content">
        <h3 class="meaning">{{ currentWord?.meaning }}</h3>
        <p class="phonetic">{{ currentWord?.phonetic }}</p>
        
        <div class="pronunciation-section">
          <button 
            class="sound-btn" 
            :class="{ playing: isPlaying }"
            @click="playPronunciation"
          >
            <el-icon :size="isMobile ? 28 : 32"><VideoPlay /></el-icon>
          </button>
          <div class="sound-hint">点击播放发音</div>
        </div>
      </div>

      <div class="input-section">
        <!-- 可见的输入框 - 移动端友好 -->
        <div v-if="!answerSubmitted" class="input-wrapper">
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
          <!-- 清除按钮 -->
          <button 
            v-if="userInput" 
            class="clear-btn" 
            @click="clearInput"
            type="button"
          >
            <el-icon><CircleClose /></el-icon>
          </button>
        </div>
        <!-- 提交按钮 -->
        <div v-if="!answerSubmitted" class="submit-area">
          <el-button 
            type="primary" 
            size="large" 
            @click="handleSubmit"
            :loading="submitting"
            :disabled="!userInput.trim()"
            class="submit-btn"
          >
            提交
          </el-button>
        </div>
      </div>

      <div v-if="answerSubmitted" class="result-area">
        <div :class="['result-box', lastResult?.correct ? 'correct' : 'wrong']">
          <div class="result-content">
            <el-icon :size="isMobile ? 32 : 40" v-if="lastResult?.correct"><CircleCheck /></el-icon>
            <el-icon :size="isMobile ? 32 : 40" v-else><CircleClose /></el-icon>
            <span class="result-text">{{ lastResult?.correct ? '回答正确!' : '回答错误' }}</span>
          </div>
          
          <!-- 答案对比区域 -->
          <div class="answer-comparison">
            <div class="answer-row">
              <span class="answer-label">你的答案</span>
              <span :class="['answer-value', 'user-answer', lastResult?.correct ? 'correct-text' : 'wrong-text']">
                {{ lastResult?.user_answer || '-' }}
              </span>
            </div>
            <div class="answer-row">
              <span class="answer-label">正确答案</span>
              <span class="answer-value correct-text">{{ lastResult?.correct_answer }}</span>
            </div>
          </div>
        </div>
        <el-button type="primary" size="large" @click="handleNext" autofocus class="next-btn">
          {{ isLastWord ? '查看结果' : '下一个' }} <el-icon><ArrowRight /></el-icon>
        </el-button>
        <p class="keyboard-hint" v-if="!isMobile">按 Enter 键继续</p>
      </div>
    </el-card>

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
        <el-icon :size="isMobile ? 48 : 60" :class="roundResultIconClass">
          <component :is="roundResultIcon" />
        </el-icon>
        <p class="result-message">{{ roundMessage }}</p>
        <div v-if="roundStats" class="round-stats">
          <el-statistic title="总单词" :value="roundStats.totalWords" value-style="color: #409EFF; font-size: 16px;" />
          <el-statistic title="本轮" :value="roundStats.total" value-style="color: #606266; font-size: 16px;" />
          <el-statistic title="正确" :value="roundStats.correct" value-style="color: #67c23a; font-size: 16px;" />
          <el-statistic title="错误" :value="roundStats.wrong" value-style="color: #f56c6c; font-size: 16px;" />
        </div>
      </div>
      <template #footer>
        <el-button v-if="nextStep === 'continue'" type="primary" size="large" @click="continueStudy" autofocus class="dialog-btn">
          {{ enhanceMode ? '继续强化' : '继续下一轮' }}
        </el-button>
        <el-button v-else-if="nextStep === 'enhance'" type="warning" size="large" @click="startEnhance" autofocus class="dialog-btn">
          开始强化听写
        </el-button>
        <el-button v-else type="success" size="large" @click="finishStudy" autofocus class="dialog-btn">
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
        <el-button @click="showQuitConfirm = false" size="large">继续学习</el-button>
        <el-button type="danger" @click="quitStudy" size="large">退出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { studyAPI, groupAPI, reviewAPI } from '../api'
import { useResponsive } from '../composables/useResponsive'
import { 
  ArrowLeft, 
  VideoPlay, 
  Close, 
  CircleCheck, 
  CircleClose, 
  Check, 
  Warning,
  ArrowRight
} from '@element-plus/icons-vue'

// 清除输入
const clearInput = () => {
  userInput.value = ''
  focusInput()
}

// 处理返回键
const handleBackButton = (e: PopStateEvent) => {
  if (!showRoundResult.value && !showQuitConfirm.value) {
    e.preventDefault()
    showQuitConfirm.value = true
    // 阻止默认返回行为
    history.pushState(null, '', location.href)
  }
}

const router = useRouter()
const route = useRoute()
const { isMobile } = useResponsive()
const groupId = ref<number>(0)
const isPlaying = ref(false)

// 从路由参数或查询参数中获取groupId
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

const currentWord = computed(() => {
  if (enhanceMode.value) {
    return enhanceWords.value[enhanceIndex.value]
  }
  return words.value[currentIndex.value]
})

const currentWordIndex = computed(() => {
  if (enhanceMode.value) {
    return enhanceIndex.value + 1
  }
  return currentIndex.value + 1
})

const totalWords = computed(() => {
  if (enhanceMode.value) {
    return enhanceWords.value.length
  }
  return words.value.length
})

const progressPercent = computed(() => {
  return (currentWordIndex.value / totalWords.value) * 100
})

const isLastWord = computed(() => {
  if (enhanceMode.value) {
    return enhanceIndex.value >= enhanceWords.value.length - 1
  }
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

    // 先尝试普通学习模式
    let response = await studyAPI.startStudy(groupId.value, isReview, false, planId.value || undefined)
    let isEnhanceMode = false
    
    // 如果没有可学习的单词，尝试强化学习模式
    if (response.data.word_ids.length === 0 && !isReview) {
      console.log('普通学习已完成，尝试强化学习模式')
      response = await studyAPI.startStudy(groupId.value, false, true, planId.value || undefined)
      if (response.data.word_ids.length > 0) {
        isEnhanceMode = true
        enhanceMode.value = true
        studyType.value = 'enhance'
      }
    }
    
    currentRound.value = response.data.current_round

    if (isEnhanceMode) {
      // 强化学习模式：使用 enhanceWordIds 和 enhanceWords
      enhanceWordIds.value = response.data.word_ids
      enhanceWords.value = []
      enhanceIndex.value = 0  // 重置索引
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
      // 普通学习模式：使用 wordIds 和 words
      wordIds.value = response.data.word_ids
      words.value = []
      currentIndex.value = 0  // 重置索引
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

const playPronunciation = () => {
  if (!currentWord.value) return
  
  const word = currentWord.value.word
  if ('speechSynthesis' in window) {
    isPlaying.value = true
    const utterance = new SpeechSynthesisUtterance(word)
    utterance.lang = 'en-US'
    utterance.rate = 0.8
    
    utterance.onend = () => {
      isPlaying.value = false
    }
    
    utterance.onerror = () => {
      isPlaying.value = false
    }
    
    speechSynthesis.speak(utterance)
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
    const response = await studyAPI.getRoundStats(groupId.value, currentRound.value, studyType.value)
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
        roundResultIconClass.value = 'correct-icon'
        nextStep.value = 'finish'
      } else {
        roundResultTitle.value = '本轮完成!'
        roundMessage.value = `恭喜你，本轮 ${currentStats.total} 个单词全部答对！`
        roundResultIcon.value = 'Check'
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
      roundResultIcon.value = 'Check'
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
      const response = await studyAPI.startStudy(groupId.value, isReview, false)
      wordIds.value = response.data.word_ids
      currentRound.value = response.data.current_round

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
    ElMessage.success('学习完成！')
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
  
  // 添加历史记录以拦截返回键
  history.pushState(null, '', location.href)
  window.addEventListener('popstate', handleBackButton)
  
  window.addEventListener('keydown', (e) => {
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
  max-width: 700px;
  margin: 0 auto;
  padding: 12px;
  min-height: calc(100vh - 100px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.word-card {
  width: 100%;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  
  :deep(.el-card__header) {
    border-bottom: 1px solid #ebeef5;
    padding: 16px;
  }
  
  :deep(.el-card__body) {
    padding: 24px 16px;
  }
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section {
  flex: 1;
  text-align: center;
  
  h2 {
    font-size: 18px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 10px;
  }
}

.progress-bar {
  width: 200px;
  height: 4px;
  background-color: #e4e7ed;
  border-radius: 2px;
  margin: 0 auto 6px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #409EFF, #66b1ff);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 13px;
  color: #909399;
  margin: 0;
}

.placeholder {
  width: 32px;
}

.word-content {
  text-align: center;
  margin-bottom: 24px;
}

.meaning {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  line-height: 1.4;
}

.phonetic {
  font-size: 16px;
  color: #606266;
  margin-bottom: 20px;
  font-family: 'Times New Roman', serif;
}

.pronunciation-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.sound-btn {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #409EFF, #66b1ff);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
  
  &:active {
    transform: scale(0.95);
  }
  
  &.playing {
    animation: pulse 1s infinite;
    background: linear-gradient(135deg, #67c23a, #85ce61);
    box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3);
  }
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.sound-hint {
  font-size: 12px;
  color: #909399;
}

.input-section {
  margin-top: 20px;
  text-align: center;
}

// 输入框包装器
.input-wrapper {
  position: relative;
  margin-bottom: 12px;
  display: flex;
  justify-content: center;
}

.word-input {
  width: 100%;
  min-height: 56px;
  padding: 12px 44px 12px 16px;
  background-color: #f5f7fa;
  border: 2px solid #e4e7ed;
  border-radius: 12px;
  font-family: 'Courier New', monospace;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  letter-spacing: 1px;
  text-align: center; // 文字居中
  transition: all 0.3s ease;
  box-sizing: border-box;
  
  &:focus {
    outline: none;
    border-color: #409EFF;
    background-color: #fff;
    box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.1);
  }
  
  &::placeholder {
    color: #c0c4cc;
    font-weight: 400;
  }
  
  // 禁用自动填充背景色
  &:-webkit-autofill,
  &:-webkit-autofill:hover,
  &:-webkit-autofill:focus {
    -webkit-box-shadow: 0 0 0px 1000px #f5f7fa inset;
    transition: background-color 5000s ease-in-out 0s;
  }
}

// 清除按钮
.clear-btn {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  border: none;
  background: #dcdfe6;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  transition: all 0.2s ease;
  padding: 0;
  
  &:active {
    transform: translateY(-50%) scale(0.9);
    background: #c0c4cc;
  }
  
  .el-icon {
    font-size: 14px;
  }
}

// 移除旧的样式
.typing-display,
.typed-text,
.cursor,
.cursor-blink,
.hidden-input {
  display: none;
}

.submit-area {
  margin-top: 12px;
}

.submit-btn {
  width: 100%;
  height: 48px;
  font-size: 17px;
  border-radius: 24px;
}

.result-area {
  margin-top: 20px;
  text-align: center;
}

.result-box {
  padding: 20px 16px;
  border-radius: 12px;
  margin-bottom: 16px;
  animation: slideIn 0.3s ease;
  
  &.correct {
    background-color: #f0f9eb;
    border: 1px solid #b3e19d;
  }
  
  &.wrong {
    background-color: #fef0f0;
    border: 1px solid #fbc4c4;
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.result-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 12px;
}

.result-text {
  font-size: 18px;
  font-weight: 600;
}

.result-box.correct .result-text {
  color: #67c23a;
}

.result-box.wrong .result-text {
  color: #f56c6c;
}

.answer-comparison {
  margin-top: 16px;
  padding: 12px;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
}

.answer-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 8px 0;
  font-size: 15px;
}

.answer-label {
  min-width: 70px;
  text-align: right;
  color: #909399;
  font-size: 13px;
  font-weight: 500;
}

.answer-value {
  min-width: 100px;
  text-align: left;
  font-family: 'Courier New', monospace;
  font-size: 18px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 6px;
  background-color: #f5f7fa;
  border: 2px solid transparent;
  letter-spacing: 1px;
}

.correct-text {
  color: #67c23a;
}

.wrong-text {
  color: #f56c6c;
}

.next-btn {
  width: 100%;
  height: 48px;
  font-size: 17px;
  border-radius: 24px;
}

.keyboard-hint {
  margin-top: 12px;
  color: #909399;
  font-size: 13px;
}

.round-result {
  text-align: center;
  padding: 10px 0;
  
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
  font-size: 15px;
  color: #606266;
  margin-bottom: 16px;
  line-height: 1.5;
}

.round-stats {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.dialog-btn {
  width: 100%;
  height: 44px;
}

// 桌面端样式
@media (min-width: 768px) {
  .study-container {
    padding: 20px;
  }
  
  .word-card {
    :deep(.el-card__header) {
      padding: 20px;
    }
    
    :deep(.el-card__body) {
      padding: 40px;
    }
  }
  
  .title-section h2 {
    font-size: 20px;
    margin-bottom: 12px;
  }
  
  .progress-bar {
    width: 300px;
    height: 4px;
    margin-bottom: 8px;
  }
  
  .progress-text {
    font-size: 14px;
  }
  
  .word-content {
    margin-bottom: 40px;
  }
  
  .meaning {
    font-size: 28px;
    margin-bottom: 16px;
  }
  
  .phonetic {
    font-size: 18px;
    margin-bottom: 30px;
  }
  
  .sound-btn {
    width: 64px;
    height: 64px;
  }
  
  .sound-hint {
    font-size: 13px;
  }
  
  .input-section {
    margin-top: 30px;
  }
  
  .typing-display {
    min-height: 60px;
    padding: 12px 20px;
    margin-bottom: 16px;
    font-size: 28px;
  }
  
  .submit-btn {
    width: auto;
    min-width: 120px;
    height: 44px;
    font-size: 16px;
  }
  
  .result-area {
    margin-top: 30px;
  }
  
  .result-box {
    padding: 24px;
    margin-bottom: 20px;
  }
  
  .result-text {
    font-size: 20px;
  }
  
  .answer-comparison {
    margin-top: 20px;
    padding: 20px 40px;
    display: inline-block;
  }
  
  .answer-row {
    gap: 20px;
    margin: 12px 0;
    font-size: 18px;
  }
  
  .answer-label {
    min-width: 80px;
    font-size: 14px;
  }
  
  .answer-value {
    min-width: 150px;
    font-size: 24px;
    padding: 8px 16px;
  }
  
  .next-btn {
    width: auto;
    min-width: 120px;
    height: 44px;
    font-size: 16px;
  }
  
  .keyboard-hint {
    margin-top: 16px;
  }
  
  .round-result {
    padding: 20px 0;
    
    .el-icon {
      margin-bottom: 16px;
    }
  }
  
  .result-message {
    font-size: 16px;
    margin-bottom: 20px;
  }
  
  .round-stats {
    gap: 30px;
    margin-top: 20px;
  }
}

// 横屏优化
@media (orientation: landscape) and (max-width: 1024px) {
  .word-card :deep(.el-card__body) {
    padding: 20px;
  }
  
  .word-content {
    margin-bottom: 20px;
  }
  
  .meaning {
    font-size: 20px;
    margin-bottom: 8px;
  }
  
  .phonetic {
    font-size: 14px;
    margin-bottom: 16px;
  }
  
  .sound-btn {
    width: 48px;
    height: 48px;
  }
  
  .typing-display {
    min-height: 44px;
    font-size: 20px;
  }
  
  .result-box {
    padding: 16px;
  }
}
</style>
