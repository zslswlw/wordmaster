<template>
  <div class="review-container" :class="{ mobile: isMobile }">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button @click="goBack" circle :size="isMobile ? 'small' : 'default'">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <span class="title">复习计划</span>
          </div>
          <div class="header-tabs">
            <el-radio-group v-model="activeTab" :size="isMobile ? 'small' : 'small'">
              <el-radio-button value="today">今日</el-radio-button>
              <el-radio-button value="all">全部</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>
      
      <!-- 今日复习计划 -->
      <div v-if="activeTab === 'today'">
        <div v-if="todayPlans.length === 0" class="empty-state">
          <el-empty description="今日暂无复习计划">
            <template #description>
              <div class="empty-description">
                <p>今日暂无复习计划</p>
                <p class="sub-text">完成新学单词后，系统会自动生成复习计划</p>
              </div>
            </template>
            <el-button type="primary" @click="goToGroups" :size="isMobile ? 'small' : 'default'">
              <el-icon><VideoPlay /></el-icon>
              去新学单词
            </el-button>
          </el-empty>
        </div>

        <!-- 桌面端时间线 -->
        <div v-else-if="!isMobile">
          <el-timeline>
            <el-timeline-item 
              v-for="plan in todayPlans" 
              :key="plan.plan_id"
              :timestamp="`第${plan.review_round}轮 - ${formatDate(plan.review_date)}`"
              placement="top"
            >
              <el-card>
                <h4>{{ plan.group_name }}</h4>
                <p class="plan-info">
                  <el-tag type="info" size="small">词库: {{ plan.bank_name }}</el-tag>
                  <el-tag type="info" size="small" style="margin-left: 8px;">范围: {{ plan.start_seq }}-{{ plan.end_seq }}</el-tag>
                </p>
                <div class="plan-actions">
                  <el-button 
                    type="primary" 
                    :disabled="!plan.can_review"
                    @click="startReview(plan)"
                  >
                    <el-icon><VideoPlay /></el-icon>
                    开始复习
                  </el-button>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </div>

        <!-- 移动端卡片列表 -->
        <div v-else class="mobile-plans-list">
          <div 
            v-for="plan in todayPlans" 
            :key="plan.plan_id"
            class="mobile-plan-card"
            :class="{ 'can-review': plan.can_review }"
          >
            <div class="plan-header">
              <div class="plan-round">第{{ plan.review_round }}轮</div>
              <el-tag v-if="plan.can_review" type="success" size="small" effect="dark">可复习</el-tag>
              <el-tag v-else type="info" size="small">待解锁</el-tag>
            </div>
            <h4 class="plan-group-name">{{ plan.group_name }}</h4>
            <div class="plan-meta">
              <span class="meta-item">
                <el-icon><Collection /></el-icon>
                {{ plan.bank_name }}
              </span>
              <span class="meta-item">
                <el-icon><Document /></el-icon>
                {{ plan.start_seq }}-{{ plan.end_seq }}
              </span>
            </div>
            <div class="plan-footer">
              <span class="plan-date">{{ formatDate(plan.review_date) }}</span>
              <el-button 
                type="primary" 
                size="small"
                :disabled="!plan.can_review"
                @click="startReview(plan)"
              >
                <el-icon><VideoPlay /></el-icon>
                开始
              </el-button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 全部复习计划 -->
      <div v-else>
        <div v-if="allPlans.length === 0" class="empty-state">
          <el-empty description="暂无复习计划">
            <template #description>
              <div class="empty-description">
                <p>暂无复习计划</p>
                <p class="sub-text">完成新学单词后，系统会自动生成复习计划</p>
              </div>
            </template>
            <el-button type="primary" @click="goToGroups" :size="isMobile ? 'small' : 'default'">
              <el-icon><VideoPlay /></el-icon>
              去新学单词
            </el-button>
          </el-empty>
        </div>

        <!-- 桌面端折叠面板 -->
        <div v-else-if="!isMobile">
          <el-collapse accordion>
            <el-collapse-item 
              v-for="dateGroup in groupedPlans" 
              :key="dateGroup.date"
            >
              <template #title>
                <span class="collapse-title">{{ formatDate(dateGroup.date) }} 
                  <el-tag size="small" style="margin-left: 8px;">{{ dateGroup.plans.length }} 个计划</el-tag>
                </span>
              </template>
              <el-timeline>
                <el-timeline-item 
                  v-for="plan in dateGroup.plans" 
                  :key="plan.plan_id"
                  :timestamp="`第${plan.review_round}轮 - ${plan.group_name}`"
                  placement="top"
                  :type="getStatusType(plan)"
                >
                  <el-card>
                    <h4>{{ plan.group_name }}</h4>
                    <p class="plan-info">
                      <el-tag type="info" size="small">词库: {{ plan.bank_name }}</el-tag>
                      <el-tag type="info" size="small" style="margin-left: 8px;">范围: {{ plan.start_seq }}-{{ plan.end_seq }}</el-tag>
                      <el-tag :type="getStatusTagType(plan)" size="small" style="margin-left: 8px;">{{ getStatusText(plan) }}</el-tag>
                    </p>
                    <div class="plan-actions">
                      <el-button 
                        type="primary" 
                        :disabled="!plan.can_review"
                        @click="startReview(plan)"
                      >
                        <el-icon><VideoPlay /></el-icon>
                        {{ plan.can_review ? '开始复习' : '不可复习' }}
                      </el-button>
                    </div>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 移动端全部计划列表 -->
        <div v-else class="mobile-all-plans">
          <div 
            v-for="dateGroup in groupedPlans" 
            :key="dateGroup.date"
            class="date-section"
          >
            <div class="date-header">
              <span class="date-title">{{ formatDate(dateGroup.date) }}</span>
              <el-tag size="small">{{ dateGroup.plans.length }} 个</el-tag>
            </div>
            <div class="date-plans">
              <div 
                v-for="plan in dateGroup.plans" 
                :key="plan.plan_id"
                class="mobile-plan-card"
                :class="{ 
                  'can-review': plan.can_review,
                  'completed': plan.status === 'completed',
                  'overdue': plan.is_overdue && plan.status !== 'completed'
                }"
              >
                <div class="plan-header">
                  <div class="plan-round">第{{ plan.review_round }}轮</div>
                  <el-tag :type="getStatusTagType(plan)" size="small" effect="dark">
                    {{ getStatusText(plan) }}
                  </el-tag>
                </div>
                <h4 class="plan-group-name">{{ plan.group_name }}</h4>
                <div class="plan-meta">
                  <span class="meta-item">
                    <el-icon><Collection /></el-icon>
                    {{ plan.bank_name }}
                  </span>
                  <span class="meta-item">
                    <el-icon><Document /></el-icon>
                    {{ plan.start_seq }}-{{ plan.end_seq }}
                  </span>
                </div>
                <div class="plan-footer">
                  <el-button 
                    type="primary" 
                    size="small"
                    :disabled="!plan.can_review"
                    @click="startReview(plan)"
                  >
                    <el-icon><VideoPlay /></el-icon>
                    {{ plan.can_review ? '开始' : '锁定' }}
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { reviewAPI } from '../api'
import { ArrowLeft, VideoPlay, Refresh, Collection, Document } from '@element-plus/icons-vue'

