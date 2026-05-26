<template>
  <div class="home-container" :class="[deviceType, orientation]">
    <el-container>
      <!-- 桌面端侧边栏 -->
      <el-aside v-if="isDesktop" width="260px" class="desktop-sidebar">
        <div class="sidebar-header">
          <div class="logo">
            <div class="logo-icon">
              <svg width="28" height="28" viewBox="0 0 48 48" fill="none">
                <path d="M24 4L4 14v20l20 10 20-10V14L24 4z" stroke="currentColor" stroke-width="2" fill="none"/>
                <path d="M4 14l20 10m0 0v20m0-20l20-10" stroke="currentColor" stroke-width="2"/>
                <circle cx="24" cy="24" r="6" fill="currentColor"/>
              </svg>
            </div>
            <span class="logo-text">WordMaster</span>
          </div>
        </div>

        <el-menu
          :default-active="activeMenu"
          class="sidebar-menu"
          router
          @select="handleMenuSelect"
        >
          <el-menu-item index="/dashboard">
            <el-icon><HomeFilled /></el-icon>
            <span>首页概览</span>
          </el-menu-item>
          <el-menu-item index="/banks">
            <el-icon><Collection /></el-icon>
            <span>词库管理</span>
          </el-menu-item>
          <el-menu-item index="/groups">
            <el-icon><FolderOpened /></el-icon>
            <span>学习组</span>
          </el-menu-item>
          <el-menu-item index="/review">
            <el-icon><Calendar /></el-icon>
            <span>复习计划</span>
          </el-menu-item>
          <el-menu-item index="/backup">
            <el-icon><Download /></el-icon>
            <span>数据备份</span>
          </el-menu-item>
          <el-menu-item index="/audio">
            <el-icon><Headset /></el-icon>
            <span>音频管理</span>
          </el-menu-item>
        </el-menu>

        <div class="sidebar-footer">
          <div class="user-info">
            <el-avatar :size="36" :icon="UserFilled" class="user-avatar" />
            <div class="user-details">
              <span class="user-name">{{ username }}</span>
              <span class="user-role">学习者</span>
            </div>
          </div>
        </div>
      </el-aside>

      <el-container>
        <!-- 顶部导航栏 -->
        <el-header :class="['app-header', { 'mobile-header': !isDesktop }]">
          <div class="header-left">
            <template v-if="isDesktop">
              <el-breadcrumb separator="/" class="breadcrumb">
                <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
                <el-breadcrumb-item v-if="currentRoute.meta?.title">{{ currentRoute.meta.title }}</el-breadcrumb-item>
              </el-breadcrumb>
            </template>
            <template v-else>
              <span class="mobile-title">{{ currentRoute.meta?.title || 'WordMaster' }}</span>
            </template>
          </div>
          <div class="header-right">
            <template v-if="isDesktop">
              <div class="header-actions">
                <el-button text @click="handleLogout" class="logout-btn">
                  <el-icon><SwitchButton /></el-icon>
                  <span>退出</span>
                </el-button>
              </div>
            </template>
            <template v-else>
              <el-dropdown trigger="click" @command="handleCommand">
                <el-avatar :size="32" :icon="UserFilled" class="user-avatar-mobile" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item disabled>
                      <el-icon><User /></el-icon>
                      {{ username }}
                    </el-dropdown-item>
                    <el-dropdown-item divided command="logout">
                      <el-icon><SwitchButton /></el-icon>
                      退出登录
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </div>
        </el-header>

        <!-- 主内容区 -->
        <el-main :class="['app-main', { 'mobile-main': !isDesktop }]">
          <router-view v-slot="{ Component }">
            <transition name="page-fade" mode="out-in">
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
import { HomeFilled, Collection, FolderOpened, Calendar, Download, UserFilled, Headset, SwitchButton, User } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const { isDesktop, deviceType, orientation } = useResponsive()
const username = ref('')
const activeMenu = ref('/dashboard')

const currentRoute = computed(() => route)

onMounted(async () => {
  try {
    const { data } = await authAPI.me()
    username.value = data.username
  } catch (error) {
    console.error('获取用户信息失败:', error)
  }
  updateActiveMenu()
})

watch(() => route.path, () => {
  updateActiveMenu()
})

