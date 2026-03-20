<template>
  <div class="home-container" :class="[deviceType, orientation]">
    <el-container>
      <!-- 桌面端侧边栏 -->
      <el-aside v-if="isDesktop" width="200px" class="desktop-sidebar">
        <div class="logo">背单词系统</div>
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical"
          router
          @select="handleMenuSelect"
        >
          <el-menu-item index="/dashboard">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
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
      </el-aside>
      
      <el-container>
        <!-- 顶部导航栏 -->
        <el-header :class="['app-header', { 'mobile-header': !isDesktop }]">
          <div class="header-left">
            <template v-if="isDesktop">
              <el-breadcrumb separator="/">
                <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
                <el-breadcrumb-item v-if="currentRoute.meta?.title">{{ currentRoute.meta.title }}</el-breadcrumb-item>
              </el-breadcrumb>
            </template>
            <template v-else>
              <span class="mobile-title">{{ currentRoute.meta?.title || '背单词系统' }}</span>
            </template>
          </div>
          <div class="header-right">
            <template v-if="isDesktop">
              <span>欢迎, {{ username }}</span>
              <el-button type="danger" size="small" @click="handleLogout">退出</el-button>
            </template>
            <template v-else>
              <el-dropdown trigger="click" @command="handleCommand">
                <el-avatar :size="32" :icon="UserFilled" class="user-avatar" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item disabled>{{ username }}</el-dropdown-item>
                    <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </div>
        </el-header>
        
        <!-- 主内容区 -->
        <el-main :class="['app-main', { 'mobile-main': !isDesktop }]">
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
import { HomeFilled, Collection, FolderOpened, Calendar, Download, UserFilled, Headset } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const { isDesktop, deviceType, orientation } = useResponsive()
const username = ref('')
const activeMenu = ref('/home')

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
      background: #f5f7fa;
    }
  }
}

.el-container {
  height: 100%;
}

// 桌面端侧边栏
.desktop-sidebar {
  background-color: #304156;
  
  .logo {
    height: 60px;
    line-height: 60px;
    text-align: center;
    color: #fff;
    font-size: 20px;
    font-weight: bold;
    border-bottom: 1px solid #1f2d3d;
  }
  
  .el-menu-vertical {
    border-right: none;
    background-color: #304156;
  }
  
  .el-menu-item {
    color: #bfcbd9;
    
    &:hover,
    &.is-active {
      background-color: #263445 !important;
      color: #409eff !important;
    }
  }
}

// 顶部导航栏
.app-header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  
  &.mobile-header {
    padding: 0 16px;
    height: 44px;
    position: sticky;
    top: 0;
    z-index: 100;
    
    .mobile-title {
      font-size: 17px;
      font-weight: 600;
      color: #333;
    }
    
    .user-avatar {
      cursor: pointer;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
  }
}

.header-left {
  display: flex;
  align-items: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

// 主内容区
.app-main {
  background-color: #f0f2f5;
  padding: 20px;
  
  &.mobile-main {
    padding: 12px;
    padding-bottom: 68px; // 为底部导航栏预留空间
    background: #f5f7fa;
    min-height: calc(100vh - 44px);
  }
}

// 横屏优化
@media (orientation: landscape) and (max-width: 1024px) {
  .app-main.mobile-main {
    padding-bottom: 60px; // 横屏时底部导航栏较矮
  }
}

// 页面切换动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
