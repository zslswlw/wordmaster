<template>
  <div class="dash">
    <div class="welcome">
      <div class="w-left">
        <h1>你好</h1>
        <p class="w-sub">今天也要坚持学习</p>
      </div>
      <div class="w-date">
        <span class="w-day">{{ day }}</span>
        <span class="w-month">{{ month }}</span>
      </div>
    </div>

    <div class="stat-row">
      <div class="stat" v-for="(s, i) in statItems" :key="i">
        <span class="s-val">{{ s.val }}</span>
        <span class="s-label">{{ s.label }}</span>
      </div>
    </div>

    <div class="section">
      <h3 class="sec-title">快速开始</h3>
      <div class="actions">
        <button class="act" v-for="a in actions" :key="a.label" @click="a.fn">
          <span class="act-icon"><el-icon><component :is="a.icon" /></el-icon></span>
          <span class="act-label">{{ a.label }}</span>
        </button>
      </div>
    </div>

    <div class="section">
      <h3 class="sec-title">学习流程</h3>
      <div class="steps">
        <div class="step" v-for="(st, i) in steps" :key="i">
          <span class="step-num">{{ i + 1 }}</span>
          <div class="step-text">
            <span class="step-title">{{ st.title }}</span>
            <span class="step-desc">{{ st.desc }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { bankAPI, groupAPI, reviewAPI } from '../api'
import { Plus, VideoPlay, RefreshRight, Download } from '@element-plus/icons-vue'

const router = useRouter()
const day = new Date().getDate()
const month = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'][new Date().getMonth()]

const statItems = ref([
  { val: 0, label: '词库' },
  { val: 0, label: '学习组' },
  { val: 0, label: '今日复习' },
  { val: 0, label: '已完成' },
])

const actions = [
  { label: '导入词库', icon: Plus, fn: () => router.push('/banks') },
  { label: '开始学习', icon: VideoPlay, fn: () => router.push('/groups') },
  { label: '今日复习', icon: RefreshRight, fn: () => router.push('/review') },
  { label: '数据备份', icon: Download, fn: () => router.push('/backup') },
]

const steps = [
  { title: '导入词库', desc: '上传CSV格式的单词文件' },
  { title: '创建学习组', desc: '选择学习范围和数量' },
  { title: '开始学习', desc: '听写单词，自动判定' },
  { title: '复习巩固', desc: '按记忆曲线自动安排' },
]

onMounted(async () => {
  try {
    const [banksRes, groupsRes, reviewRes] = await Promise.all([bankAPI.getAll(), groupAPI.getAll(), reviewAPI.getToday()])
    const banks = Array.isArray(banksRes.data) ? banksRes.data : []
    const groups = Array.isArray(groupsRes.data) ? groupsRes.data : []
    const reviews = Array.isArray(reviewRes.data) ? reviewRes.data : []
    statItems.value[0].val = banks.length
    statItems.value[1].val = groups.length
    statItems.value[2].val = reviews.length
    statItems.value[3].val = groups.filter((g: any) => g.status === 'completed').length
  } catch { /* ignore */ }
})
</script>

<style scoped lang="scss">
.dash { max-width: 640px; margin: 0 auto; }

// welcome
.welcome {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: 8px 0 32px;
  h1 { font-size: 1.5rem; font-weight: 600; color: var(--color-text-primary); margin: 0; }
}
.w-sub { color: var(--color-text-muted); font-size: 0.8125rem; margin: 4px 0 0; }
.w-date { text-align: center; }
.w-day { display: block; font-size: 2.25rem; font-weight: 600; color: var(--color-text-primary); line-height: 1; }
.w-month { display: block; font-size: 0.6875rem; color: var(--color-text-muted); margin-top: 2px; }

// stats
.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 32px; }
.stat { text-align: center; padding: 16px 8px; background: var(--color-bg-paper); border-radius: 8px; border: 1px solid var(--color-border-light); }
.s-val { display: block; font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary); }
.s-label { display: block; font-size: 0.6875rem; color: var(--color-text-muted); margin-top: 2px; }

// sections
.section { margin-bottom: 32px; }
.sec-title { font-size: 0.875rem; font-weight: 600; color: var(--color-text-muted); margin: 0 0 12px; text-transform: uppercase; letter-spacing: 0.05em; }

// actions
.actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.act {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 16px 8px; background: var(--color-bg-paper); border: 1px solid var(--color-border-light);
  border-radius: 8px; cursor: pointer; transition: background 0.15s;
  &:hover { background: var(--color-bg-muted); }
}
.act-icon {
  width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  background: var(--color-bg-muted); color: var(--color-text-secondary); font-size: 20px;
}
.act-label { font-size: 0.75rem; color: var(--color-text-secondary); }

// steps
.steps { display: flex; flex-direction: column; gap: 1px; background: var(--color-border-light); border-radius: 8px; overflow: hidden; }
.step {
  display: flex; align-items: center; gap: 14px; padding: 14px 16px;
  background: var(--color-bg-paper);
}
.step-num {
  width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  background: var(--color-text-primary); color: var(--color-bg-paper); font-size: 0.75rem; font-weight: 600; flex-shrink: 0;
}
.step-text { display: flex; flex-direction: column; }
.step-title { font-size: 0.875rem; font-weight: 500; color: var(--color-text-primary); }
.step-desc { font-size: 0.75rem; color: var(--color-text-muted); }

@media (max-width: 480px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); gap: 8px; }
  .actions { grid-template-columns: repeat(2, 1fr); gap: 8px; }
}
</style>
