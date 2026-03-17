<template>
  <div class="mobile-tab-bar" v-if="isMobile">
    <div 
      v-for="item in menuItems" 
      :key="item.path"
      class="tab-item"
      :class="{ active: isActive(item.path) }"
      @click="handleClick(item)"
    >
      <el-icon :size="isLandscape ? 18 : 22">
        <component :is="item.icon" />
      </el-icon>
      <span>{{ item.title }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useResponsive } from '../composables/useResponsive'
import { 
  HomeFilled, 
  Collection, 
  FolderOpened, 
  Calendar, 
  Download 
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { isMobile, isLandscape } = useResponsive()

const menuItems = [
  { path: '/dashboard', title: '首页', icon: HomeFilled },
  { path: '/banks', title: '词库', icon: Collection },
  { path: '/groups', title: '学习', icon: FolderOpened },
  { path: '/review', title: '复习', icon: Calendar },
  { path: '/backup', title: '备份', icon: Download },
]

const isActive = (path: string) => {
  if (path === '/dashboard') {
    return route.path === '/dashboard' || route.path === '/'
  }
  return route.path.startsWith(path)
}

const handleClick = (item: typeof menuItems[0]) => {
  router.push(item.path)
}
</script>

<style scoped lang="scss">
.mobile-tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: #fff;
  display: flex;
  justify-content: space-around;
  align-items: center;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.08);
  z-index: 1000;
  padding-bottom: constant(safe-area-inset-bottom);
  padding-bottom: env(safe-area-inset-bottom);
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  
  .el-icon {
    margin-bottom: 2px;
    transition: transform 0.2s;
  }
  
  &.active {
    color: #667eea;
    
    .el-icon {
      transform: scale(1.1);
    }
  }
  
  &:active {
    opacity: 0.7;
  }
}

/* 横屏适配 */
@media (orientation: landscape) and (max-width: 1024px) {
  .mobile-tab-bar {
    height: 48px;
  }
  
  .tab-item {
    flex-direction: row;
    font-size: 13px;
    gap: 6px;
    
    .el-icon {
      margin-bottom: 0;
    }
  }
}
</style>
