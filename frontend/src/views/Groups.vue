<template>
  <div class="groups-container" :class="{ mobile: isMobile }">
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button @click="goBack" circle :size="isMobile ? 'small' : 'default'" class="back-btn">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <h3 class="title">学习组管理</h3>
          </div>
          <el-button
            type="primary"
            @click="openCreateDialog"
            :size="isMobile ? 'small' : 'default'"
            class="create-btn"
          >
            <el-icon><Plus /></el-icon>
            <span v-if="!isMobile">创建学习组</span>
            <span v-else>新建</span>
          </el-button>
        </div>
      </template>

      <div v-if="groups.length === 0" class="empty-state">
        <div class="empty-icon">
          <el-icon :size="64"><FolderOpened /></el-icon>
        </div>
        <h4>暂无学习组</h4>
        <p>创建您的第一个学习组开始背单词吧</p>
        <el-button type="primary" @click="openCreateDialog" class="empty-btn">
          创建学习组
        </el-button>
      </div>

      <!-- 桌面端表格 -->
      <el-table
        v-else-if="!isMobile"
        :data="groups"
        style="width: 100%"
        v-loading="loading"
        class="groups-table"
      >
        <el-table-column type="index" label="序号" width="70">
          <template #default="{ $index }">
            <span class="index-badge">{{ $index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="组名称" min-width="180">
          <template #default="{ row }">
            <div class="group-name-cell">
              <span class="group-name">{{ row.name }}</span>
              <span class="word-count">{{ row.end_seq - row.start_seq + 1 }} 词</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="单词范围" width="140">
          <template #default="{ row }">
            <span class="range-text">{{ row.start_seq }} - {{ row.end_seq }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" :class="['status-tag', row.status]">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            <span class="date-text">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="今日复习" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.today_review_status === 'completed'" type="success" class="review-tag">
              已完成
            </el-tag>
            <el-tag v-else-if="row.today_review_status === 'pending'" type="warning" class="review-tag">
              待复习
            </el-tag>
            <el-tag v-else type="info" class="review-tag">
              无计划
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button
                v-if="row.status !== 'completed'"
                type="primary"
                size="small"
                @click="startStudy(row.id)"
                class="action-btn study"
              >
                <el-icon><VideoPlay /></el-icon>
                学习
              </el-button>
              <el-button
                v-else-if="row.today_review_status === 'pending'"
                type="success"
                size="small"
                @click="goToGroupReview(row.id)"
                class="action-btn review"
              >
                <el-icon><RefreshRight /></el-icon>
                复习
              </el-button>
              <el-button
                v-else-if="row.today_review_status === 'completed'"
                type="info"
                size="small"
                disabled
                class="action-btn"
              >
                <el-icon><RefreshRight /></el-icon>
                今日已复习
              </el-button>
              <el-button
                v-else
                type="info"
                size="small"
                disabled
                class="action-btn"
              >
                <el-icon><RefreshRight /></el-icon>
                暂无复习
              </el-button>
              <el-button
                v-if="row.status === 'completed'"
                type="default"
                size="small"
                @click="viewReviewProgress(row)"
                class="action-btn"
              >
                <el-icon><View /></el-icon>
                进度
              </el-button>
              <el-button
                type="danger"
                size="small"
                @click="confirmDelete(row)"
                class="action-btn delete"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 移动端卡片列表 -->
      <div v-else class="mobile-list" v-loading="loading">
        <div
          v-for="(group, index) in groups"
          :key="group.id"
          class="mobile-card"
        >
          <div class="card-header-row">
            <div class="card-main">
              <div class="group-index">{{ index + 1 }}</div>
              <div class="group-info">
                <h4 class="group-name">{{ group.name }}</h4>
                <div class="group-meta">
                  <span class="word-range">{{ group.start_seq }} - {{ group.end_seq }}</span>
                  <el-tag :type="getStatusType(group.status)" size="small" :class="['status-tag', group.status]">
                    {{ getStatusText(group.status) }}
                  </el-tag>
                </div>
              </div>
            </div>
            <div class="review-status">
              <el-tag
                v-if="group.today_review_status === 'completed'"
                type="success"
                size="small"
                effect="dark"
              >
                已复习
              </el-tag>
              <el-tag
                v-else-if="group.today_review_status === 'pending'"
                type="warning"
                size="small"
                effect="dark"
              >
                待复习
              </el-tag>
            </div>
          </div>
          <div class="card-footer">
            <span class="create-time">{{ formatDate(group.created_at) }}</span>
            <div class="card-actions">
              <el-button
                v-if="group.status !== 'completed'"
                type="primary"
                size="small"
                @click="startStudy(group.id)"
              >
                <el-icon><VideoPlay /></el-icon>
                学习
              </el-button>
              <el-button
                v-else-if="group.today_review_status === 'pending'"
                type="success"
                size="small"
                @click="goToGroupReview(group.id)"
              >
                <el-icon><RefreshRight /></el-icon>
                复习
              </el-button>
              <el-button
                v-else-if="group.today_review_status === 'completed'"
                type="info"
                size="small"
                disabled
              >
                已复习
              </el-button>
              <el-button
                v-else
                type="info"
                size="small"
                disabled
              >
                暂无
              </el-button>
              <el-button
                v-if="group.status === 'completed'"
                type="default"
                size="small"
                circle
                @click="viewReviewProgress(group)"
              >
                <el-icon><View /></el-icon>
              </el-button>
              <el-button
                type="danger"
                size="small"
                circle
                @click="confirmDelete(group)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 创建学习组对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建学习组"
      :width="isMobile ? '90%' : '480px'"
      :close-on-click-modal="false"
      class="create-dialog"
    >
      <el-form :model="form" label-width="90px" ref="formRef" :rules="formRules" class="create-form">
        <el-form-item label="选择词库" prop="bank_id">
          <el-select v-model="form.bank_id" placeholder="请选择词库" style="width: 100%">
            <el-option
              v-for="bank in banks"
              :key="bank.id"
              :label="`${bank.name} (${bank.word_count}个单词)`"
              :value="bank.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="起始序号" prop="start_seq">
          <el-input-number
            v-model="form.start_seq"
            :min="1"
            :max="maxSeq"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束序号" prop="end_seq">
          <el-input-number
            v-model="form.end_seq"
            :min="1"
            :max="maxSeq"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="selectedBank">
          <div class="bank-info">
            <el-icon><InfoFilled /></el-icon>
            <span>已选择词库: <strong>{{ selectedBank.name }}</strong>，共 <strong>{{ selectedBank.word_count }}</strong> 个单词</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false" size="large">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate" size="large">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 删除确认对话框 -->
    <el-dialog
      v-model="showDeleteDialog"
      title="确认删除"
      :width="isMobile ? '90%' : '400px'"
      :close-on-click-modal="false"
    >
      <div class="delete-warning">
        <el-icon :size="48" color="var(--color-warning)"><Warning /></el-icon>
        <p class="delete-title">删除后无法恢复</p>
        <p class="delete-desc">确定要删除学习组 "{{ groupToDelete?.name }}" 吗？</p>
        <p class="delete-hint">同时会删除相关的学习计划和学习记录</p>
      </div>
      <template #footer>
        <el-button @click="showDeleteDialog = false" size="large">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="handleDelete" size="large">
          删除
        </el-button>
      </template>
    </el-dialog>

    <!-- 复习进度弹窗 -->
    <el-dialog
      v-model="showProgressDialog"
      title="艾宾浩斯复习进度"
      :width="isMobile ? '95%' : '800px'"
      :close-on-click-modal="false"
      class="progress-dialog"
    >
      <ReviewProgress v-if="selectedProgress" :data="selectedProgress" />
      <template #footer>
        <el-button @click="showProgressDialog = false" size="large">关闭</el-button>
        <el-button
          v-if="selectedGroup && selectedGroup.today_review_status === 'pending'"
          type="primary"
          @click="startReviewFromProgress"
          size="large"
        >
          开始复习
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { bankAPI, groupAPI, reviewAPI } from '../api'
import { ArrowLeft, Plus, VideoPlay, RefreshRight, Delete, View, FolderOpened, Warning, InfoFilled } from '@element-plus/icons-vue'
import ReviewProgress from '../components/ReviewProgress.vue'

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

interface Group {
  id: number
  name: string
  bank_id: number
  start_seq: number
  end_seq: number
  status: string
  created_at: string
  completed_at: string | null
  today_review_status: 'completed' | 'pending' | 'none' | null
}

interface Bank {
  id: number
  name: string
  word_count: number
}

const router = useRouter()
const groups = ref<Group[]>([])
const banks = ref<Bank[]>([])
const loading = ref(false)
const showCreateDialog = ref(false)
const showDeleteDialog = ref(false)
const showProgressDialog = ref(false)
const creating = ref(false)
const deleting = ref(false)
const loadingProgress = ref(false)
const formRef = ref()
const groupToDelete = ref<Group | null>(null)
const selectedGroup = ref<Group | null>(null)
const selectedProgress = ref<any>(null)
const form = reactive({
  bank_id: null as number | null,
  start_seq: 1,
  end_seq: 50
})

const formRules = {
  bank_id: [{ required: true, message: '请选择词库', trigger: 'change' }],
  start_seq: [{ required: true, message: '请输入起始序号', trigger: 'blur' }],
  end_seq: [{ required: true, message: '请输入结束序号', trigger: 'blur' }]
}

const selectedBank = computed(() => {
  const banksList = Array.isArray(banks.value) ? banks.value : []
  return banksList.find(b => b.id === form.bank_id)
})

const maxSeq = computed(() => {
  return selectedBank.value?.word_count || 9999
})

watch(() => form.bank_id, (newVal, oldVal) => {
  if (newVal && oldVal) {
    const banksList = Array.isArray(banks.value) ? banks.value : []
    const bank = banksList.find(b => b.id === newVal)
    if (bank) {
      if (form.end_seq > bank.word_count) {
        form.end_seq = bank.word_count
      }
      if (form.start_seq > bank.word_count) {
        form.start_seq = 1
      }
    }
  }
})

onMounted(async () => {
  await loadGroups()
  await loadBanks()
})

const loadGroups = async () => {
  loading.value = true
  try {
    const { data } = await groupAPI.getAll()
    groups.value = Array.isArray(data) ? data : []
  } catch (error) {
    ElMessage.error('加载学习组失败')
    groups.value = []
  } finally {
    loading.value = false
  }
}

const loadBanks = async () => {
  try {
    const { data } = await bankAPI.getAll()
    banks.value = Array.isArray(data) ? data : []
  } catch (error) {
    ElMessage.error('加载词库失败')
    banks.value = []
  }
}

const goBack = () => {
  router.push('/dashboard')
}

const goToReview = () => {
  router.push('/review')
}

const goToGroupReview = async (groupId: number) => {
  try {
    const { data } = await reviewAPI.getGroupPlans(groupId)
    const plans = Array.isArray(data) ? data : []
    const pendingPlan = plans.find((p: any) => p.can_review)
    if (pendingPlan) {
      router.push(`/study?groupId=${groupId}&planId=${pendingPlan.plan_id}&isReview=true`)
    } else {
      ElMessage.info('暂无待复习的计划')
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '获取复习计划失败')
  }
}

const confirmDelete = (group: Group) => {
  groupToDelete.value = group
  showDeleteDialog.value = true
}

const handleDelete = async () => {
  if (!groupToDelete.value) return

  deleting.value = true
  try {
    await groupAPI.delete(groupToDelete.value.id)
    ElMessage.success('删除成功')
    showDeleteDialog.value = false
    groupToDelete.value = null
    loadGroups()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

const openCreateDialog = () => {
  const banksList = Array.isArray(banks.value) ? banks.value : []
  if (banksList.length === 0) {
    ElMessage.warning('请先导入词库')
    router.push('/banks')
    return
  }
  form.bank_id = null
  form.start_seq = 1
  form.end_seq = 50
  showCreateDialog.value = true
}

const handleCreate = async () => {
  if (!form.bank_id) {
    ElMessage.warning('请选择词库')
    return
  }
  if (form.start_seq > form.end_seq) {
    ElMessage.warning('起始序号不能大于结束序号')
    return
  }

  const bank = banks.value.find(b => b.id === form.bank_id)
  if (bank && form.end_seq > bank.word_count) {
    ElMessage.warning(`结束序号不能超过词库最大序号 ${bank.word_count}`)
    return
  }

  creating.value = true
  try {
    await groupAPI.create({
      bank_id: form.bank_id,
      start_seq: form.start_seq,
      end_seq: form.end_seq
    })
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    await loadGroups()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

const startStudy = (groupId: number) => {
  router.push(`/study/${groupId}`)
}

const viewReviewProgress = async (group: Group) => {
  if (group.status !== 'completed') {
    ElMessage.info('学习组尚未完成学习，暂无复习计划')
    return
  }

  selectedGroup.value = group
  loadingProgress.value = true
  showProgressDialog.value = true

  try {
    const { data } = await groupAPI.getReviewProgress(group.id)
    selectedProgress.value = data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '获取复习进度失败')
    showProgressDialog.value = false
  } finally {
    loadingProgress.value = false
  }
}

const startReviewFromProgress = () => {
  if (selectedGroup.value) {
    showProgressDialog.value = false
    goToGroupReview(selectedGroup.value.id)
  }
}

const getStatusType = (status: string) => {
  const types: Record<string, string> = {
    new: 'info',
    learning: 'warning',
    completed: 'success'
  }
  return types[status] || 'info'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    new: '新建',
    learning: '学习中',
    completed: '已完成'
  }
  return texts[status] || status
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped lang="scss">
.groups-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.groups-container.mobile {
  padding: 12px;
}

.main-card {
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--color-border-light);
  overflow: hidden;

  :deep(.el-card__header) {
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border-light);
    background: var(--color-bg-muted);
  }

  :deep(.el-card__body) {
    padding: 0;
  }
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

.back-btn {
  background: var(--color-bg-paper);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);

  &:hover {
    background: var(--color-bg-muted);
    color: var(--color-text-primary);
  }
}

.title {
  font-family: var(--font-display);
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.create-btn {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border: none;
  box-shadow: 0 4px 12px rgba(var(--color-primary-rgb), 0.25);

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(var(--color-primary-rgb), 0.35);
  }
}

/* 空状态 */
.empty-state {
  padding: 60px 20px;
  text-align: center;
}

.empty-icon {
  width: 100px;
  height: 100px;
  margin: 0 auto 20px;
  background: var(--color-bg-muted);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-light);
}

.empty-state h4 {
  font-family: var(--font-display);
  font-size: 1.125rem;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.empty-state p {
  color: var(--color-text-muted);
  font-size: 0.875rem;
  margin-bottom: 24px;
}

.empty-btn {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border: none;
}

/* 桌面端表格 */
.groups-table {
  :deep(.el-table__header th) {
    background: var(--color-bg-muted) !important;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  :deep(.el-table__row) {
    transition: background var(--transition-fast);

    &:hover > td {
      background: var(--color-bg-muted) !important;
    }
  }
}

.index-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  color: white;
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: 600;
}

.group-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-name {
  font-weight: 500;
  color: var(--color-text-primary);
}

.word-count {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.range-text {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
}

.date-text {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}

.status-tag {
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  padding: 2px 10px;

  &.new {
    background: rgba(74, 126, 184, 0.1);
    color: var(--color-info);
    border-color: transparent;
  }

  &.learning {
    background: rgba(212, 134, 12, 0.1);
    color: var(--color-warning);
    border-color: transparent;
  }

  &.completed {
    background: rgba(45, 138, 94, 0.1);
    color: var(--color-success);
    border-color: transparent;
  }
}

.review-tag {
  border-radius: var(--radius-full);
  font-size: 0.6875rem;
  padding: 2px 8px;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.action-btn {
  border-radius: var(--radius-md);
  font-size: 0.8125rem;

  &.study {
    background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
    border: none;
    color: white;
  }

  &.review {
    background: linear-gradient(135deg, var(--color-success) 0%, #3dd477 100%);
    border: none;
    color: white;
  }

  &.delete {
    background: transparent;
    border-color: var(--color-danger);
    color: var(--color-danger);

    &:hover {
      background: var(--color-danger);
      color: white;
    }
  }
}

/* 移动端列表 */
.mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.mobile-card {
  background: var(--color-bg-paper);
  border-radius: var(--radius-lg);
  padding: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-border-light);
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.card-main {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: 1;
}

.group-index {
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: bold;
  flex-shrink: 0;
}

.group-info {
  flex: 1;
  min-width: 0;
}

.group-name {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 8px 0;
  line-height: 1.4;
}

.group-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.word-range {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  background: var(--color-bg-muted);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.review-status {
  flex-shrink: 0;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
}

.create-time {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.card-actions {
  display: flex;
  gap: 8px;
}

/* 创建表单 */
.create-form {
  :deep(.el-form-item__label) {
    font-weight: 500;
    color: var(--color-text-secondary);
  }
}

.bank-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(var(--color-primary-rgb), 0.05);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  font-size: 0.875rem;

  .el-icon {
    color: var(--color-primary);
  }

  strong {
    color: var(--color-text-primary);
  }
}

/* 删除确认 */
.delete-warning {
  text-align: center;
  padding: 20px 0;
}

.delete-title {
  font-family: var(--font-display);
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 16px 0 8px;
}

.delete-desc {
  color: var(--color-text-secondary);
  font-size: 0.9375rem;
  margin-bottom: 8px;
}

.delete-hint {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
}

/* 横屏适配 */
@media (min-width: 569px) and (max-width: 896px) and (orientation: landscape) {
  .mobile-list {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
}

/* 小屏幕手机 */
@media (max-width: 375px) {
  .groups-container.mobile {
    padding: 8px;
  }

  .mobile-card {
    padding: 12px;
  }

  .group-name {
    font-size: 0.9375rem;
  }

  .card-actions {
    gap: 4px;
  }
}
</style>
