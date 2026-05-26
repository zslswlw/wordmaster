<template>
  <div class="dashboard-container">
    <!-- 欢迎区域 -->
    <div class="welcome-section animate-fade-in-up">
      <div class="welcome-content">
        <h1 class="welcome-title">你好，{{ username }} 👋</h1>
        <p class="welcome-subtitle">今天也要坚持学习哦，保持进步！</p>
      </div>
      <div class="welcome-date">
        <div class="date-badge">
          <span class="date-day">{{ currentDay }}</span>
          <span class="date-month">{{ currentMonth }}</span>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <div class="stat-card animate-fade-in-up delay-1">
          <div class="stat-icon" style="--accent-color: var(--color-primary);">
            <el-icon :size="isMobile ? 22 : 28"><Collection /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.banks }}</div>
            <div class="stat-label">词库</div>
          </div>
          <div class="stat-decoration"></div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <div class="stat-card animate-fade-in-up delay-2">
          <div class="stat-icon" style="--accent-color: var(--color-success);">
            <el-icon :size="isMobile ? 22 : 28"><FolderOpened /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.groups }}</div>
            <div class="stat-label">学习组</div>
          </div>
          <div class="stat-decoration"></div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <div class="stat-card animate-fade-in-up delay-3">
          <div class="stat-icon" style="--accent-color: var(--color-warning);">
            <el-icon :size="isMobile ? 22 : 28"><Calendar /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.todayReview }}</div>
            <div class="stat-label">今日复习</div>
          </div>
          <div class="stat-decoration"></div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <div class="stat-card animate-fade-in-up delay-4">
          <div class="stat-icon" style="--accent-color: var(--color-accent);">
            <el-icon :size="isMobile ? 22 : 28"><Trophy /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.completed }}</div>
            <div class="stat-label">已完成</div>
          </div>
          <div class="stat-decoration"></div>
        </div>
      </el-col>
    </el-row>

    <!-- 快速操作 -->
    <div class="section-card animate-fade-in-up delay-2">
      <div class="section-header">
        <h3 class="section-title">
          <el-icon><Lightning /></el-icon>
          快速开始
        </h3>
      </div>
      <div class="quick-actions">
        <div class="action-item" @click="goToBanks">
          <div class="action-icon" style="--bg-color: rgba(var(--color-primary-rgb), 0.1);">
            <el-icon :size="isMobile ? 24 : 32" color="var(--color-primary)"><Plus /></el-icon>
          </div>
          <div class="action-text">
            <span class="action-title">导入词库</span>
            <span class="action-desc">添加新单词</span>
          </div>
          <el-icon class="action-arrow"><ArrowRight /></el-icon>
        </div>
        <div class="action-item" @click="goToGroups">
          <div class="action-icon" style="--bg-color: rgba(45, 138, 94, 0.1);">
            <el-icon :size="isMobile ? 24 : 32" color="var(--color-success)"><VideoPlay /></el-icon>
          </div>
          <div class="action-text">
            <span class="action-title">开始学习</span>
            <span class="action-desc">创建学习组</span>
          </div>
          <el-icon class="action-arrow"><ArrowRight /></el-icon>
        </div>
        <div class="action-item" @click="goToReview">
          <div class="action-icon" style="--bg-color: rgba(212, 134, 12, 0.1);">
            <el-icon :size="isMobile ? 24 : 32" color="var(--color-warning)"><RefreshRight /></el-icon>
          </div>
          <div class="action-text">
            <span class="action-title">今日复习</span>
            <span class="action-desc">查看计划</span>
          </div>
          <el-icon class="action-arrow"><ArrowRight /></el-icon>
        </div>
        <div class="action-item" @click="goToBackup">
          <div class="action-icon" style="--bg-color: rgba(196, 84, 74, 0.1);">
            <el-icon :size="isMobile ? 24 : 32" color="var(--color-danger)"><Download /></el-icon>
          </div>
          <div class="action-text">
            <span class="action-title">数据备份</span>
            <span class="action-desc">备份数据</span>
          </div>
          <el-icon class="action-arrow"><ArrowRight /></el-icon>
        </div>
      </div>
    </div>

    <!-- 学习提示 -->
    <el-row :gutter="16" class="info-row">
      <el-col :xs="24" :sm="24" :md="12">
        <div class="section-card animate-fade-in-up delay-3">
          <div class="section-header">
            <h3 class="section-title">
              <el-icon><InfoFilled /></el-icon>
              学习提示
            </h3>
          </div>
          <div class="tips-list">
            <div class="tip-item">
              <div class="tip-icon primary"><el-icon><Aim /></el-icon></div>
              <span>建议每天学习20-50个新单词</span>
            </div>
            <div class="tip-item">
              <div class="tip-icon success"><el-icon><Timer /></el-icon></div>
              <span>按照艾宾浩斯遗忘曲线复习</span>
            </div>
            <div class="tip-item">
              <div class="tip-icon warning"><el-icon><Headset /></el-icon></div>
              <span>听写时认真听发音，多练习</span>
            </div>
            <div class="tip-item">
              <div class="tip-icon danger"><el-icon><Warning /></el-icon></div>
              <span>定期备份数据防止丢失</span>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="24" :md="12">
        <div class="section-card animate-fade-in-up delay-4">
          <div class="section-header">
            <h3 class="section-title">
              <el-icon><Guide /></el-icon>
              学习流程
            </h3>
          </div>
          <div class="steps-list">
            <div class="step-item">
              <div class="step-number">1</div>
              <div class="step-content">
                <span class="step-title">导入词库</span>
                <span class="step-desc">上传CSV格式的单词文件</span>
              </div>
            </div>
            <div class="step-item">
              <div class="step-number">2</div>
              <div class="step-content">
                <span class="step-title">创建学习组</span>
                <span class="step-desc">选择学习范围和单词数量</span>
              </div>
            </div>
            <div class="step-item">
              <div class="step-number">3</div>
              <div class="step-content">
                <span class="step-title">开始学习</span>
                <span class="step-desc">听写单词，系统自动判定</span>
              </div>
            </div>
            <div class="step-item">
              <div class="step-number">4</div>
              <div class="step-content">
                <span class="step-title">复习巩固</span>
                <span class="step-desc">按记忆曲线自动安排复习</span>
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { bankAPI, groupAPI, reviewAPI } from '../api'
import { useResponsive } from '../composables/useResponsive'
import {
  Collection,
  FolderOpened,
  Calendar,
  Trophy,
  Plus,
  VideoPlay,
  RefreshRight,
  Download,
  InfoFilled,
  Lightning,
  ArrowRight,
  Aim,
  Timer,
  Headset,
  Warning,
  Guide
} from '@element-plus/icons-vue'

