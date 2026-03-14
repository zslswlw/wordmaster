<template>
  <div class="backup-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button @click="goBack" circle>
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <span class="title">数据备份与恢复</span>
          </div>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card class="action-card" shadow="hover">
            <div class="action-icon">
              <el-icon :size="48" color="#409eff"><Download /></el-icon>
            </div>
            <h3>数据备份</h3>
            <p class="action-desc">将您的学习数据导出为备份文件，包含所有词库、学习记录和复习计划</p>
            <el-button 
              type="primary" 
              size="large" 
              @click="handleBackup"
              :loading="backingUp"
              class="action-btn"
            >
              <el-icon><Download /></el-icon>
              导出备份
            </el-button>
          </el-card>
        </el-col>
        
        <el-col :span="12">
          <el-card class="action-card" shadow="hover">
            <div class="action-icon">
              <el-icon :size="48" color="#67c23a"><Upload /></el-icon>
            </div>
            <h3>数据恢复</h3>
            <p class="action-desc">从备份文件恢复您的学习数据，将覆盖当前所有数据</p>
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".json"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              :file-list="fileList"
              class="upload-area"
            >
              <el-button 
                type="success" 
                size="large"
                :loading="restoring"
                class="action-btn"
              >
                <el-icon><Upload /></el-icon>
                选择备份文件
              </el-button>
              <template #tip>
                <div class="el-upload__tip">
                  请选择之前导出的JSON备份文件
                </div>
              </template>
            </el-upload>
            <el-button 
              v-if="selectedFile"
              type="warning" 
              size="large" 
              @click="handleRestore"
              :loading="restoring"
              class="action-btn restore-btn"
            >
              <el-icon><RefreshRight /></el-icon>
              确认恢复
            </el-button>
          </el-card>
        </el-col>
      </el-row>

      <el-divider />

      <div class="backup-info">
        <h4>备份说明</h4>
        <el-alert
          title="备份内容包括"
          type="info"
          :closable="false"
          class="info-alert"
        >
          <ul>
            <li>所有导入的词库数据</li>
            <li>学习组和学习记录</li>
            <li>复习计划和完成情况</li>
            <li>用户个人设置</li>
          </ul>
        </el-alert>
        <el-alert
          title="注意事项"
          type="warning"
          :closable="false"
          class="info-alert"
        >
          <ul>
            <li>建议定期备份以防数据丢失</li>
            <li>恢复操作将覆盖当前所有数据，请谨慎操作</li>
            <li>备份文件请妥善保管，不要泄露给他人</li>
          </ul>
        </el-alert>
      </div>
    </el-card>

    <!-- 恢复确认对话框 -->
    <el-dialog
      v-model="showRestoreConfirm"
      title="确认恢复数据"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="警告"
        type="error"
        :closable="false"
        show-icon
      >
        <p>恢复操作将覆盖当前所有数据，此操作不可撤销！</p>
      </el-alert>
      <p class="confirm-text">确定要继续恢复数据吗？</p>
      <template #footer>
        <el-button @click="showRestoreConfirm = false">取消</el-button>
        <el-button type="danger" :loading="restoring" @click="confirmRestore">
          确认恢复
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { backupAPI } from '../api'
import { ArrowLeft, Download, Upload, RefreshRight } from '@element-plus/icons-vue'

const router = useRouter()
const backingUp = ref(false)
const restoring = ref(false)
const selectedFile = ref<File | null>(null)
const fileList = ref<any[]>([])
const showRestoreConfirm = ref(false)
const uploadRef = ref()

const goBack = () => {
  router.push('/home')
}

const handleBackup = async () => {
  backingUp.value = true
  try {
    const { data } = await backupAPI.exportData()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `vocab_backup_${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('备份成功')
  } catch (error) {
    ElMessage.error('备份失败')
  } finally {
    backingUp.value = false
  }
}

const handleFileChange = (file: any) => {
  selectedFile.value = file.raw
}

const handleFileRemove = () => {
  selectedFile.value = null
  fileList.value = []
}

const handleRestore = () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择备份文件')
    return
  }
  showRestoreConfirm.value = true
}

const confirmRestore = async () => {
  if (!selectedFile.value) return
  
  restoring.value = true
  try {
    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const data = JSON.parse(e.target?.result as string)
        await backupAPI.importData(data)
        ElMessage.success('恢复成功')
        showRestoreConfirm.value = false
        selectedFile.value = null
        fileList.value = []
      } catch (error) {
        ElMessage.error('恢复失败，请检查备份文件格式')
      } finally {
        restoring.value = false
      }
    }
    reader.readAsText(selectedFile.value)
  } catch (error) {
    ElMessage.error('读取文件失败')
    restoring.value = false
  }
}
</script>

<style scoped>
.backup-container {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
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

.action-card {
  text-align: center;
  padding: 30px 20px;
  height: 100%;
}

.action-icon {
  margin-bottom: 20px;
}

.action-card h3 {
  margin: 0 0 12px 0;
  font-size: 20px;
  color: #303133;
}

.action-desc {
  color: #606266;
  margin-bottom: 24px;
  line-height: 1.6;
  min-height: 48px;
}

.action-btn {
  width: 100%;
  max-width: 200px;
}

.upload-area {
  margin-bottom: 16px;
}

.restore-btn {
  margin-top: 12px;
}

.backup-info {
  margin-top: 20px;
}

.backup-info h4 {
  margin-bottom: 16px;
  color: #303133;
}

.info-alert {
  margin-bottom: 16px;
}

.info-alert ul {
  margin: 8px 0;
  padding-left: 20px;
}

.info-alert li {
  margin: 4px 0;
}

.confirm-text {
  margin-top: 20px;
  text-align: center;
  font-size: 16px;
  color: #606266;
}
</style>
