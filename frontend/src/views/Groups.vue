<template>
  <div class="page">
    <div class="page-top">
      <h2>学习组管理</h2>
      <el-button type="primary" size="small" @click="openCreateDialog">
        <el-icon><Plus /></el-icon> 创建学习组
      </el-button>
    </div>

    <div v-if="groups.length === 0" class="empty">
      <p>暂无学习组</p>
      <el-button type="primary" @click="openCreateDialog">创建学习组</el-button>
    </div>

    <div v-else class="groups">
      <div v-for="(g, i) in groups" :key="g.id" class="group-row">
        <div class="group-info">
          <span class="gi-index">{{ i + 1 }}</span>
          <div class="gi-main">
            <span class="gi-name">{{ g.name }}</span>
            <span class="gi-meta">
              {{ g.start_seq }}-{{ g.end_seq }}
              <span class="gi-status" :class="g.status">{{ statusText(g.status) }}</span>
            </span>
          </div>
        </div>
        <div class="group-actions">
          <el-tag v-if="g.today_review_status === 'pending'" type="warning" size="small" effect="dark">待复习</el-tag>
          <el-tag v-else-if="g.today_review_status === 'completed'" type="success" size="small" effect="dark">已复习</el-tag>

          <el-button v-if="g.status !== 'completed'" type="primary" size="small" @click="startStudy(g.id)">
            <el-icon><VideoPlay /></el-icon> 学习
          </el-button>
          <el-button v-else-if="g.today_review_status === 'pending'" type="success" size="small" @click="goToGroupReview(g.id)">
            <el-icon><RefreshRight /></el-icon> 复习
          </el-button>
          <el-button v-else-if="g.today_review_status === 'completed'" type="info" size="small" disabled>
            今日已复习
          </el-button>

          <el-button v-if="g.status === 'completed'" size="small" text @click="viewReviewProgress(g)">
            <el-icon><View /></el-icon>
          </el-button>
          <el-button size="small" text type="danger" @click="confirmDelete(g)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- dialogs unchanged structure -->
    <el-dialog v-model="showCreateDialog" title="创建学习组" :width="isMobile ? '90%' : '460px'" :close-on-click-modal="false">
      <el-form :model="form" ref="formRef" :rules="formRules" label-width="80px">
        <el-form-item label="选择词库" prop="bank_id">
          <el-select v-model="form.bank_id" placeholder="请选择词库" style="width:100%">
            <el-option v-for="b in banks" :key="b.id" :label="`${b.name} (${b.word_count}词)`" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="起始序号" prop="start_seq">
          <el-input-number v-model="form.start_seq" :min="1" :max="maxSeq" style="width:100%" />
        </el-form-item>
        <el-form-item label="结束序号" prop="end_seq">
          <el-input-number v-model="form.end_seq" :min="1" :max="maxSeq" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDeleteDialog" title="确认删除" :width="isMobile ? '90%' : '380px'" :close-on-click-modal="false">
      <p style="text-align:center;color:var(--color-text-muted)">确定要删除学习组 "{{ groupToDelete?.name }}" 吗？相关的学习计划和学习记录也会删除。</p>
      <template #footer>
        <el-button @click="showDeleteDialog = false">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="handleDelete">删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showProgressDialog" title="艾宾浩斯复习进度" :width="isMobile ? '95%' : '800px'" :close-on-click-modal="false">
      <ReviewProgress v-if="selectedProgress" :data="selectedProgress" />
      <template #footer>
        <el-button @click="showProgressDialog = false">关闭</el-button>
        <el-button v-if="selectedGroup?.today_review_status === 'pending'" type="primary" @click="startReviewFromProgress">开始复习</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { bankAPI, groupAPI, reviewAPI } from '../api'
import { Plus, VideoPlay, RefreshRight, Delete, View } from '@element-plus/icons-vue'
import ReviewProgress from '../components/ReviewProgress.vue'

const isMobile = ref(window.innerWidth <= 768)
const hr = () => { isMobile.value = window.innerWidth <= 768 }
onMounted(() => window.addEventListener('resize', hr))
onUnmounted(() => window.removeEventListener('resize', hr))

interface Group { id: number; name: string; bank_id: number; start_seq: number; end_seq: number; status: string; created_at: string; completed_at: string | null; today_review_status: 'completed' | 'pending' | 'none' | null }
interface Bank { id: number; name: string; word_count: number }

const router = useRouter()
const groups = ref<Group[]>([])
const banks = ref<Bank[]>([])
const showCreateDialog = ref(false)
const showDeleteDialog = ref(false)
const showProgressDialog = ref(false)
const creating = ref(false)
const deleting = ref(false)
const formRef = ref(); void formRef
const groupToDelete = ref<Group | null>(null)
const selectedGroup = ref<Group | null>(null)
const selectedProgress = ref<any>(null)

const form = reactive({ bank_id: null as number | null, start_seq: 1, end_seq: 50 })
const formRules = {
  bank_id: [{ required: true, message: '请选择词库', trigger: 'change' }],
  start_seq: [{ required: true, message: '请输入起始序号', trigger: 'blur' }],
  end_seq: [{ required: true, message: '请输入结束序号', trigger: 'blur' }]
}

