<template>
  <div class="dashboard-container">
    <!-- 统计卡片 -->
    <el-row :gutter="12" class="stats-row">
      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background-color: #409eff;">
            <el-icon :size="isMobile ? 24 : 32" color="#fff"><Collection /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.banks }}</div>
            <div class="stat-label">词库</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background-color: #67c23a;">
            <el-icon :size="isMobile ? 24 : 32" color="#fff"><FolderOpened /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.groups }}</div>
            <div class="stat-label">学习组</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background-color: #e6a23c;">
            <el-icon :size="isMobile ? 24 : 32" color="#fff"><Calendar /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.todayReview }}</div>
            <div class="stat-label">今日复习</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background-color: #f56c6c;">
            <el-icon :size="isMobile ? 24 : 32" color="#fff"><Trophy /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.completed }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快速操作 -->
    <el-row class="action-row">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>快速开始</span>
            </div>
          </template>
          <div class="quick-actions">
            <div class="action-item" @click="goToBanks">
              <div class="action-icon-large" style="background-color: #ecf5ff;">
                <el-icon :size="isMobile ? 28 : 40" color="#409eff"><Plus /></el-icon>
              </div>
              <div class="action-title">导入词库</div>
              <div class="action-desc" v-if="!isMobile">添加新单词</div>
            </div>
            <div class="action-item" @click="goToGroups">
              <div class="action-icon-large" style="background-color: #f0f9eb;">
                <el-icon :size="isMobile ? 28 : 40" color="#67c23a"><VideoPlay /></el-icon>
              </div>
              <div class="action-title">开始学习</div>
              <div class="action-desc" v-if="!isMobile">创建学习组</div>
            </div>
            <div class="action-item" @click="goToReview">
              <div class="action-icon-large" style="background-color: #fdf6ec;">
                <el-icon :size="isMobile ? 28 : 40" color="#e6a23c"><RefreshRight /></el-icon>
              </div>
              <div class="action-title">今日复习</div>
              <div class="action-desc" v-if="!isMobile">查看计划</div>
            </div>
            <div class="action-item" @click="goToBackup">
              <div class="action-icon-large" style="background-color: #fef0f0;">
                <el-icon :size="isMobile ? 28 : 40" color="#f56c6c"><Download /></el-icon>
              </div>
              <div class="action-title">数据备份</div>
              <div class="action-desc" v-if="!isMobile">备份数据</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 学习提示和系统说明 -->
    <el-row :gutter="12" class="info-row">
      <el-col :xs="24" :sm="24" :md="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>学习提示</span>
            </div>
          </template>
          <div class="tips-list">
            <div class="tip-item">
              <el-icon color="#409eff"><InfoFilled /></el-icon>
              <span>建议每天学习20-50个新单词</span>
            </div>
            <div class="tip-item">
              <el-icon color="#67c23a"><InfoFilled /></el-icon>
              <span>按照艾宾浩斯遗忘曲线复习</span>
            </div>
            <div class="tip-item">
              <el-icon color="#e6a23c"><InfoFilled /></el-icon>
              <span>听写时认真听发音，多练习</span>
            </div>
            <div class="tip-item">
              <el-icon color="#f56c6c"><InfoFilled /></el-icon>
              <span>定期备份数据防止丢失</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="24" :md="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统说明</span>
            </div>
          </template>
          <div class="system-info">
            <p><strong>学习流程：</strong></p>
            <ol>
              <li>导入词库 - 上传CSV格式的单词文件</li>
              <li>创建学习组 - 选择学习范围和单词数量</li>
              <li>开始学习 - 听写单词，系统自动判定</li>
              <li>复习巩固 - 按记忆曲线自动安排复习</li>
            </ol>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { bankAPI, groupAPI, reviewAPI } from '../api'
import { useResponsive } from '../composables/useResponsive'
import { 
  Collection, 
  FolderOpened, 
  Calendar, 
  Trophy, 
  Plus, 
  VideoPlay, 
  RefreshRight, 
  Download,
  InfoFilled
} from '@element-plus/icons-vue'

