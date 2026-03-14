<template>
  <div class="review-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button @click="goBack" circle>
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <span class="title">复习计划</span>
          </div>
          <div class="header-tabs">
            <el-radio-group v-model="activeTab" size="small">
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
            <el-button type="primary" @click="goToGroups">
              <el-icon><VideoPlay /></el-icon>
              去新学单词
            </el-button>
          </el-empty>
        </div>

        <div v-else>
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
            <el-button type="primary" @click="goToGroups">
              <el-icon><VideoPlay /></el-icon>
              去新学单词
            </el-button>
          </el-empty>
        </div>

        <div v-else>
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
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { reviewAPI } from '../api'
import { ArrowLeft, VideoPlay, Refresh } from '@element-plus/icons-vue'

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
  return allPlans.value.filter(plan => plan.is_overdue && plan.status !== 'completed')
})

const groupedPlans = computed(() => {
  const groups: { date: string; plans: ReviewPlan[] }[] = []
  const dates = [...new Set(allPlans.value.map(p => p.review_date))]
  
  dates.forEach(date => {
    const plans = allPlans.value.filter(p => p.review_date === date)
    groups.push({ date, plans })
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
  
  localStorage.setItem('reviewPlanId', plan.plan_id.toString())
  router.push(`/study/${plan.group_id}`)
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
    todayPlans.value = response.data
  } catch (error) {
    ElMessage.error('加载今日复习计划失败')
  }
}

const loadAllPlans = async () => {
  try {
    const response = await reviewAPI.getAllPlans()
    allPlans.value = response.data
  } catch (error) {
    ElMessage.error('加载全部复习计划失败')
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 18px;
  font-weight: bold;
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
</style>