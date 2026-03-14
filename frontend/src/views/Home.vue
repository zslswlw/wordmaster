<template>
  <div class="home-container">
    <el-container>
      <el-aside width="200px">
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
        </el-menu>
      </el-aside>
      <el-container>
        <el-header>
          <div class="header-left">
            <el-breadcrumb separator="/">
              <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
              <el-breadcrumb-item v-if="currentRoute.meta?.title">{{ currentRoute.meta.title }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          <div class="header-right">
            <span>欢迎, {{ username }}</span>
            <el-button type="danger" size="small" @click="handleLogout">退出</el-button>
          </div>
        </el-header>
        <el-main>
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
import { HomeFilled, Collection, FolderOpened, Calendar, Download } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
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

const handleLogout = () => {
  localStorage.removeItem('token')
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.home-container {
  height: 100vh;
}

.el-container {
  height: 100%;
}

.el-aside {
  background-color: #304156;
}

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
}

.el-menu-item:hover,
.el-menu-item.is-active {
  background-color: #263445 !important;
  color: #409eff !important;
}

.el-header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
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

.el-main {
  background-color: #f0f2f5;
  padding: 20px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
