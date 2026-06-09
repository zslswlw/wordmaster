<template>
  <div class="page">
    <div class="page-top">
      <h2>音频管理</h2>
      <el-button type="primary" size="small" :loading="syncing" @click="startSync">
        <el-icon><Download /></el-icon> 同步音频
      </el-button>
    </div>

    <div class="stat-row">
      <div class="stat"><span class="sv">{{ status.total_words }}</span><span class="sl">总单词</span></div>
      <div class="stat green"><span class="sv">{{ status.has_audio }}</span><span class="sl">已有音频</span></div>
      <div class="stat red"><span class="sv">{{ status.missing }}</span><span class="sl">缺失</span></div>
    </div>

    <div class="prog-section">
      <div class="prog-top"><span>覆盖率</span><span class="prog-pct">{{ status.coverage }}</span></div>
      <div class="prog-track"><div class="prog-fill" :style="{ width: pct + '%' }"></div></div>
    </div>

    <div v-if="status.missing_sample?.length" class="section">
      <h3 class="sec-title">缺失音频（前10）</h3>
      <div class="tags">
        <span v-for="w in status.missing_sample" :key="w" class="tag">{{ w }}</span>
      </div>
    </div>

    <div class="section">
      <h3 class="sec-title">快捷操作</h3>
      <div class="actions">
        <button class="act" @click="checkSpecificWord"><el-icon><Search /></el-icon> 检查单词</button>
        <button class="act" @click="refreshStatus"><el-icon><Refresh /></el-icon> 刷新</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Search, Refresh } from '@element-plus/icons-vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

interface AudioStatus { total_words: number; has_audio: number; missing: number; coverage: string; audio_dir: string; missing_sample: string[] }

const router = useRouter()
const { isAdmin } = useAuth()

const status = ref<AudioStatus>({ total_words: 0, has_audio: 0, missing: 0, coverage: '0%', audio_dir: '', missing_sample: [] })
const syncing = ref(false)

const pct = computed(() => status.value.total_words === 0 ? 0 : Math.round((status.value.has_audio / status.value.total_words) * 100))

const fetchStatus = async () => {
  try {
    const token = localStorage.getItem('token')
    const r = await axios.get('/api/audio/status', { headers: { Authorization: `Bearer ${token}` } })
    status.value = r.data
  } catch { ElMessage.error('获取状态失败') }
}

const startSync = async () => {
  syncing.value = true
  try {
    const token = localStorage.getItem('token')
    await axios.post('/api/audio/sync', {}, { headers: { Authorization: `Bearer ${token}` } })
    ElMessage.success('同步已启动，请稍后刷新')
  } catch { ElMessage.error('启动同步失败') }
  finally { syncing.value = false }
}

const checkSpecificWord = async () => {
  try {
    const { value: word } = await ElMessageBox.prompt('请输入要检查的单词', '检查单词', { confirmButtonText: '检查', cancelButtonText: '取消', inputPattern: /\S+/, inputErrorMessage: '请输入单词' })
    const token = localStorage.getItem('token')
    const r = await axios.get(`/api/audio/check/${word}`, { headers: { Authorization: `Bearer ${token}` } })
    if (r.data.exists) ElMessage.success(`"${word}" 已有音频`)
    else {
      ElMessage.warning(`"${word}" 缺少音频`)
      try {
        await ElMessageBox.confirm(`是否下载"${word}"的音频？`, '下载', { confirmButtonText: '下载' })
        await axios.post(`/api/audio/sync-word/${word}`, {}, { headers: { Authorization: `Bearer ${token}` } })
        ElMessage.success('下载成功'); fetchStatus()
      } catch { /* cancel */ }
    }
  } catch { /* cancel */ }
}

const refreshStatus = () => { fetchStatus(); ElMessage.success('已刷新') }

onMounted(() => {
  if (!isAdmin.value) { router.replace('/dashboard'); return }
  fetchStatus()
})
</script>

<style scoped lang="scss">
.page { max-width: 720px; margin: 0 auto; }
.page-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;
  h2 { font-size: 1.125rem; font-weight: 700; color: var(--color-text-primary); margin: 0; }
}

.stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; }
.stat { text-align: center; padding: 16px; background: var(--color-bg-paper); border: 1px solid var(--color-border-light); border-radius: 8px; }
.sv { display: block; font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary); }
.sl { display: block; font-size: 0.6875rem; color: var(--color-text-muted); margin-top: 2px; }
.green .sv { color: var(--color-success); }
.red .sv { color: var(--color-danger); }

.prog-section { margin-bottom: 24px; }
.prog-top { display: flex; justify-content: space-between; font-size: 0.8125rem; color: var(--color-text-muted); margin-bottom: 6px; }
.prog-pct { font-weight: 600; color: var(--color-text-primary); }
.prog-track { height: 4px; background: var(--color-border-light); border-radius: 2px; overflow: hidden; }
.prog-fill { height: 100%; background: var(--color-text-primary); transition: width 0.3s; }

.section { margin-bottom: 24px; }
.sec-title { font-size: 0.8125rem; font-weight: 600; color: var(--color-text-muted); margin: 0 0 10px; text-transform: uppercase; letter-spacing: 0.05em; }

.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { padding: 4px 10px; background: rgba(var(--color-danger-rgb), 0.08); color: var(--color-danger); border-radius: 4px; font-size: 0.75rem; }

.actions { display: flex; gap: 8px; }
.act {
  display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
  background: var(--color-bg-paper); border: 1px solid var(--color-border); border-radius: 6px;
  font-size: 0.8125rem; color: var(--color-text-secondary); cursor: pointer;
  &:hover { background: var(--color-bg-muted); }
}
</style>