// 响应式检测
const isMobile = ref(window.innerWidth <= 768)
const handleResize = () => {
  isMobile.value = window.innerWidth <= 768
}
onMounted(() => {
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

interface ReviewPlan {
  plan_id: number;
  group_id: number;
  group_name: string;
  bank_name: string;
  review_round: number;
  review_date: string;
  start_seq: number;
  end_seq: number;
  status: string;
  is_today: boolean;
  is_overdue: boolean;
  is_future: boolean;
  can_review: boolean;
}

const router = useRouter()
const activeTab = ref('today')
const todayPlans = ref<ReviewPlan[]>([])
const allPlans = ref<ReviewPlan[]>([])

const overduePlans = computed(() => {
  const plans = Array.isArray(allPlans.value) ? allPlans.value : []
  return plans.filter(plan => plan.is_overdue && plan.status !== 'completed')
})

const groupedPlans = computed(() => {
  const groups: { date: string; plans: ReviewPlan[] }[] = []
  const plans = Array.isArray(allPlans.value) ? allPlans.value : []
  const dates = [...new Set(plans.map(p => p.review_date))]
  
  dates.forEach(date => {
    const datePlans = plans.filter(p => p.review_date === date)
    groups.push({ date, plans: datePlans })
  })
  
  // Sort by date
  groups.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  
  return groups
})

const goBack = () => {
  router.go(-1)
}

const goToGroups = () => {
  router.push('/groups')
}

const startReview = (plan: ReviewPlan) => {
  if (!plan.can_review) {
    ElMessage.warning('该计划还不能复习')
    return
  }
  
  // 使用查询参数传递 planId 和 isReview，与学习组页面的复习跳转保持一致
  router.push(`/study/${plan.group_id}?planId=${plan.plan_id}&isReview=true`)
}

const getStatusType = (plan: ReviewPlan) => {
  if (plan.is_overdue) return 'danger'
  if (plan.is_today) return 'primary'
  return 'info'
}

const getStatusTagType = (plan: ReviewPlan) => {
  if (plan.status === 'completed') return 'success'
  if (plan.is_overdue) return 'danger'
  if (plan.is_today) return 'warning'
  return 'info'
}

const getStatusText = (plan: ReviewPlan) => {
  if (plan.status === 'completed') return '已完成'
  if (plan.is_overdue) return '逾期'
  if (plan.is_today) return '今日'
  if (plan.is_future) return '未来'
  return '待复习'
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

const loadTodayPlans = async () => {
  try {
    const response = await reviewAPI.getTodayPlans()
    todayPlans.value = Array.isArray(response.data) ? response.data : []
  } catch (error) {
    ElMessage.error('加载今日复习计划失败')
    todayPlans.value = []
  }
}

const loadAllPlans = async () => {
  try {
    const response = await reviewAPI.getAllPlans()
    allPlans.value = Array.isArray(response.data) ? response.data : []
  } catch (error) {
    ElMessage.error('加载全部复习计划失败')
    allPlans.value = []
  }
}

onMounted(() => {
  loadTodayPlans()
  loadAllPlans()
})
</script>

<style scoped>
.review-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

.review-container.mobile {
  padding: 12px;
  max-width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.review-container.mobile .card-header {
  padding: 4px 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.review-container.mobile .header-left {
  gap: 8px;
}

.title {
  font-size: 18px;
  font-weight: bold;
}

.review-container.mobile .title {
  font-size: 16px;
}

.header-tabs {
  margin-right: 20px;
}

.plan-info {
  margin: 12px 0;
}

.plan-actions {
  margin-top: 16px;
  text-align: right;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
}

.review-container.mobile .empty-state {
  padding: 30px 0;
}

.empty-description p {
  margin: 8px 0;
}

.sub-text {
  color: #909399;
  font-size: 14px;
}

.collapse-title {
  font-weight: bold;
  font-size: 16px;
}

/* 移动端计划卡片样式 */
.mobile-plans-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-plan-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border: 1px solid #ebeef5;
  transition: all 0.3s ease;
}

.mobile-plan-card.can-review {
  border-left: 4px solid #67c23a;
  background: linear-gradient(to right, #f0f9ff, #fff);
}

.mobile-plan-card.completed {
  border-left: 4px solid #909399;
  opacity: 0.8;
}

.mobile-plan-card.overdue {
  border-left: 4px solid #f56c6c;
  background: linear-gradient(to right, #fef0f0, #fff);
}

.plan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.plan-round {
  font-size: 13px;
  color: #606266;
  background: #f5f7fa;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.mobile-plan-card.can-review .plan-round {
  background: #e1f3d8;
  color: #67c23a;
}

.plan-group-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 12px 0;
  line-height: 1.4;
}

.plan-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}

.meta-item .el-icon {
  font-size: 14px;
  color: #909399;
}

.plan-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.plan-date {
  font-size: 13px;
  color: #909399;
}

/* 移动端全部计划 */
.mobile-all-plans {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.date-section {
  background: #f5f7fa;
  border-radius: 12px;
  padding: 16px;
}

.date-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e4e7ed;
}

.date-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.date-plans {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.date-plans .mobile-plan-card {
  margin: 0;
}

/* 横屏适配 */
@media (min-width: 569px) and (max-width: 896px) and (orientation: landscape) {
  .mobile-plans-list {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  
  .date-plans {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
}

/* 小屏幕手机适配 */
@media (max-width: 375px) {
  .review-container.mobile {
    padding: 8px;
  }
  
  .mobile-plan-card {
    padding: 12px;
  }
  
  .plan-group-name {
    font-size: 15px;
  }
  
  .plan-meta {
    gap: 6px;
  }
}
</style>