const router = useRouter()
const { isMobile } = useResponsive()

const stats = ref({
  banks: 0,
  groups: 0,
  todayReview: 0,
  completed: 0
})

onMounted(async () => {
  await loadStats()
})

const loadStats = async () => {
  try {
    const [banksRes, groupsRes, reviewRes] = await Promise.all([
      bankAPI.getAll(),
      groupAPI.getAll(),
      reviewAPI.getToday()
    ])
    
    const banks = Array.isArray(banksRes.data) ? banksRes.data : []
    const groups = Array.isArray(groupsRes.data) ? groupsRes.data : []
    const reviews = Array.isArray(reviewRes.data) ? reviewRes.data : []
    
    stats.value.banks = banks.length
    stats.value.groups = groups.length
    stats.value.todayReview = reviews.length
    stats.value.completed = groups.filter((g: any) => g.status === 'completed').length
  } catch (error) {
    console.error('加载统计数据失败', error)
  }
}

const goToBanks = () => router.push('/banks')
const goToGroups = () => router.push('/groups')
const goToReview = () => router.push('/review')
const goToBackup = () => router.push('/backup')
</script>

<style scoped lang="scss">
.dashboard-container {
  padding: 0;
}

.stats-row {
  margin-bottom: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 16px;
  margin-bottom: 12px;
  
  :deep(.el-card__body) {
    padding: 0;
    display: flex;
    align-items: center;
    width: 100%;
  }
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
}

.action-row {
  margin-bottom: 12px;
}

.card-header {
  font-weight: bold;
  font-size: 16px;
}

.quick-actions {
  display: flex;
  justify-content: space-around;
  padding: 10px 0;
}

.action-item {
  text-align: center;
  cursor: pointer;
  padding: 12px 8px;
  border-radius: 12px;
  transition: all 0.3s;
  flex: 1;
  max-width: 100px;
  
  &:active {
    transform: scale(0.95);
    background-color: #f5f7fa;
  }
  
  &:hover {
    background-color: #f5f7fa;
  }
}

.action-icon-large {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 8px;
}

.action-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.action-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.info-row {
  .el-col {
    margin-bottom: 12px;
  }
}

.tips-list {
  padding: 5px 0;
}

.tip-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
  font-size: 14px;
  
  &:last-child {
    border-bottom: none;
  }
  
  span {
    color: #606266;
  }
}

.system-info {
  color: #606266;
  line-height: 1.8;
  font-size: 14px;
  
  ol {
    padding-left: 18px;
    margin: 8px 0;
  }
  
  li {
    margin: 6px 0;
  }
}

// 桌面端样式
@media (min-width: 768px) {
  .stats-row {
    margin-bottom: 20px;
  }
  
  .stat-card {
    margin-bottom: 0;
    padding: 20px;
    
    :deep(.el-card__body) {
      padding: 0;
    }
  }
  
  .stat-icon {
    width: 64px;
    height: 64px;
    margin-right: 16px;
  }
  
  .stat-value {
    font-size: 28px;
  }
  
  .stat-label {
    font-size: 14px;
    margin-top: 4px;
  }
  
  .action-row {
    margin-bottom: 20px;
  }
  
  .quick-actions {
    padding: 20px 0;
  }
  
  .action-item {
    padding: 20px;
    max-width: 120px;
    
    &:hover {
      transform: translateY(-4px);
    }
  }
  
  .action-icon-large {
    width: 80px;
    height: 80px;
    margin-bottom: 16px;
  }
  
  .action-title {
    font-size: 16px;
    margin-bottom: 4px;
  }
  
  .info-row .el-col {
    margin-bottom: 0;
  }
}

// 横屏优化
@media (orientation: landscape) and (max-width: 1024px) {
  .stat-card {
    padding: 12px;
  }
  
  .stat-icon {
    width: 40px;
    height: 40px;
  }
  
  .action-item {
    padding: 10px;
  }
  
  .action-icon-large {
    width: 48px;
    height: 48px;
  }
}
</style>