const updateActiveMenu = () => {
  const path = route.path
  if (path.startsWith('/banks')) {
    activeMenu.value = '/banks'
  } else if (path.startsWith('/groups')) {
    activeMenu.value = '/groups'
  } else if (path.startsWith('/review') || path.startsWith('/study-review')) {
    activeMenu.value = '/review'
  } else if (path.startsWith('/backup')) {
    activeMenu.value = '/backup'
  } else if (path.startsWith('/study')) {
    activeMenu.value = '/groups'
  } else {
    activeMenu.value = '/dashboard'
  }
}

const handleMenuSelect = (index: string) => {
  router.push(index)
}

const handleCommand = (command: string) => {
  if (command === 'logout') {
    handleLogout()
  }
}

const handleLogout = () => {
  localStorage.removeItem('token')
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped lang="scss">
.home-container {
  height: 100vh;

  &.mobile, &.tablet {
    .el-container {
      background: var(--color-bg-base);
    }
  }
}

.el-container {
  height: 100%;
}

/* 桌面端侧边栏 */
.desktop-sidebar {
  background: linear-gradient(180deg, #1a2428 0%, #242d31 100%);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image: url("data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23ffffff' fill-opacity='0.02' fill-rule='evenodd'%3E%3Cpath d='M0 40L40 0H20L0 20M40 40V20L20 40'/%3E%3C/g%3E%3C/svg%3E");
    pointer-events: none;
  }
}

.sidebar-header {
  padding: 24px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  position: relative;
  z-index: 1;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  width: 44px;
  height: 44px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 4px 12px rgba(var(--color-primary-rgb), 0.3);
}

.logo-text {
  font-family: var(--font-display);
  font-size: 1.375rem;
  font-weight: 600;
  color: white;
  letter-spacing: -0.01em;
}

.sidebar-menu {
  flex: 1;
  background: transparent;
  border-right: none;
  padding: 16px 12px;
  position: relative;
  z-index: 1;

  :deep(.el-menu-item) {
    height: 48px;
    line-height: 48px;
    margin-bottom: 4px;
    border-radius: var(--radius-md);
    color: rgba(255, 255, 255, 0.65);
    font-size: 0.9375rem;
    transition: all var(--transition-fast);

    &:hover {
      background: rgba(255, 255, 255, 0.06);
      color: rgba(255, 255, 255, 0.9);
    }

    &.is-active {
      background: linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.3) 0%, rgba(var(--color-primary-rgb), 0.2) 100%);
      color: white;
      font-weight: 500;

      .el-icon {
        color: var(--color-primary-light);
      }
    }

    .el-icon {
      margin-right: 12px;
      font-size: 18px;
    }
  }
}

.sidebar-footer {
  padding: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  position: relative;
  z-index: 1;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-avatar {
  background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-light) 100%);
  color: white;
  flex-shrink: 0;
}

.user-details {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  color: white;
  font-size: 0.9375rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.75rem;
}

/* 顶部导航栏 */
.app-header {
  background: var(--color-bg-paper);
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 64px;
  border-bottom: 1px solid var(--color-border-light);
  position: sticky;
  top: 0;
  z-index: 100;

  &.mobile-header {
    padding: 0 16px;
    height: 56px;

    .mobile-title {
      font-family: var(--font-display);
      font-size: 1.125rem;
      font-weight: 600;
      color: var(--color-text-primary);
    }

    .user-avatar-mobile {
      background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
      color: white;
      cursor: pointer;
    }
  }
}

.header-left {
  display: flex;
  align-items: center;
}

.breadcrumb {
  :deep(.el-breadcrumb__item) {
    font-size: 0.875rem;

    .el-breadcrumb__inner {
      color: var(--color-text-muted);

      &.is-link:hover {
        color: var(--color-primary);
      }
    }

    &:last-child .el-breadcrumb__inner {
      color: var(--color-text-primary);
      font-weight: 500;
    }
  }
}

.header-right {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logout-btn {
  color: var(--color-text-muted);
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);

  &:hover {
    background: var(--color-bg-muted);
    color: var(--color-danger);
  }

  .el-icon {
    font-size: 16px;
  }
}

/* 主内容区 */
.app-main {
  background: var(--color-bg-base);
  padding: 24px;
  min-height: calc(100vh - 64px);

  &.mobile-main {
    padding: 16px;
    padding-bottom: 80px;
    min-height: calc(100vh - 56px);
  }
}

/* 横屏优化 */
@media (orientation: landscape) and (max-width: 1024px) {
  .app-main.mobile-main {
    padding-bottom: 60px;
  }
}

/* 页面切换动画 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
