<template>
  <div class="page">
    <div class="page-top">
      <h2>复习计划</h2>
      <el-radio-group v-model="tab" size="small">
        <el-radio-button value="today">今日</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 今日 -->
    <template v-if="tab === 'today'">
      <div v-if="todayPlans.length === 0" class="empty">
        <p>今日暂无复习计划</p>
        <p class="sub">完成新学单词后，系统会自动生成复习计划</p>
      </div>
      <div v-else class="plans">
        <div v-for="p in todayPlans" :key="p.plan_id" class="plan-row" :class="{ revivable: p.can_review }">
          <div class="plan-info">
            <span class="plan-round">第{{ p.review_round }}轮</span>
            <span class="plan-name">{{ p.group_name }}</span>
          </div>
          <div class="plan-right">
            <el-tag v-if="p.is_overdue" type="danger" size="small">逾期 {{ p.overdue_days }} 天</el-tag>
            <el-tag v-else-if="p.blocked_by_plan_id" type="info" size="small">等待前序轮次</el-tag>
            <span class="plan-date">{{ fmt(p.review_date) }}</span>
            <el-button type="primary" size="small" :disabled="!p.can_review" @click="startReview(p)">开始</el-button>
          </div>
        </div>
      </div>
    </template>

    <!-- 全部 -->
    <template v-else>
      <div v-if="allPlans.length === 0" class="empty">
        <p>暂无复习计划</p>
      </div>
      <div v-else class="all-plans">
        <div v-for="dg in groupedPlans" :key="dg.date" class="date-block">
          <div class="date-head">{{ fmt(dg.date) }} <span class="count">{{ dg.plans.length }} 个</span></div>
          <div v-for="p in dg.plans" :key="p.plan_id" class="plan-row" :class="{ revivable: p.can_review, done: p.status === 'completed' }">
            <div class="plan-info">
              <span class="plan-round">第{{ p.review_round }}轮</span>
              <span class="plan-name">{{ p.group_name }}</span>
            </div>
            <div class="plan-right">
              <el-tag :type="tagType(p)" size="small">{{ tagText(p) }}</el-tag>
              <el-button type="primary" size="small" :disabled="!p.can_review" @click="startReview(p)">{{ p.can_review ? '复习' : p.blocked_by_plan_id ? '待前序' : '锁定' }}</el-button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { reviewAPI } from '../api'

const router = useRouter()
const tab = ref('today')
const todayPlans = ref<any[]>([])
const allPlans = ref<any[]>([])

interface Plan { plan_id: number; group_id: number; group_name: string; bank_name: string; review_round: number; review_date: string; start_seq: number; end_seq: number; status: string; is_today: boolean; is_overdue: boolean; overdue_days: number; is_future: boolean; can_review: boolean; blocked_by_plan_id: number | null }

const groupedPlans = computed(() => {
  const m = new Map<string, Plan[]>()
  for (const p of (Array.isArray(allPlans.value) ? allPlans.value : [])) {
    if (!m.has(p.review_date)) m.set(p.review_date, [])
    m.get(p.review_date)!.push(p)
  }
  return [...m.entries()].sort((a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime()).map(([date, plans]) => ({ date, plans }))
})

const startReview = (plan: Plan) => {
  if (!plan.can_review) { ElMessage.warning('该计划还不能复习'); return }
  router.push(`/study/${plan.group_id}?planId=${plan.plan_id}&isReview=true`)
}

const tagType = (p: Plan) => p.status === 'completed' ? 'success' : p.is_overdue ? 'danger' : p.is_today ? 'warning' : 'info'
const tagText = (p: Plan) => p.status === 'completed' ? '已完成' : p.is_overdue ? `逾期 ${p.overdue_days} 天` : p.blocked_by_plan_id ? '等待前序轮次' : p.is_today ? '今日' : '等待'

const fmt = (d: string) => {
  const [, month, day] = d.split('-').map(Number)
  return `${month}月${day}日`
}

onMounted(async () => {
  try { const r = await reviewAPI.getTodayPlans(); todayPlans.value = Array.isArray(r.data) ? r.data : [] } catch { todayPlans.value = [] }
  try { const r = await reviewAPI.getAllPlans(); allPlans.value = Array.isArray(r.data) ? r.data : [] } catch { allPlans.value = [] }
})
</script>

<style scoped lang="scss">
.page { max-width: 720px; margin: 0 auto; }
.page-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;
  h2 { font-size: 1.125rem; font-weight: 700; color: var(--color-text-primary); margin: 0; }
}

.empty { text-align: center; padding: 60px 0; p { color: var(--color-text-muted); margin: 0 0 4px; } .sub { font-size: 0.8125rem; } }

.plans { display: flex; flex-direction: column; gap: 1px; background: var(--color-border-light); border-radius: 8px; overflow: hidden; }
.plan-row {
  display: flex; justify-content: space-between; align-items: center; padding: 14px 16px;
  background: var(--color-bg-paper); gap: 12px;
  &.revivable { border-left: 3px solid var(--color-text-primary); }
  &.done { opacity: 0.5; }
}
.plan-info { display: flex; align-items: center; gap: 12px; min-width: 0; }
.plan-round { font-size: 0.75rem; color: var(--color-text-muted); flex-shrink: 0; }
.plan-name { font-size: 0.9375rem; font-weight: 500; color: var(--color-text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.plan-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.plan-date { font-size: 0.75rem; color: var(--color-text-muted); }

.all-plans { display: flex; flex-direction: column; gap: 20px; }
.date-block { }
.date-head { font-size: 0.8125rem; font-weight: 600; color: var(--color-text-muted); margin-bottom: 8px; .count { font-weight: 400; color: var(--color-text-light); } }
.date-block .plan-row { border-top: 1px solid var(--color-border-light); }
</style>
