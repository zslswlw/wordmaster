<template>
  <div class="study-container">
    <el-card class="word-card">
      <template #header>
        <div class="header">
          <el-button @click="showQuitConfirm = true" circle>
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
            <el-icon :size="32"><VideoPlay /></el-icon>
          </button>
          <div class="sound-hint">点击播放发音</div>
        </div>
      </div>

      <div class="input-section">
        <!-- 打字效果显示区域 -->
        <div v-if="!answerSubmitted" class="typing-display" @click="focusInput">
          <span class="typed-text">{{ userInput }}</span>
          <span class="cursor" :class="{ 'cursor-blink': !answerSubmitted }">|</span>
        </div>
        <!-- 隐藏的实际输入框 -->
        <input
          ref="inputRef"
          v-model="userInput"
          type="text"
          class="hidden-input"
          @keyup.enter="handleSubmit"
          :disabled="answerSubmitted"
          autocomplete="off"
          autocapitalize="off"
          spellcheck="false"
        />
        <!-- 提交按钮 -->
        <div v-if="!answerSubmitted" class="submit-area">
          <el-button 
            type="primary" 
            size="large" 
            @click="handleSubmit"
            :loading="submitting"
            :disabled="!userInput.trim()"
          >
            提交
          </el-button>
        </div>
      </div>

      <div v-if="answerSubmitted" class="result-area">
        <div :class="['result-box', lastResult?.correct ? 'correct' : 'wrong']">
          <div class="result-content">
            <el-icon :size="40" v-if="lastResult?.correct"><CircleCheck /></el-icon>
            <el-icon :size="40" v-else><CircleClose /></el-icon>
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
        <p class="keyboard-hint">按 Enter 键继续</p>
      </div>
    </el-card>

    <!-- 轮次结束对话框 -->
    <el-dialog 
      v-model="showRoundResult" 
      :title="roundResultTitle" 
      width="400px" 
      :close-on-click-modal="false"
      :show-close="false"
      class="round-dialog"
    >
      <div class="round-result">
        <el-icon :size="60" :class="roundResultIconClass">
          <component :is="roundResultIcon" />
        </el-icon>
        <p class="result-message">{{ roundMessage }}</p>
        <div v-if="roundStats" class="round-stats">
          <el-statistic title="总单词" :value="roundStats.totalWords" value-style="color: #409EFF" />
          <el-statistic title="本轮" :value="roundStats.total" value-style="color: #606266" />
          <el-statistic title="正确" :value="roundStats.correct" value-style="color: #67c23a" />
          <el-statistic title="错误" :value="roundStats.wrong" value-style="color: #f56c6c" />
        </div>
      </div>
      <template #footer>
        <el-button v-if="nextStep === 'continue'" type="primary" size="large" @click="continueStudy" autofocus>
          {{ enhanceMode ? '继续强化 (Enter)' : '继续下一轮 (Enter)' }}
        </el-button>
        <el-button v-else-if="nextStep === 'enhance'" type="warning" size="large" @click="startEnhance" autofocus>
          开始强化听写 (Enter)
        </el-button>
        <el-button v-else type="success" size="large" @click="finishStudy" autofocus>
          完成学习 (Enter)
        </el-button>
      </template>
    </el-dialog>

    <!-- 退出确认对话框 -->
    <el-dialog
      v-model="showQuitConfirm"
      title="确认退出"
      width="350px"
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { studyAPI, groupAPI, reviewAPI } from '../api'
import { 
  ArrowLeft, 
  VideoPlay, 
  Close, 
  CircleCheck, 
  CircleClose, 
  Check, 
  Warning 
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const groupId = ref<number>(0)
const isPlaying = ref(false)

// 从路由参数或查询参数中获取groupId
const initGroupId = () => {
  // 优先从路由参数获取
  const id = route.params.id
  if (id && !isNaN(Number(id))) {
    groupId.value = Number(id)
    return true
  }
  // 从查询参数获取（复习模式）
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
const lastResult = ref<{ correct: boolean; correct_answer: string } | null>(null)
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

const studyType = ref('new') // 'new' or 'review'
const planId = ref<number | null>(null)

const initStudy = async () => {
  // 先初始化groupId
  if (!initGroupId()) {
    ElMessage.error('无效的学习组ID')
    router.push('/groups')
    return
  }

  try {
    // Check if this is a review session from query params (学习组管理界面跳转)
    const queryPlanId = route.query.planId
    const queryIsReview = route.query.isReview === 'true'
    let isReview = false

    if (queryPlanId && queryIsReview) {
      // 从学习组管理界面跳转的复习模式
      studyType.value = 'review'
      planId.value = Number(queryPlanId)
      isReview = true
    } else {
      // Check if this is a review session from localStorage (复习计划界面跳转)
      const reviewPlanId = localStorage.getItem('reviewPlanId')
      isReview = !!reviewPlanId
      if (reviewPlanId) {
        studyType.value = 'review'
        planId.value = Number(reviewPlanId)
        localStorage.removeItem('reviewPlanId')
      }
    }

    // 开始学习计划，获取单词ID列表
    const response = await studyAPI.startStudy(groupId.value, isReview, false)
    wordIds.value = response.data.word_ids
    currentRound.value = response.data.current_round

    // 串行获取单词详情，避免并发请求过多导致超时
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
      router.push('/groups')
      return
    }

    // Play first word pronunciation
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

    // 先设置结果，再显示结果区域，避免闪现错误提示
    lastResult.value = {
      correct: response.data.correct,
      correct_answer: response.data.correct_answer,
      user_answer: userInput.value.trim()
    }
    answerSubmitted.value = true

    // Play pronunciation of correct answer
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
      // End of enhance round
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
      // End of study round
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
    // 根据当前学习类型获取统计，复习模式使用 'review'，新学模式使用 'new'
    const response = await studyAPI.getRoundStats(groupId.value, currentRound.value, studyType.value)
    const data = response.data
    
    // 使用后端返回的当前轮次统计
    const currentStats = data.current_round_stats || { correct: 0, wrong: 0, total: 0 }
    roundStats.value = {
      correct: currentStats.correct,
      wrong: currentStats.wrong,
      total: currentStats.total,
      totalWords: data.total_words
    }
    
    if (currentStats.wrong === 0) {
      // All correct
      if (studyType.value === 'review') {
        // 复习模式：直接完成，没有强化学习环节
        roundResultTitle.value = '复习完成!'
        roundMessage.value = `恭喜你，本轮 ${currentStats.total} 个单词全部答对！复习完成！`
        roundResultIcon.value = 'Check'
        roundResultIconClass.value = 'correct-icon'
        nextStep.value = 'finish'
      } else {
        // 新学模式：进入强化学习环节
        roundResultTitle.value = '本轮完成!'
        roundMessage.value = `恭喜你，本轮 ${currentStats.total} 个单词全部答对！`
        roundResultIcon.value = 'Check'
        roundResultIconClass.value = 'correct-icon'
        nextStep.value = 'enhance'
      }
    } else {
      // Some wrong, show stats
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
    
    // 使用后端返回的当前轮次统计
    const currentStats = data.current_round_stats || { correct: 0, wrong: 0, total: 0 }
    roundStats.value = {
      correct: currentStats.correct,
      wrong: currentStats.wrong,
      total: currentStats.total,
      totalWords: data.total_words
    }
    
    if (currentStats.wrong === 0) {
      // All correct, finish study
      roundResultTitle.value = '学习完成!'
      roundMessage.value = `恭喜你，强化听写 ${currentStats.total} 个单词全部答对，学习完成！`
      roundResultIcon.value = 'Check'
      roundResultIconClass.value = 'correct-icon'
      nextStep.value = 'finish'
    } else {
      // Some wrong, continue enhance
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
      // 从后端获取上一轮错误的单词列表（已随机打乱）
      const response = await studyAPI.startStudy(groupId.value, false, true)
      enhanceWordIds.value = response.data.word_ids
      currentRound.value = response.data.current_round
      studyType.value = 'enhance'
      
      // 获取所有单词详情
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
      // 根据学习类型判断是否是复习模式
      const isReview = studyType.value === 'review'
      // 新学/复习模式：从后端获取上一轮错误的单词列表（已随机打乱）
      const response = await studyAPI.startStudy(groupId.value, isReview, false)
      wordIds.value = response.data.word_ids
      currentRound.value = response.data.current_round

      // 串行获取单词详情，避免并发请求过多导致超时
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
    // 从后端获取所有单词（已随机打乱）
    const response = await studyAPI.startStudy(groupId.value, false, true)
    enhanceWordIds.value = response.data.word_ids
    currentRound.value = response.data.current_round

    // 串行获取单词详情，避免并发请求过多导致超时
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
  
  // Add keyboard shortcut for next word and round result dialog
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      if (showRoundResult.value) {
        // 统计结果对话框显示时，回车执行下一步
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

// Auto focus input when userInput changes
watch(userInput, () => {
  if (!answerSubmitted.value) {
    focusInput()
  }
})
</script>

<style scoped>
.study-container {
  max-width: 700px;
  margin: 0 auto;
  padding: 20px;
  min-height: calc(100vh - 100px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.word-card {
  width: 100%;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.word-card :deep(.el-card__header) {
  border-bottom: 1px solid #ebeef5;
  padding: 20px;
}

.word-card :deep(.el-card__body) {
  padding: 40px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section {
  flex: 1;
  text-align: center;
}

.title-section h2 {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.progress-bar {
  width: 300px;
  height: 4px;
  background-color: #e4e7ed;
  border-radius: 2px;
  margin: 0 auto 8px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #409EFF, #66b1ff);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

.placeholder {
  width: 32px;
}

.word-content {
  text-align: center;
  margin-bottom: 40px;
}

.meaning {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
  line-height: 1.4;
}

.phonetic {
  font-size: 18px;
  color: #606266;
  margin-bottom: 30px;
  font-family: 'Times New Roman', serif;
}

.pronunciation-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.sound-btn {
  width: 64px;
  height: 64px;
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
}

.sound-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.4);
}

.sound-btn.playing {
  animation: pulse 1s infinite;
  background: linear-gradient(135deg, #67c23a, #85ce61);
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3);
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

.sound-hint {
  font-size: 13px;
  color: #909399;
}

.input-section {
  margin-top: 30px;
  text-align: center;
}

/* 打字效果显示区域 */
.typing-display {
  min-height: 60px;
  padding: 12px 20px;
  margin-bottom: 16px;
  background-color: #f5f7fa;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  cursor: text;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Courier New', monospace;
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  letter-spacing: 2px;
  transition: all 0.3s ease;
}

.typing-display:hover {
  border-color: #c0c4cc;
  background-color: #f9fafc;
}

.typing-display:focus-within {
  border-color: #409EFF;
  background-color: #fff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.1);
}

.typed-text {
  min-height: 32px;
}

/* 光标样式 */
.cursor {
  color: #409EFF;
  font-weight: 300;
  margin-left: 2px;
}

.cursor-blink {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% {
    opacity: 1;
  }
  51%, 100% {
    opacity: 0;
  }
}

/* 隐藏的实际输入框 */
.hidden-input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
  width: 0;
  height: 0;
}

.submit-area {
  margin-top: 16px;
}

.result-area {
  margin-top: 30px;
  text-align: center;
}

.result-box {
  padding: 24px;
  border-radius: 12px;
  margin-bottom: 20px;
  animation: slideIn 0.3s ease;
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

.result-box.correct {
  background-color: #f0f9eb;
  border: 1px solid #b3e19d;
}

.result-box.wrong {
  background-color: #fef0f0;
  border: 1px solid #fbc4c4;
}

.result-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 12px;
}

.result-text {
  font-size: 20px;
  font-weight: 600;
}

.result-box.correct .result-text {
  color: #67c23a;
}

.result-box.wrong .result-text {
  color: #f56c6c;
}

/* 答案对比区域样式 */
.answer-comparison {
  margin-top: 20px;
  padding: 20px 40px;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
  display: inline-block;
}

.answer-row {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 20px;
  margin: 12px 0;
  font-size: 18px;
}

.answer-label {
  min-width: 80px;
  text-align: left;
  color: #909399;
  font-size: 14px;
  font-weight: 500;
}

.answer-value {
  min-width: 150px;
  text-align: left;
  font-family: 'Courier New', monospace;
  font-size: 24px;
  font-weight: 700;
  padding: 8px 16px;
  border-radius: 6px;
  background-color: #f5f7fa;
  border: 2px solid transparent;
  letter-spacing: 1px;
}

.answer-value.user-answer {
  border-color: currentColor;
}

.correct-text {
  color: #67c23a;
}

.wrong-text {
  color: #f56c6c;
}

.next-btn {
  min-width: 120px;
  height: 44px;
  font-size: 16px;
}

.keyboard-hint {
  margin-top: 16px;
  color: #909399;
  font-size: 13px;
}

.round-result {
  text-align: center;
  padding: 20px 0;
}

.round-result .el-icon {
  margin-bottom: 16px;
}

.correct-icon {
  color: #67c23a;
}

.warning-icon {
  color: #e6a23c;
}

.result-message {
  font-size: 16px;
  color: #606266;
  margin-bottom: 20px;
}

.round-stats {
  display: flex;
  justify-content: center;
  gap: 30px;
  margin-top: 20px;
}
</style>