const selectedBank = computed(() => (Array.isArray(banks.value) ? banks.value : []).find(b => b.id === form.bank_id))
const maxSeq = computed(() => selectedBank.value?.word_count || 9999)

watch(() => form.bank_id, (n, o) => {
  if (n && o) {
    const bank = (Array.isArray(banks.value) ? banks.value : []).find(b => b.id === n)
    if (bank) {
      if (form.end_seq > bank.word_count) form.end_seq = bank.word_count
      if (form.start_seq > bank.word_count) form.start_seq = 1
    }
  }
})

onMounted(async () => { await loadGroups(); await loadBanks() })

const loadGroups = async () => {
  try { const { data } = await groupAPI.getAll(); groups.value = Array.isArray(data) ? data : [] } catch { ElMessage.error('加载学习组失败'); groups.value = [] }
}
const loadBanks = async () => {
  try { const { data } = await bankAPI.getAll(); banks.value = Array.isArray(data) ? data : [] } catch { ElMessage.error('加载词库失败'); banks.value = [] }
}

const goToGroupReview = async (groupId: number) => {
  try {
    const { data } = await reviewAPI.getGroupPlans(groupId)
    const plans = Array.isArray(data) ? data : []
    const pp = plans.find((p: any) => p.can_review)
    if (pp) router.push(`/study?groupId=${groupId}&planId=${pp.plan_id}&isReview=true`)
    else ElMessage.info('暂无待复习的计划')
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '获取复习计划失败') }
}

const confirmDelete = (g: Group) => { groupToDelete.value = g; showDeleteDialog.value = true }
const handleDelete = async () => {
  if (!groupToDelete.value) return
  deleting.value = true
  try { await groupAPI.delete(groupToDelete.value.id); ElMessage.success('删除成功'); showDeleteDialog.value = false; groupToDelete.value = null; loadGroups() }
  catch (e: any) { ElMessage.error(e.response?.data?.detail || '删除失败') }
  finally { deleting.value = false }
}

const openCreateDialog = () => {
  if ((Array.isArray(banks.value) ? banks.value : []).length === 0) { ElMessage.warning('请先导入词库'); router.push('/banks'); return }
  form.bank_id = null; form.start_seq = 1; form.end_seq = 50; showCreateDialog.value = true
}

const handleCreate = async () => {
  if (!form.bank_id) { ElMessage.warning('请选择词库'); return }
  if (form.start_seq > form.end_seq) { ElMessage.warning('起始序号不能大于结束序号'); return }
  const bank = banks.value.find(b => b.id === form.bank_id)
  if (bank && form.end_seq > bank.word_count) { ElMessage.warning(`结束序号不能超过词库最大序号 ${bank.word_count}`); return }
  creating.value = true
  try { await groupAPI.create({ bank_id: form.bank_id, start_seq: form.start_seq, end_seq: form.end_seq }); ElMessage.success('创建成功'); showCreateDialog.value = false; await loadGroups() }
  catch (e: any) { ElMessage.error(e.response?.data?.detail || '创建失败') }
  finally { creating.value = false }
}

const startStudy = (groupId: number) => router.push(`/study/${groupId}`)

const viewReviewProgress = async (group: Group) => {
  if (group.status !== 'completed') { ElMessage.info('学习组尚未完成学习'); return }
  selectedGroup.value = group; showProgressDialog.value = true
  try { const { data } = await groupAPI.getReviewProgress(group.id); selectedProgress.value = data }
  catch (e: any) { ElMessage.error(e.response?.data?.detail || '获取失败'); showProgressDialog.value = false }
}

const startReviewFromProgress = () => {
  if (selectedGroup.value) { showProgressDialog.value = false; goToGroupReview(selectedGroup.value.id) }
}

const statusText = (s: string) => ({ new: '新建', learning: '学习中', completed: '已完成' }[s] || s)
</script>

<style scoped lang="scss">
.page { max-width: 800px; margin: 0 auto; }
.page-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;
  h2 { font-size: 1.125rem; font-weight: 700; color: var(--color-text-primary); margin: 0; }
}
.empty { text-align: center; padding: 60px 0; color: var(--color-text-muted); p { margin-bottom: 16px; } }

.groups { display: flex; flex-direction: column; gap: 1px; background: var(--color-border-light); border-radius: 8px; overflow: hidden; }
.group-row { background: var(--color-bg-paper); padding: 16px; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.group-info { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
.gi-index { width: 24px; height: 24px; border-radius: 50%; background: var(--color-text-primary); color: #fff; font-size: 0.6875rem; font-weight: 600; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.gi-main { display: flex; flex-direction: column; min-width: 0; }
.gi-name { font-size: 0.9375rem; font-weight: 500; color: var(--color-text-primary); }
.gi-meta { font-size: 0.75rem; color: var(--color-text-muted); margin-top: 2px; display: flex; align-items: center; gap: 8px; }
.gi-status { padding: 1px 8px; border-radius: 4px; font-size: 0.6875rem;
  &.new { background: rgba(var(--color-primary-rgb), 0.08); color: var(--color-primary); }
  &.learning { background: rgba(var(--color-warning-rgb), 0.08); color: var(--color-warning); }
  &.completed { background: rgba(var(--color-success-rgb), 0.08); color: var(--color-success); }
}
.group-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
</style>
