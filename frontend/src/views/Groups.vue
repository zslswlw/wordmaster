<template>
  <div class="groups-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button @click="goBack" circle>
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <span class="title">学习组管理</span>
          </div>
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            创建学习组
          </el-button>
        </div>
      </template>
      
      <div v-if="groups.length === 0" class="empty-state">
        <el-empty description="暂无学习组，请先创建">
          <el-button type="primary" @click="openCreateDialog">
            创建学习组
          </el-button>
        </el-empty>
      </div>
      
      <el-table v-else :data="groups" style="width: 100%" v-loading="loading">
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="name" label="组名称" min-width="180" />
        <el-table-column label="单词范围" width="120">
          <template #default="{ row }">
            {{ row.start_seq }} - {{ row.end_seq }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="今日复习" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.today_review_status === 'completed'" type="success">
              已完成
            </el-tag>
            <el-tag v-else-if="row.today_review_status === 'pending'" type="warning">
              待复习
            </el-tag>
            <el-tag v-else type="info">
              无计划
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="row.status !== 'completed'" 
              type="primary" 
              size="small" 
              @click="startStudy(row.id)"
            >
              <el-icon><VideoPlay /></el-icon>
              学习
            </el-button>
            <el-button 
              v-else-if="row.today_review_status === 'pending'"
              type="success" 
              size="small" 
              @click="goToGroupReview(row.id)"
            >
              <el-icon><RefreshRight /></el-icon>
              复习
            </el-button>
            <el-button 
              v-else-if="row.today_review_status === 'completed'"
              type="info" 
              size="small" 
              disabled
            >
              <el-icon><RefreshRight /></el-icon>
              今日已复习
            </el-button>
            <el-button 
              v-else
              type="info" 
              size="small" 
              disabled
            >
              <el-icon><RefreshRight /></el-icon>
              暂无复习
            </el-button>
            <el-button 
              type="danger" 
              size="small" 
              @click="confirmDelete(row)"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog 
      v-model="showCreateDialog" 
      title="创建学习组" 
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="100px" ref="formRef" :rules="formRules">
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
          <el-alert 
            :title="`已选择词库: ${selectedBank.name}，共 ${selectedBank.word_count} 个单词`"
            type="info"
            :closable="false"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">
          创建
        </el-button>
      </template>
    </el-dialog>

    <el-dialog 
      v-model="showDeleteDialog" 
      title="确认删除" 
      width="400px"
      :close-on-click-modal="false"
    >
      <el-alert 
        title="删除后无法恢复"
        type="warning"
        :closable="false"
        style="margin-bottom: 15px"
      />
      <p>确定要删除学习组 "{{ groupToDelete?.name }}" 吗？</p>
      <p style="color: #999; font-size: 12px; margin-top: 10px;">
        同时会删除相关的学习计划和学习记录
      </p>
      <template #footer>
        <el-button @click="showDeleteDialog = false">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="handleDelete">
          删除
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { bankAPI, groupAPI, reviewAPI } from '../api'
import { ArrowLeft, Plus, VideoPlay, RefreshRight, Delete } from '@element-plus/icons-vue'

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
const creating = ref(false)
const deleting = ref(false)
const formRef = ref()
const groupToDelete = ref<Group | null>(null)
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
  return banks.value.find(b => b.id === form.bank_id)
})

const maxSeq = computed(() => {
  return selectedBank.value?.word_count || 9999
})

watch(() => form.bank_id, (newVal, oldVal) => {
  if (newVal && oldVal) {
    // 只有切换词库时才调整，且只在当前值超出新词库范围时调整
    const bank = banks.value.find(b => b.id === newVal)
    if (bank) {
      // 如果当前结束序号超出新词库范围，则调整到词库最大值
      if (form.end_seq > bank.word_count) {
        form.end_seq = bank.word_count
      }
      // 如果起始序号超出新词库范围，则调整到1
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
    groups.value = data
  } catch (error) {
    ElMessage.error('加载学习组失败')
  } finally {
    loading.value = false
  }
}

const loadBanks = async () => {
  try {
    const { data } = await bankAPI.getAll()
    banks.value = data
  } catch (error) {
    ElMessage.error('加载词库失败')
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
    const pendingPlan = data.find((p: any) => p.can_review)
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
  if (banks.value.length === 0) {
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

<style scoped>
.groups-container {
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

.empty-state {
  padding: 60px 20px;
}
</style>
