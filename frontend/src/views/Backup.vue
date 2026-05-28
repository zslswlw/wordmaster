<template>
  <div class="page">
    <h2>数据备份</h2>

    <div class="two-col">
      <div class="card">
        <h3>导出备份</h3>
        <p>将学习数据导出为JSON文件，包含词库、学习记录和复习计划。</p>
        <el-button size="large" :loading="backingUp" @click="handleBackup">导出备份</el-button>
      </div>

      <div class="card">
        <h3>恢复数据</h3>
        <p>从备份文件恢复。此操作将覆盖当前所有数据。</p>
        <el-upload ref="uploadRef" :auto-upload="false" :limit="1" accept=".json" :on-change="onFileChange" :on-remove="onFileRemove" :file-list="fileList" class="upload">
          <el-button size="large">选择文件</el-button>
        </el-upload>
        <el-button v-if="selectedFile" type="danger" size="large" :loading="restoring" @click="showRestoreConfirm = true" class="restore-btn">确认恢复</el-button>
      </div>
    </div>

    <div class="notes">
      <h4>备份说明</h4>
      <ul>
        <li>备份内容：所有词库、学习组、学习记录、复习计划</li>
        <li>建议定期备份，特别是完成一批单词后</li>
        <li>恢复会覆盖当前所有数据，请谨慎操作</li>
      </ul>
    </div>

    <el-dialog v-model="showRestoreConfirm" title="确认恢复" :width="isMobile ? '90%' : '380px'" :close-on-click-modal="false">
      <p style="text-align:center;color:var(--color-danger);font-weight:500;">恢复操作将覆盖当前所有数据，不可撤销！</p>
      <template #footer>
        <el-button @click="showRestoreConfirm = false">取消</el-button>
        <el-button type="danger" :loading="restoring" @click="confirmRestore">确认恢复</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { backupAPI } from '../api'

const backingUp = ref(false)
const restoring = ref(false)
const selectedFile = ref<File | null>(null)
const fileList = ref<any[]>([])
const showRestoreConfirm = ref(false)
const isMobile = ref(window.innerWidth <= 768)

const handleBackup = async () => {
  backingUp.value = true
  try {
    const { data } = await backupAPI.exportData()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `wordmaster_${new Date().toISOString().slice(0,10)}.json`
    document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url)
    ElMessage.success('备份成功')
  } catch { ElMessage.error('备份失败') }
  finally { backingUp.value = false }
}

const onFileChange = (f: any) => { selectedFile.value = f.raw }
const onFileRemove = () => { selectedFile.value = null; fileList.value = [] }

const confirmRestore = async () => {
  if (!selectedFile.value) return
  restoring.value = true
  const reader = new FileReader()
  reader.onload = async (e) => {
    try {
      const data = JSON.parse(e.target?.result as string)
      await backupAPI.import(data)
      ElMessage.success('恢复成功'); showRestoreConfirm.value = false
      selectedFile.value = null; fileList.value = []
    } catch { ElMessage.error('恢复失败，请检查文件格式') }
    finally { restoring.value = false }
  }
  reader.readAsText(selectedFile.value)
}
</script>

<style scoped lang="scss">
.page { max-width: 600px; margin: 0 auto;
  h2 { font-size: 1.125rem; font-weight: 700; color: var(--color-text-primary); margin: 0 0 24px; }
}

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 32px; }
.card {
  padding: 20px; background: var(--color-bg-paper); border: 1px solid var(--color-border-light); border-radius: 8px;
  h3 { font-size: 1rem; font-weight: 600; color: var(--color-text-primary); margin: 0 0 4px; }
  p { font-size: 0.8125rem; color: var(--color-text-muted); margin: 0 0 16px; line-height: 1.5; }
}
.restore-btn { margin-top: 12px; width: 100%; }

.notes {
  h4 { font-size: 0.8125rem; font-weight: 600; color: var(--color-text-muted); margin: 0 0 8px; text-transform: uppercase; letter-spacing: 0.05em; }
  ul { padding-left: 18px; }
  li { font-size: 0.8125rem; color: var(--color-text-muted); margin: 4px 0; }
}

:deep(.el-upload) { width: 100%; .el-button { width: 100%; } }

@media (max-width: 480px) {
  .two-col { grid-template-columns: 1fr; }
}
</style>
