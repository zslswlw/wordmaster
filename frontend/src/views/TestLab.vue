<template>
  <div v-if="ready" class="test-lab">
    <header class="page-head">
      <div>
        <h2>时间实验室</h2>
        <p>独立测试数据 · {{ clock.timezone }}</p>
      </div>
      <el-tag type="warning" effect="plain">测试模式</el-tag>
    </header>

    <section class="time-band">
      <div class="time-readout">
        <span class="date">{{ displayDate }}</span>
        <span class="time">{{ displayTime }}</span>
      </div>
      <div class="time-controls">
        <el-date-picker
          v-model="selectedTime"
          type="datetime"
          format="YYYY-MM-DD HH:mm"
          value-format="YYYY-MM-DDTHH:mm:ss"
          placeholder="设置模拟时间"
        />
        <el-button type="primary" :icon="Check" :loading="working" @click="applyTime">应用</el-button>
        <el-button :icon="RefreshLeft" :loading="working" @click="resetTime">恢复当前时间</el-button>
      </div>
      <div class="jump-controls">
        <el-button :icon="Plus" @click="advance(0, 2)">前进 2 分钟</el-button>
        <el-button :icon="Calendar" @click="advance(1)">前进 1 天</el-button>
        <el-button :icon="DArrowRight" @click="jumpToNextReview">跳到下一复习日</el-button>
      </div>
    </section>

    <section class="scenario-band">
      <div class="section-title">
        <h3>复现场景</h3>
        <span>载入场景会重置当前测试用户的数据</span>
      </div>
      <div class="scenario-list">
        <button
          v-for="item in scenarios"
          :key="item.value"
          class="scenario-row"
          :class="{ active: activeScenario === item.value }"
          :disabled="working"
          @click="loadScenario(item.value)"
        >
          <span class="scenario-name">{{ item.label }}</span>
          <span class="scenario-desc">{{ item.description }}</span>
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>
    </section>

    <section class="state-band">
      <div class="section-title">
        <h3>当前复习状态</h3>
        <el-button text :icon="Refresh" @click="refreshPlans">刷新</el-button>
      </div>
      <el-empty v-if="plans.length === 0" description="当前没有复习计划" :image-size="64" />
      <div v-else class="plan-table">
        <div class="plan-row plan-head">
          <span>轮次</span><span>计划日期</span><span>状态</span><span>可复习</span>
        </div>
        <div v-for="plan in plans" :key="plan.plan_id" class="plan-row">
          <span>第 {{ plan.review_round }} 轮</span>
          <span>{{ plan.review_date }}</span>
          <el-tag :type="planTag(plan)" size="small">{{ planText(plan) }}</el-tag>
          <span>{{ plan.can_review ? '是' : plan.blocked_by_plan_id ? '等待前序轮次' : '否' }}</span>
        </div>
      </div>
    </section>

    <footer v-if="scenarioGroupId" class="action-bar">
      <span>测试学习组 #{{ scenarioGroupId }}</span>
      <el-button type="primary" @click="openGroup">{{ openGroupLabel }}</el-button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowRight,
  Calendar,
  Check,
  DArrowRight,
  Plus,
  Refresh,
  RefreshLeft,
} from '@element-plus/icons-vue'
import { reviewAPI, systemAPI, testAPI } from '../api'

type Scenario = 'fresh' | 'partial-round' | 'completed-day0' | 'overdue-backlog' | 'ten-word-review'

const router = useRouter()
const ready = ref(false)
const working = ref(false)
const selectedTime = ref('')
const activeScenario = ref<Scenario | ''>('')
const scenarioGroupId = ref<number | null>(null)
const scenarioGroupStatus = ref('')
const plans = ref<any[]>([])
const clock = ref({ now: '', business_date: '', timezone: '' })

const scenarios: Array<{ value: Scenario; label: string; description: string }> = [
  { value: 'fresh', label: '全新三词组', description: '从第一轮开始检查完整学习流程' },
  { value: 'partial-round', label: '中途退出', description: '已有两词记录，验证恢复后只出现未答词' },
  { value: 'completed-day0', label: '刚完成强化', description: '已生成五次复习计划，适合测试跨天' },
  { value: 'overdue-backlog', label: '积压 16 天', description: '四轮已逾期，验证按顺序逐轮解锁' },
  { value: 'ten-word-review', label: '10 词待复习', description: '今日应复习 10 词，验证少答一词也不能完成' },
]

const parsedNow = computed(() => clock.value.now ? new Date(clock.value.now) : null)
const displayDate = computed(() => parsedNow.value?.toLocaleDateString('zh-CN', {
  year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short',
}) || '--')
const displayTime = computed(() => parsedNow.value?.toLocaleTimeString('zh-CN', {
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
}) || '--')
const openGroupLabel = computed(() => scenarioGroupStatus.value === 'completed'
  ? '打开可复习轮次'
  : '打开学习组')

const refreshClock = async () => {
  const { data } = await testAPI.getClock()
  clock.value = data
  selectedTime.value = data.now.slice(0, 19)
}

const refreshPlans = async () => {
  const { data } = await reviewAPI.getAllPlans()
  plans.value = Array.isArray(data) ? data : []
}

const applyTime = async () => {
  if (!selectedTime.value) return
  working.value = true
  try {
    await testAPI.setClock(selectedTime.value)
    await Promise.all([refreshClock(), refreshPlans()])
  } finally { working.value = false }
}