const router = useRouter()
const { isMobile } = useResponsive()

const username = ref('')

const stats = ref({
  banks: 0,
  groups: 0,
  todayReview: 0,
  completed: 0
})

const currentDay = computed(() => {
  return new Date().getDate()
})

const currentMonth = computed(() => {
  const months = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月']
  return months[new Date().getMonth()]
})

onMounted(async () => {
  username.value = localStorage.getItem('username') || '学习者'
  await loadStats()
})

const loadStats = async () => {
  try {
    const [banksRes, groupsRes, reviewRes] = await Promise.all([
      bankAPI.getAll(),
      groupAPI.getAll(),
      reviewAPI.getToday()
    ])

    const banks = Array.isArray(banksRes.data) ? banksRes.data : []
    const groups = Array.isArray(groupsRes.data) ? groupsRes.data : []
    const reviews = Array.isArray(reviewRes.data) ? reviewRes.data : []

    stats.value.banks = banks.length
    stats.value.groups = groups.length
    stats.value.todayReview = reviews.length
    stats.value.completed = groups.filter((g: any) => g.status === 'completed').length
  } catch (error) {
    console.error('加载统计数据失败', error)
  }
}

const goToBanks = () => router.push('/banks')
const goToGroups = () => router.push('/groups')
const goToReview = () => router.push('/review')
const goToBackup = () => router.push('/backup')
</script>

<style scoped lang="scss">
.dashboard-container {
  max-width: 1200px;
  margin: 0 auto;
}

/* 欢迎区域 */
.welcome-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 24px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border-radius: var(--radius-xl);
  color: white;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    width: 300px;
    height: 100%;
    background: linear-gradient(135deg, transparent 0%, rgba(255, 255, 255, 0.1) 100%);
    pointer-events: none;
  }

  &::after {
    content: '';
    position: absolute;
    bottom: -50%;
    right: -10%;
    width: 200px;
    height: 200px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 50%;
  }
}

