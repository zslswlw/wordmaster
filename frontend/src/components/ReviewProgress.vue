<template>
  <div class="review-progress" :class="{ mobile: isMobile, tablet: isTablet }">
    <!-- 总体进度概览 -->
    <div class="progress-overview">
      <div class="progress-title">艾宾浩斯复习进度</div>
      <div class="progress-stats">
        <span class="completed-count">{{ completedCount }}</span>
        <span class="total-count">/ {{ totalCount }}</span>
        <el-tag :type="overallStatusType" size="small" class="status-tag">
          {{ overallStatusText }}
        </el-tag>
      </div>
      <el-progress 
        :percentage="progressPercentage" 
        :status="progressStatus"
        :stroke-width="isMobile ? 8 : 12"
        class="overall-progress-bar"
      />
    </div>

    <!-- 桌面端/平板：水平时间线 -->
    <div v-if="!isMobile" class="timeline-horizontal">
      <div class="timeline-track">
        <div 
          v-for="(item, index) in progress" 
          :key="item.round"
          class="timeline-node"
          :class="[
            item.status,
            { first: index === 0, last: index === progress.length - 1 }
          ]"
        >
          <!-- 节点圆点 -->
          <div class="node-dot">
            <el-icon v-if="item.status === 'completed'"><Check /></el-icon>
            <el-icon v-else-if="item.status === 'today'"><AlarmClock /></el-icon>
            <el-icon v-else-if="item.status === 'overdue'"><Warning /></el-icon>
            <span v-else class="dot-number">{{ item.round }}</span>
          </div>
          
          <!-- 节点信息 -->
          <div class="node-info">
            <div class="node-day">第{{ item.interval_days }}天</div>
            <div class="node-status" :class="item.status">
              {{ getStatusText(item.status) }}
            </div>
            <div class="node-date">{{ formatDate(item.display_date) }}</div>
            <div v-if="item.postponed_days > 0" class="postponed-badge">
              延期{{ item.postponed_days }}天
            </div>
          </div>
          
          <!-- 连接线（除了最后一个） -->
          <div v-if="index < progress.length - 1" class="node-line" :class="item.status" />
        </div>
      </div>
    </div>

    <!-- 手机端：垂直时间线 -->
    <div v-else class="timeline-vertical">
      <div 
        v-for="(item, index) in progress" 
        :key="item.round"
        class="timeline-item"
        :class="item.status"
      >
        <!-- 左侧：节点和连线 -->
        <div class="item-left">
          <div class="item-dot" :class="item.status">
            <el-icon v-if="item.status === 'completed'"><Check /></el-icon>
            <el-icon v-else-if="item.status === 'today'"><AlarmClock /></el-icon>
            <el-icon v-else-if="item.status === 'overdue'"><Warning /></el-icon>
            <span v-else>{{ item.round }}</span>
          </div>
          <div v-if="index < progress.length - 1" class="item-line" />
        </div>
        
        <!-- 右侧：信息卡片 -->
        <div class="item-card" :class="item.status">
          <div class="card-header">
            <span class="round-name">第{{ item.round }}轮</span>
            <span class="interval">({{ item.interval_days }}天后)</span>
          </div>
          <div class="card-status" :class="item.status">
            {{ getStatusText(item.status) }}
          </div>
          <div class="card-date">
            <template v-if="item.status === 'completed'">
              完成于 {{ formatDate(item.completed_at) }}
            </template>
            <template v-else-if="item.status === 'overdue'">
              已逾期 {{ getOverdueDays(item.review_date) }} 天
            </template>
            <template v-else>
              计划: {{ formatDate(item.display_date) }}
            </template>
          </div>
          <div v-if="item.postponed_days > 0" class="postponed-info">
            已延期 {{ item.postponed_days }} 天
            <span class="original-date">(原: {{ formatDate(item.original_date) }})</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 延期说明 -->
    <div v-if="hasPostponedPlans" class="postponed-notice">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
      >
        <template #title>
          有复习计划已被延期，建议尽快完成以保持记忆效果
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useResponsive } from '../composables/useResponsive'
import { Check, AlarmClock, Warning } from '@element-plus/icons-vue'

interface ReviewProgressItem {
  round: number
  interval_days: number
  status: 'completed' | 'today' | 'pending' | 'overdue' | 'not_created'
  original_date: string | null
  review_date: string | null
  display_date: string | null
  postponed_days: number
  completed_at: string | null
}

interface ReviewProgressData {
  group_id: number
  group_name: string
  group_status: string
  completed_at: string | null
  overall_progress: {
    completed: number
    total: number
    percentage: number
  }
  ebinghaus_progress: ReviewProgressItem[]
}

const props = defineProps<{
  data: ReviewProgressData
}>()

const { isMobile, isTablet } = useResponsive()

const progress = computed(() => props.data.ebinghaus_progress)
const completedCount = computed(() => props.data.overall_progress.completed)
const totalCount = computed(() => props.data.overall_progress.total)
const progressPercentage = computed(() => props.data.overall_progress.percentage)

const progressStatus = computed(() => {
  if (progressPercentage.value === 100) return 'success'
  if (progressPercentage.value >= 60) return ''
  return 'exception'
})

const overallStatusType = computed(() => {
  const completed = completedCount.value
  if (completed === totalCount.value) return 'success'
  if (completed >= 3) return 'primary'
  if (completed >= 1) return 'warning'
  return 'info'
})

const overallStatusText = computed(() => {
  const completed = completedCount.value
  if (completed === totalCount.value) return '全部完成'
  if (completed === 0) return '待开始'
  return `进行中 ${completed}/${totalCount.value}`
})

