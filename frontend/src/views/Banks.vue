<template>
  <div class="page">
    <div class="page-top">
      <h2>词库管理</h2>
      <el-button v-if="isAdmin" type="primary" size="small" @click="showImportDialog = true">
        <el-icon><Plus /></el-icon> 导入词库
      </el-button>
    </div>

    <div v-if="banks.length === 0" class="empty">
      <p>暂无词库</p>
      <el-button v-if="isAdmin" type="primary" @click="showImportDialog = true">导入词库</el-button>
    </div>

    <div v-else class="banks">
      <div v-for="bank in banks" :key="bank.id" class="bank-row">
        <div class="bank-info">
          <span class="bank-name">{{ bank.name }}</span>
          <span class="bank-meta">{{ bank.word_count }} 词 &middot; {{ formatDate(bank.created_at) }}</span>
        </div>
        <el-button v-if="isAdmin" type="danger" size="small" text @click="handleDelete(bank)" :loading="bank.deleting">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>

    <el-dialog v-model="showImportDialog" title="导入词库" :width="isMobile ? '90%' : '460px'" :close-on-click-modal="false">
      <el-form :model="importForm" ref="importFormRef">
        <el-form-item label="词库名称" prop="name" :rules="[{ required: true, message: '请输入词库名称', trigger: 'blur' }]">
          <el-input v-model="importForm.name" placeholder="如：大学英语六级" />
        </el-form-item>
        <el-form-item label="CSV文件" prop="file" :rules="[{ required: true, message: '请选择文件', trigger: 'change' }]">
          <el-upload ref="uploadRef" :auto-upload="false" :limit="1" accept=".csv" :on-change="onFileChange" :on-remove="onFileRemove" :file-list="fileList">
            <el-button>选择CSV文件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bankAPI } from '../api'
import { useAuth } from '../composables/useAuth'
import { Plus, Delete } from '@element-plus/icons-vue'

interface Bank { id: number; name: string; word_count: number; created_at: string; deleting?: boolean }

const { isAdmin } = useAuth()
const banks = ref<Bank[]>([])
const showImportDialog = ref(false)
const importing = ref(false)
const importForm = reactive({ name: '', file: null as File | null })
const fileList = ref<any[]>([])
const isMobile = ref(window.innerWidth <= 768)

onMounted(() => loadBanks())

const loadBanks = async () => {
  try { const { data } = await bankAPI.getAll(); banks.value = Array.isArray(data) ? data : [] }
  catch { ElMessage.error('加载失败') }
}

const onFileChange = (f: any) => { importForm.file = f.raw }
const onFileRemove = () => { importForm.file = null; fileList.value = [] }

const handleImport = async () => {
  if (!importForm.name || !importForm.file) { ElMessage.warning('请填写名称并选择文件'); return }
  importing.value = true
  try {
    await bankAPI.upload(importForm.file, importForm.name)
    ElMessage.success('导入成功，AI 预处理已在后台自动启动')
    showImportDialog.value = false
    importForm.name = ''; importForm.file = null; fileList.value = []
    await loadBanks()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '导入失败') }
  finally { importing.value = false }
}

const handleDelete = async (row: Bank) => {
  try {
    await ElMessageBox.confirm(`确定删除词库"${row.name}"？此操作不可恢复。`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    row.deleting = true
    await bankAPI.delete(row.id)
    ElMessage.success('已删除')
    await loadBanks()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  } finally { row.deleting = false }
}

const formatDate = (d: string) => {
  if (!d) return ''; const dt = new Date(d)
  return `${dt.getMonth() + 1}/${dt.getDate()}`
}
</script>

<style scoped lang="scss">
.page { max-width: 720px; margin: 0 auto; }
.page-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;
  h2 { font-size: 1.125rem; font-weight: 700; color: var(--color-text-primary); margin: 0; }
}

.empty { text-align: center; padding: 60px 0; color: var(--color-text-muted);
  p { margin-bottom: 16px; }
}

.banks { display: flex; flex-direction: column; gap: 1px; background: var(--color-border-light); border-radius: 8px; overflow: hidden; }
.bank-row {
  display: flex; justify-content: space-between; align-items: center; padding: 14px 16px;
  background: var(--color-bg-paper);
}
.bank-info { display: flex; flex-direction: column; min-width: 0; }
.bank-name { font-size: 0.9375rem; font-weight: 500; color: var(--color-text-primary); }
.bank-meta { font-size: 0.75rem; color: var(--color-text-muted); margin-top: 2px; }
</style>
