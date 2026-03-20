<template>
  <div class="audio-manage-container">
    <el-card class="status-card">
      <template #header>
        <div class="card-header">
          <span>音频管理</span>
          <el-button 
            type="primary" 
            :loading="syncing"
            @click="startSync"
          >
            <el-icon><Download /></el-icon>
            同步音频
          </el-button>
        </div>
      </template>
      
      <div class="status-overview">
        <el-row :gutter="20">
          <el-col :xs="24" :sm="8">
            <div class="stat-item">
              <div class="stat-value">{{ status.total_words }}</div>
              <div class="stat-label">总单词数</div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="8">
            <div class="stat-item">
              <div class="stat-value has-audio">{{ status.has_audio }}</div>
              <div class="stat-label">已有音频</div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="8">
            <div class="stat-item">
              <div class="stat-value missing">{{ status.missing }}</div>
              <div class="stat-label">缺失音频</div>
            </div>
          </el-col>
        </el-row>
        
        <div class="progress-section">
          <div class="progress-header">
            <span>音频覆盖率</span>
            <span class="progress-value">{{ status.coverage }}</span>
          </div>
          <el-progress 
            :percentage="coveragePercent" 
            :status="progressStatus"
            :stroke-width="20"
          />
        </div>
      </div>
    </el-card>
    
    <el-card v-if="status.missing_sample?.length" class="missing-card">
      <template #header>
        <span>缺失音频的单词（前10个）</span>
      </template>
      <el-tag 
        v-for="word in status.missing_sample" 
        :key="word"
        class="missing-word"
        type="danger"
        effect="plain"
      >
        {{ word }}
      </el-tag>
    </el-card>
    
    <el-card class="action-card">
      <template #header>
        <span>快捷操作</span>
      </template>
      <el-button @click="checkSpecificWord">
        <el-icon><Search /></el-icon>
        检查指定单词
      </el-button>
      <el-button @click="refreshStatus">
        <el-icon><Refresh /></el-icon>
        刷新状态
      </el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Search, Refresh } from '@element-plus/icons-vue'
import axios from 'axios'

interface AudioStatus {
  total_words: number
  has_audio: number
  missing: number
  coverage: string
  audio_dir: string
  missing_sample: string[]
}

const status = ref<AudioStatus>({
  total_words: 0,
  has_audio: 0,
  missing: 0,
  coverage: '0%',
  audio_dir: '',
  missing_sample: []
})

const syncing = ref(false)

const coveragePercent = computed(() => {
  if (status.value.total_words === 0) return 0
  return Math.round((status.value.has_audio / status.value.total_words) * 100)
})

const progressStatus = computed(() => {
  if (coveragePercent.value === 100) return 'success'
  if (coveragePercent.value >= 80) return ''
  return 'exception'
})

const fetchStatus = async () => {
  try {
    const token = localStorage.getItem('token')
    const response = await axios.get('/api/audio/status', {
      headers: { Authorization: `Bearer ${token}` }
    })
    status.value = response.data
  } catch (error) {
    ElMessage.error('获取音频状态失败')
  }
}

const startSync = async () => {
  try {
    syncing.value = true
    const token = localStorage.getItem('token')
    await axios.post('/api/audio/sync', {}, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('音频同步任务已启动，请稍后刷新查看进度')
  } catch (error) {
    ElMessage.error('启动同步失败')
  } finally {
    syncing.value = false
  }
}

const checkSpecificWord = async () => {
  try {
    const { value: word } = await ElMessageBox.prompt(
      '请输入要检查的单词',
      '检查单词音频',
      {
        confirmButtonText: '检查',
        cancelButtonText: '取消',
        inputPattern: /\S+/,
        inputErrorMessage: '请输入单词'
      }
    )
    
    const token = localStorage.getItem('token')
    const response = await axios.get(`/api/audio/check/${word}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    
    if (response.data.exists) {
      ElMessage.success(`单词 "${word}" 已有音频`)
    } else {
      ElMessage.warning(`单词 "${word}" 缺少音频`)
      
      // 询问是否下载
      try {
        await ElMessageBox.confirm(
          `是否立即下载 "${word}" 的音频？`,
          '下载音频',
          { confirmButtonText: '下载', cancelButtonText: '取消' }
        )
        
        await axios.post(`/api/audio/sync-word/${word}`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        })
        ElMessage.success(`"${word}" 音频下载成功`)
        fetchStatus()
      } catch {
        // 用户取消下载
      }
    }
  } catch {
    // 用户取消输入
  }
}

const refreshStatus = () => {
  fetchStatus()
  ElMessage.success('状态已刷新')
}

onMounted(() => {
  fetchStatus()
})
</script>

<style scoped>
.audio-manage-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.status-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-overview {
  padding: 20px 0;
}

.stat-item {
  text-align: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 10px;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 8px;
}

.stat-value.has-audio {
  color: #67c23a;
}

.stat-value.missing {
  color: #f56c6c;
}

.stat-label {
  font-size: 14px;
  color: #606266;
}

.progress-section {
  margin-top: 30px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-size: 16px;
}

.progress-value {
  font-weight: bold;
  color: #409eff;
}

.missing-card {
  margin-bottom: 20px;
}

.missing-word {
  margin: 5px;
}

.action-card {
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  .audio-manage-container {
    padding: 10px;
  }
  
  .stat-value {
    font-size: 24px;
  }
}
</style>