.welcome-content {
  position: relative;
  z-index: 1;
}

.welcome-title {
  font-family: var(--font-display);
  font-size: 1.75rem;
  font-weight: 600;
  margin-bottom: 4px;
  color: white;
}

.welcome-subtitle {
  font-size: 0.9375rem;
  opacity: 0.9;
  color: rgba(255, 255, 255, 0.9);
}

.welcome-date {
  position: relative;
  z-index: 1;
}

.date-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.date-day {
  font-family: var(--font-display);
  font-size: 2rem;
  font-weight: 700;
  line-height: 1;
  color: white;
}

.date-month {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 2px;
}

/* 统计卡片 */
.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  background: var(--color-bg-paper);
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-border-light);
  transition: all var(--transition-base);

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-md);
  background: var(--bg-color);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-color);
  flex-shrink: 0;
  background: var(--accent-color);
  opacity: 0.9;
  color: white;
  box-shadow: 0 4px 12px color-mix(in srgb, var(--accent-color) 30%, transparent);
}

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-family: var(--font-display);
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.stat-decoration {
  position: absolute;
  top: 0;
  right: 0;
  width: 80px;
  height: 80px;
  background: var(--accent-color);
  opacity: 0.03;
  border-radius: 0 0 0 80px;
}

/* 通用卡片样式 */
.section-card {
  background: var(--color-bg-paper);
  border-radius: var(--radius-lg);
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-border-light);
}

.section-header {
  margin-bottom: 16px;
}

.section-title {
  font-family: var(--font-display);
  font-size: 1.0625rem;
  font-weight: 600;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 8px;

  .el-icon {
    color: var(--color-primary);
  }
}

/* 快速操作 */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 12px;
  background: var(--color-bg-muted);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-base);
  position: relative;

  &:hover {
    background: var(--color-bg-base);
    transform: translateY(-2px);

    .action-arrow {
      opacity: 1;
      transform: translateX(0);
    }
  }
}

.action-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  background: var(--bg-color);
}

.action-text {
  text-align: center;
}

.action-title {
  display: block;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 2px;
}

.action-desc {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.action-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%) translateX(-8px);
  color: var(--color-text-light);
  opacity: 0;
  transition: all var(--transition-fast);
  font-size: 14px;
}

/* 提示列表 */
.tips-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tip-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-muted);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  color: var(--color-text-secondary);
  transition: background var(--transition-fast);

  &:hover {
    background: var(--color-bg-base);
  }
}

.tip-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;

  &.primary {
    background: rgba(var(--color-primary-rgb), 0.1);
    color: var(--color-primary);
  }

  &.success {
    background: rgba(45, 138, 94, 0.1);
    color: var(--color-success);
  }

  &.warning {
    background: rgba(212, 134, 12, 0.1);
    color: var(--color-warning);
  }

  &.danger {
    background: rgba(196, 84, 74, 0.1);
    color: var(--color-danger);
  }
}

/* 步骤列表 */
.steps-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
  background: var(--color-bg-muted);
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);

  &:hover {
    background: var(--color-bg-base);
  }
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: 600;
  flex-shrink: 0;
}

.step-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.step-title {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--color-text-primary);
}

.step-desc {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

/* 移动端适配 */
@media (max-width: 768px) {
  .welcome-section {
    padding: 20px;
    margin-bottom: 16px;
  }

  .welcome-title {
    font-size: 1.375rem;
  }

  .date-badge {
    padding: 10px 16px;
  }

  .date-day {
    font-size: 1.5rem;
  }

  .stats-row {
    margin-bottom: 12px;
  }

  .stat-card {
    padding: 16px;
  }

  .stat-icon {
    width: 44px;
    height: 44px;
  }

  .stat-value {
    font-size: 1.5rem;
  }

  .quick-actions {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .action-item {
    padding: 16px 10px;
  }

  .action-icon {
    width: 48px;
    height: 48px;
    margin-bottom: 10px;
  }

  .action-arrow {
    display: none;
  }

  .section-card {
    padding: 16px;
    margin-bottom: 12px;
  }
}

/* 横屏适配 */
@media (orientation: landscape) and (max-width: 1024px) {
  .stat-card {
    padding: 12px;
  }

  .stat-icon {
    width: 40px;
    height: 40px;
  }

  .stat-value {
    font-size: 1.375rem;
  }
}
</style>