const hasPostponedPlans = computed(() => {
  return progress.value.some(item => item.postponed_days > 0)
})

function getStatusText(status: string): string {
  const statusMap: Record<string, string> = {
    'completed': '已完成',
    'today': '今日复习',
    'pending': '待复习',
    'overdue': '已逾期',
    'not_created': '未创建'
  }
  return statusMap[status] || status
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

function getOverdueDays(reviewDate: string | null): number {
  if (!reviewDate) return 0
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(reviewDate)
  due.setHours(0, 0, 0, 0)
  const diff = Math.floor((today.getTime() - due.getTime()) / (1000 * 60 * 60 * 24))
  return Math.max(0, diff)
}
</script>

<style scoped lang="scss">
.review-progress {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;

  &.mobile {
    padding: 12px;
  }
}

// 总体进度概览
.progress-overview {
  margin-bottom: 24px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);

  .mobile & {
    margin-bottom: 16px;
    padding: 12px;
  }
}

.progress-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;

  .mobile & {
    font-size: 14px;
    margin-bottom: 8px;
  }
}

.progress-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;

  .completed-count {
    font-size: 28px;
    font-weight: 700;
    color: #67c23a;

    .mobile & {
      font-size: 24px;
    }
  }

  .total-count {
    font-size: 16px;
    color: #909399;

    .mobile & {
      font-size: 14px;
    }
  }

  .status-tag {
    margin-left: auto;
  }
}

.overall-progress-bar {
  :deep(.el-progress__text) {
    font-weight: 600;
  }
}

// 水平时间线（桌面端/平板）
.timeline-horizontal {
  background: white;
  border-radius: 8px;
  padding: 24px;
  overflow-x: auto;

  .tablet & {
    padding: 16px;
  }
}

.timeline-track {
  display: flex;
  justify-content: space-between;
  position: relative;
  min-width: 600px;
}

.timeline-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;

  &.first {
    align-items: flex-start;
  }

  &.last {
    align-items: flex-end;
  }
}

.node-dot {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  z-index: 2;
  transition: all 0.3s;

  .timeline-node.completed & {
    background: #67c23a;
    color: white;
  }

  .timeline-node.today & {
    background: #409eff;
    color: white;
    animation: pulse 2s infinite;
  }

  .timeline-node.pending & {
    background: #e4e7ed;
    color: #909399;
  }

  .timeline-node.overdue & {
    background: #f56c6c;
    color: white;
  }

  .timeline-node.not_created & {
    background: #f5f7fa;
    color: #c0c4cc;
    border: 2px dashed #dcdfe6;
  }
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.4);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(64, 158, 255, 0);
  }
}

.node-info {
  margin-top: 12px;
  text-align: center;

  .timeline-node.first & {
    text-align: left;
  }

  .timeline-node.last & {
    text-align: right;
  }
}

.node-day {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.node-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 4px;
  display: inline-block;

  &.completed {
    color: #67c23a;
    background: #f0f9eb;
  }

  &.today {
    color: #409eff;
    background: #ecf5ff;
  }

  &.pending {
    color: #909399;
  }

  &.overdue {
    color: #f56c6c;
    background: #fef0f0;
  }
}

.node-date {
  font-size: 12px;
  color: #909399;
}

.postponed-badge {
  font-size: 10px;
  color: #e6a23c;
  background: #fdf6ec;
  padding: 2px 6px;
  border-radius: 4px;
  margin-top: 4px;
}

.node-line {
  position: absolute;
  top: 20px;
  left: 50%;
  right: -50%;
  height: 2px;
  background: #e4e7ed;
  z-index: 1;

  &.completed {
    background: #67c23a;
  }
}

// 垂直时间线（手机端）
.timeline-vertical {
  background: white;
  border-radius: 8px;
  padding: 16px;
}

.timeline-item {
  display: flex;
  gap: 12px;
  position: relative;

  &:not(:last-child) {
    margin-bottom: 16px;
  }
}

.item-left {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.item-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;

  &.completed {
    background: #67c23a;
    color: white;
  }

  &.today {
    background: #409eff;
    color: white;
  }

  &.pending {
    background: #e4e7ed;
    color: #909399;
  }

  &.overdue {
    background: #f56c6c;
    color: white;
  }

  &.not_created {
    background: #f5f7fa;
    color: #c0c4cc;
    border: 2px dashed #dcdfe6;
  }
}

.item-line {
  width: 2px;
  flex: 1;
  background: #e4e7ed;
  margin: 4px 0;
}

.item-card {
  flex: 1;
  padding: 12px;
  border-radius: 8px;
  background: #f5f7fa;
  border-left: 4px solid #dcdfe6;

  &.completed {
    border-left-color: #67c23a;
    background: #f0f9eb;
  }

  &.today {
    border-left-color: #409eff;
    background: #ecf5ff;
  }

  &.overdue {
    border-left-color: #f56c6c;
    background: #fef0f0;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.round-name {
  font-weight: 600;
  color: #303133;
}

.interval {
  font-size: 12px;
  color: #909399;
}

.card-status {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;

  &.completed {
    color: #67c23a;
  }

  &.today {
    color: #409eff;
  }

  &.pending {
    color: #909399;
  }

  &.overdue {
    color: #f56c6c;
  }
}

.card-date {
  font-size: 12px;
  color: #606266;
}

.postponed-info {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #dcdfe6;
  font-size: 11px;
  color: #e6a23c;

  .original-date {
    color: #909399;
    margin-left: 4px;
  }
}

// 延期提示
.postponed-notice {
  margin-top: 16px;
}
</style>
