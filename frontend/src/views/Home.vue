<template>
  <div class="home" :class="[deviceType, orientation]">
    <el-container>
      <el-aside v-if="isDesktop" width="220px" class="sidebar">
        <div class="sb-logo">
          <span class="sb-brand">WordMaster</span>
        </div>

        <el-menu :default-active="activeMenu" class="sb-menu" router @select="handleMenuSelect">
          <el-menu-item index="/dashboard"><el-icon><HomeFilled /></el-icon><span>首页概览</span></el-menu-item>
          <el-menu-item index="/groups"><el-icon><FolderOpened /></el-icon><span>学习组</span></el-menu-item>
          <el-menu-item index="/review"><el-icon><Calendar /></el-icon><span>复习计划</span></el-menu-item>
          <el-menu-item v-if="isAdmin" index="/backup"><el-icon><Download /></el-icon><span>数据备份</span></el-menu-item>
          <el-menu-item v-if="isAdmin" index="/admin"><el-icon><Setting /></el-icon><span>管理</span></el-menu-item>
        </el-menu>

        <div class="sb-footer">
          <el-avatar :size="32" :icon="UserFilled" class="sb-avatar" />
          <div class="sb-user">
            <span class="sb-name">{{ username }}</span>
            <button class="sb-logout" @click="handleLogout">退出</button>
          </div>
        </div>
      </el-aside>

      <el-container>
        <el-header :class="['topbar', { 'topbar-mobile': !isDesktop }]">
          <template v-if="isDesktop">
            <el-breadcrumb separator="/" class="breadcrumb">
              <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
              <el-breadcrumb-item v-if="currentRoute.meta?.title">{{ currentRoute.meta.title }}</el-breadcrumb-item>
            </el-breadcrumb>
            <button class="tb-logout" @click="handleLogout">退出</button>
          </template>
          <template v-else>
            <span class="tb-title">{{ currentRoute.meta?.title || 'WordMaster' }}</span>
            <el-dropdown trigger="click" @command="handleCommand">
              <el-avatar :size="28" :icon="UserFilled" class="tb-avatar" />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item disabled>{{ username }}</el-dropdown-item>
                  <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-header>

        <el-main :class="['main', { 'main-mobile': !isDesktop }]">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authAPI } from '../api'
import { useResponsive } from '../composables/useResponsive'
import { useAuth } from '../composables/useAuth'
import { HomeFilled, FolderOpened, Calendar, Download, UserFilled, Setting } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const { isDesktop, deviceType, orientation } = useResponsive()
const { isAdmin, setRole, clearAuth } = useAuth()
const username = ref('')
const activeMenu = ref('/dashboard')

const currentRoute = computed(() => route)

const updateActiveMenu = () => {
  const path = route.path
  if (path.startsWith('/admin')) activeMenu.value = '/admin'
  else if (path.startsWith('/groups')) activeMenu.value = '/groups'
  else if (path.startsWith('/review') || path.startsWith('/study-review')) activeMenu.value = '/review'
  else if (path.startsWith('/backup')) activeMenu.value = '/backup'
  else if (path.startsWith('/study')) activeMenu.value = '/groups'
  else activeMenu.value = '/dashboard'
}

onMounted(async () => {
  try {
    const { data } = await authAPI.me()
    username.value = data.username
    setRole(data.role || 'user')
  } catch { /* ignore */ }
  updateActiveMenu()
})

watch(() => route.path, updateActiveMenu)

const handleMenuSelect = (index: string) => router.push(index)
const handleCommand = (cmd: string) => { if (cmd === 'logout') handleLogout() }

const handleLogout = () => {
  clearAuth()
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped lang="scss">
.home { height: 100vh; }

// sidebar
.sidebar {
  background: #1a1f23;
  display: flex; flex-direction: column;
}

.sb-logo {
  padding: 20px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.sb-brand {
  font-size: 1.125rem; font-weight: 700; color: #fff;
}

.sb-menu {
  flex: 1;
  background: transparent;
  border-right: none;
  padding: 12px 8px;
  :deep(.el-menu-item) {
    height: 44px; line-height: 44px; margin-bottom: 2px; border-radius: 6px;
    color: rgba(255,255,255,0.55); font-size: 0.875rem;
    &:hover { background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.8); }
    &.is-active { background: rgba(255,255,255,0.08); color: #fff; font-weight: 500; }
  }
}

.sb-footer {
  padding: 16px; border-top: 1px solid rgba(255,255,255,0.06);
  display: flex; align-items: center; gap: 10px;
}
.sb-avatar { background: #555; color: #fff; }
.sb-user { display: flex; flex-direction: column; min-width: 0; }
.sb-name { color: #fff; font-size: 0.8125rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sb-logout { background: none; border: none; color: rgba(255,255,255,0.35); font-size: 0.6875rem; cursor: pointer; padding: 0; text-align: left; &:hover { color: rgba(255,255,255,0.6); } }

// topbar
.topbar {
  background: var(--color-bg-paper);
  border-bottom: 1px solid var(--color-border-light);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 56px;

  &.topbar-mobile {
    padding: 0 16px; height: 48px;
    .tb-title { font-size: 1rem; font-weight: 600; color: var(--color-text-primary); }
    .tb-avatar { cursor: pointer; background: var(--color-text-muted); color: #fff; }
  }
}

.breadcrumb { font-size: 0.8125rem; }

.tb-logout {
  background: none; border: none; color: var(--color-text-muted); font-size: 0.8125rem; cursor: pointer;
  &:hover { color: var(--color-danger); }
}

// main
.main {
  background: var(--color-bg-base);
  padding: 16px;
  min-height: calc(100vh - 56px);
  &.main-mobile { padding: 12px; padding-bottom: 80px; min-height: calc(100vh - 48px); }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
