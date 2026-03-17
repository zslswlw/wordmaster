<template>
  <div class="banks-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button @click="goBack" circle>
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <span class="title">词库管理</span>
          </div>
          <el-button type="primary" @click="showImportDialog = true">
            <el-icon><Plus /></el-icon>
            导入词库
          </el-button>
        </div>
      </template>
      
      <div v-if="banks.length === 0" class="empty-state">
        <el-empty description="暂无词库，请先导入">
          <el-button type="primary" @click="showImportDialog = true">
            导入词库
          </el-button>
        </el-empty>
      </div>
      
      <el-table v-else :data="banks" style="width: 100%" v-loading="loading">
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="name" label="词库名称" />
        <el-table-column prop="word_count" label="单词数量" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.word_count }} 个</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button 
              type="danger" 
              size="small" 
              @click="handleDelete(row)"
              :loading="row.deleting"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog 
      v-model="showImportDialog" 
      title="导入词库" 
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="importForm" label-width="100px" ref="importFormRef">
        <el-form-item 
          label="词库名称" 
          prop="name"
          :rules="[{ required: true, message: '请输入词库名称', trigger: 'blur' }]"
        >
          <el-input v-model="importForm.name" placeholder="请输入词库名称" />
        </el-form-item>
        <el-form-item 
          label="CSV文件"
          prop="file"
          :rules="[{ required: true, message: '请选择CSV文件', trigger: 'change' }]"
        >
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".csv"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :file-list="fileList"
          >
            <el-button type="primary">
              <el-icon><Upload /></el-icon>
              选择文件
            </el-button>
            <template #tip>
              <div class="el-upload__tip">
                支持CSV格式，格式：序号,单词,音标,释义<br>
                文件大小不超过10MB
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImport">
          导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bankAPI } from '../api'
import { ArrowLeft, Plus, Delete, Upload } from '@element-plus/icons-vue'

interface Bank {
  id: number
  name: string
  word_count: number
  created_at: string
  deleting?: boolean
}

const router = useRouter()
const banks = ref<Bank[]>([])
const loading = ref(false)
const showImportDialog = ref(false)
const importing = ref(false)
const importForm = reactive({
  name: '',
  file: null as File | null
})
const fileList = ref<any[]>([])
const importFormRef = ref()
const uploadRef = ref()

onMounted(async () => {
  await loadBanks()
})

const loadBanks = async () => {
  loading.value = true
  try {
    const { data } = await bankAPI.getAll()
    banks.value = Array.isArray(data) ? data : []
  } catch (error) {
    ElMessage.error('加载词库失败')
    banks.value = []
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push('/dashboard')
}

const handleFileChange = (file: any) => {
  importForm.file = file.raw
}

const handleFileRemove = () => {
  importForm.file = null
  fileList.value = []
}

const handleImport = async () => {
  if (!importForm.name || !importForm.file) {
    ElMessage.warning('请填写词库名称并选择文件')
    return
  }
  
  importing.value = true
  try {
    await bankAPI.upload(importForm.file, importForm.name)
    ElMessage.success('导入成功')
    showImportDialog.value = false
    // 重置表单
    importForm.name = ''
    importForm.file = null
    fileList.value = []
    await loadBanks()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

const handleDelete = async (row: Bank) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除词库"${row.name}"吗？此操作不可恢复！`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    row.deleting = true
    await bankAPI.delete(row.id)
    ElMessage.success('删除成功')
    await loadBanks()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  } finally {
    row.deleting = false
  }
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.banks-container {
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