const resetTime = async () => {
  working.value = true
  try {
    await testAPI.resetClock()
    await Promise.all([refreshClock(), refreshPlans()])
  } finally { working.value = false }
}

const advance = async (days: number, minutes: number = 0) => {
  working.value = true
  try {
    await testAPI.advanceClock(days, minutes)
    await Promise.all([refreshClock(), refreshPlans()])
  } finally { working.value = false }
}

const jumpToNextReview = async () => {
  const pending = plans.value
    .filter((plan: any) => plan.status === 'pending' && plan.is_future)
    .sort((a: any, b: any) => a.review_date.localeCompare(b.review_date))[0]
  if (!pending) {
    ElMessage.info('没有未来的复习计划')
    return
  }
  selectedTime.value = `${pending.review_date}T09:00:00`
  await applyTime()
}

const loadScenario = async (scenario: Scenario) => {
  working.value = true
  try {
    const { data } = await testAPI.loadScenario(scenario)
    activeScenario.value = scenario
    scenarioGroupId.value = data.group_id
    scenarioGroupStatus.value = data.group_status
    await refreshPlans()
    ElMessage.success('测试场景已载入')
  } finally { working.value = false }
}

const openGroup = () => {
  if (!scenarioGroupId.value) return
  if (scenarioGroupStatus.value === 'completed') {
    const available = plans.value.find((plan: any) =>
      plan.group_id === scenarioGroupId.value && plan.can_review)
    if (available) {
      router.push(`/study/${scenarioGroupId.value}?planId=${available.plan_id}&isReview=true`)
    } else {
      ElMessage.info('当前还没有到期的复习轮次')
    }
    return
  }
  router.push(`/study/${scenarioGroupId.value}`)
}

const planTag = (plan: any) => plan.status === 'completed'
  ? 'success'
  : plan.is_overdue
    ? 'danger'
    : plan.is_today
      ? 'warning'
      : 'info'
const planText = (plan: any) => plan.status === 'completed'
  ? '已完成'
  : plan.is_overdue
    ? `逾期 ${plan.overdue_days} 天`
    : plan.is_today
      ? '今日'
      : '等待'

onMounted(async () => {
  try {
    const { data } = await systemAPI.health()
    if (!data.test_mode) {
      ElMessage.warning('时间实验室仅在测试模式开放')
      router.replace('/dashboard')
      return
    }
    await Promise.all([refreshClock(), refreshPlans()])
    ready.value = true
  } catch {
    ElMessage.error('测试环境未就绪')
    router.replace('/dashboard')
  }
})
</script>

<style scoped lang="scss">
.test-lab { max-width: 900px; margin: 0 auto; color: var(--color-text-primary); }
.page-head {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px;
  h2 { font-size: 1.125rem; margin: 0; }
  p { margin: 2px 0 0; color: var(--color-text-muted); font-size: 0.8125rem; }
}
.time-band, .scenario-band, .state-band {
  border-top: 1px solid var(--color-border); padding: 20px 0;
}
.time-readout {
  display: flex; align-items: baseline; gap: 14px; margin-bottom: 16px;
  .date { font-size: 1rem; color: var(--color-text-secondary); }
  .time { font-family: var(--font-mono); font-size: 2rem; font-weight: 650; }
}
.time-controls, .jump-controls { display: flex; flex-wrap: wrap; gap: 8px; }
.jump-controls { margin-top: 10px; }
.section-title {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;
  h3 { font-size: 0.9375rem; margin: 0; }
  span { font-size: 0.75rem; color: var(--color-text-muted); }
}
.scenario-list { border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }
.scenario-row {
  width: 100%; min-height: 58px; display: grid; grid-template-columns: 150px 1fr 20px;
  align-items: center; gap: 12px; padding: 10px 14px; border: 0;
  border-bottom: 1px solid var(--color-border-light); background: var(--color-bg-paper);
  text-align: left; cursor: pointer; color: inherit;
  &:last-child { border-bottom: 0; }
  &:hover, &.active { background: var(--color-bg-muted); }
  &:disabled { cursor: wait; opacity: 0.6; }
}
.scenario-name { font-weight: 600; font-size: 0.875rem; }
.scenario-desc { font-size: 0.8125rem; color: var(--color-text-muted); }
.plan-table { border-top: 1px solid var(--color-border); }
.plan-row {
  display: grid; grid-template-columns: 100px 1fr 120px 130px; align-items: center;
  min-height: 44px; border-bottom: 1px solid var(--color-border-light); font-size: 0.8125rem;
}
.plan-head { color: var(--color-text-muted); font-size: 0.75rem; }
.action-bar {
  position: sticky; bottom: 0; display: flex; align-items: center; justify-content: space-between;
  padding: 12px 0; background: var(--color-bg-base); border-top: 1px solid var(--color-border);
  span { font-size: 0.8125rem; color: var(--color-text-muted); }
}
@media (max-width: 640px) {
  .time-controls { flex-direction: column; align-items: stretch; }
  .scenario-row { grid-template-columns: 1fr 20px; }
  .scenario-desc { grid-column: 1; }
  .plan-row { grid-template-columns: 72px 1fr 92px; }
  .plan-row > :last-child { display: none; }
  .time-readout { flex-direction: column; gap: 2px; }
  .time-readout .time { font-size: 1.625rem; }
}
</style>
