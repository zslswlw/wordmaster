<template>
  <div class="admin-page">
    <div class="page-top">
      <h2>管理</h2>
    </div>

    <el-tabs v-model="activeTab" class="admin-tabs">
      <el-tab-pane name="banks" label="词库" />
      <el-tab-pane name="ai" label="AI 配置" />
      <el-tab-pane name="audio" label="音频" />
    </el-tabs>

    <div class="tab-content">
      <KeepAlive>
        <component :is="currentTab" :key="activeTab" />
      </KeepAlive>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import BanksView from './Banks.vue'
import SettingsView from './Settings.vue'
import AudioManageView from './AudioManage.vue'

const router = useRouter()
const { isAdmin } = useAuth()
const activeTab = ref('banks')

const currentTab = computed(() => {
  const map: Record<string, any> = { banks: BanksView, ai: SettingsView, audio: AudioManageView }
  return map[activeTab.value]
})

onMounted(() => {
  if (!isAdmin.value) { router.replace('/dashboard') }
})
</script>

<style scoped lang="scss">
.admin-page {
  max-width: 780px;
  margin: 0 auto;
}
.page-top {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;
  h2 { font-size: 1.125rem; font-weight: 700; color: var(--color-text-primary); margin: 0; }
}
.admin-tabs {
  margin-bottom: 0;
  :deep(.el-tabs__header) { margin-bottom: 16px; }
}
.tab-content {
  min-height: 400px;
}
</style>
