<template>
  <div class="admin-security">
    <section class="section-band">
      <div class="section-heading">
        <div>
          <h3>管理员账号</h3>
          <p>每位管理员使用独立账号，权限变更立即在服务端生效。</p>
        </div>
        <el-button :icon="Refresh" circle title="刷新" @click="loadUsers" />
      </div>
      <div v-loading="loadingUsers" class="user-list">
        <div v-for="user in users" :key="user.id" class="user-row">
          <div>
            <strong>{{ user.username }}</strong>
            <span>{{ user.id === currentUserId ? '当前账号' : formatDate(user.created_at) }}</span>
          </div>
          <el-select
            :model-value="user.role"
            :disabled="user.id === currentUserId"
            size="small"
            style="width: 112px"
            @change="(role: 'admin' | 'user') => changeRole(user, role)"
          >
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
          </el-select>
        </div>
      </div>
    </section>

    <section class="section-band">
      <div class="section-heading">
        <div>
          <h3>操作记录</h3>
          <p>敏感信息不会写入记录，时间统一按上海时区显示。</p>
        </div>
        <el-button :icon="Refresh" circle title="刷新" @click="loadAudit" />
      </div>
      <div v-loading="loadingAudit" class="audit-list">
        <div v-for="item in auditItems" :key="item.id" class="audit-row">
          <div class="audit-main">
            <strong>{{ item.actor_username }}</strong>
            <span>{{ actionText[item.action] || item.action }}</span>
          </div>
          <span class="audit-target">{{ item.target_type }}{{ item.target_id ? ` #${item.target_id}` : '' }}</span>
          <time>{{ formatDate(item.created_at) }}</time>
        </div>
        <div v-if="!loadingAudit && auditItems.length === 0" class="empty">暂无操作记录</div>
      </div>
      <el-button v-if="nextBeforeId" text class="load-more" @click="loadMore">加载更多</el-button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { adminAPI, authAPI } from '../api'

const users = ref<any[]>([])
const auditItems = ref<any[]>([])
const currentUserId = ref<number | null>(null)
const loadingUsers = ref(false)
const loadingAudit = ref(false)
const nextBeforeId = ref<number | null>(null)

const actionText: Record<string, string> = {
  'admin.role.update': '修改账号角色',
  'ai_config.create': '新增 AI 配置',
  'ai_config.update': '修改 AI 配置',
  'ai_config.delete': '删除 AI 配置',
  'feature_flags.update': '修改功能开关',
  'ai_worker.pause': '暂停后台调度',
  'ai_worker.resume': '恢复后台调度',
  'ai_worker.config.update': '修改调度参数',
  'ai_jobs.retry_failed': '重试失败任务',
  'word_bank.import': '导入词库',
  'word_bank.delete': '删除词库',
  'memory_bundle.draft.create': '创建记忆草稿',
  'memory_bundle.activate': '启用记忆版本',
  'memory_bundle.rollback': '回滚记忆版本',
  'backup.restore': '恢复备份',
  'backup.restore.failed': '恢复备份失败',
}

const formatDate = (value: string) => `${new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
  hour12: false,
}).format(new Date(value))}（上海）`

const loadUsers = async () => {
  loadingUsers.value = true
  try {
    const [{ data }, me] = await Promise.all([adminAPI.users(), authAPI.me()])
    users.value = data || []
    currentUserId.value = me.data.id
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '用户列表加载失败')
  } finally {
    loadingUsers.value = false
  }
}

const loadAudit = async () => {
  loadingAudit.value = true
  try {
    const { data } = await adminAPI.auditLogs({ limit: 80 })
    auditItems.value = data.items || []
    nextBeforeId.value = data.next_before_id
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作记录加载失败')
  } finally {
    loadingAudit.value = false
  }
}

const loadMore = async () => {
  if (!nextBeforeId.value) return
  const { data } = await adminAPI.auditLogs({ limit: 80, before_id: nextBeforeId.value })
  auditItems.value.push(...(data.items || []))
  nextBeforeId.value = data.next_before_id
}

const changeRole = async (user: any, role: 'admin' | 'user') => {
  try {
    await ElMessageBox.confirm(
      `确定将 ${user.username} 设置为${role === 'admin' ? '管理员' : '普通用户'}？`,
      '确认权限变更',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' },
    )
    await adminAPI.updateRole(user.id, role)
    ElMessage.success('权限已更新')
    await Promise.all([loadUsers(), loadAudit()])
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '权限更新失败')
  }
}

onMounted(() => Promise.all([loadUsers(), loadAudit()]))
</script>

<style scoped lang="scss">
.admin-security { display: flex; flex-direction: column; gap: 32px; }
.section-band { width: 100%; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 12px;
  h3 { margin: 0; font-size: 0.9375rem; }
  p { margin: 3px 0 0; color: var(--color-text-muted); font-size: 0.75rem; }
}
.user-list, .audit-list { border-top: 1px solid var(--color-border-light); }
.user-row, .audit-row { min-height: 54px; display: flex; align-items: center; gap: 16px; border-bottom: 1px solid var(--color-border-light); }
.user-row { justify-content: space-between;
  strong, span { display: block; }
  strong { font-size: 0.875rem; }
  span { margin-top: 2px; color: var(--color-text-muted); font-size: 0.6875rem; }
}
.audit-row { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(120px, 0.8fr) auto; font-size: 0.75rem; }
.audit-main { min-width: 0;
  strong { margin-right: 8px; }
  span { color: var(--color-text-secondary); }
}
.audit-target, time { color: var(--color-text-muted); overflow-wrap: anywhere; }
.empty { padding: 28px 0; text-align: center; color: var(--color-text-muted); font-size: 0.8125rem; }
.load-more { display: block; margin: 10px auto 0; }
@media (max-width: 640px) {
  .audit-row { grid-template-columns: 1fr auto; padding: 8px 0; }
  .audit-target { grid-column: 1 / -1; }
}
</style>
