<template>
  <div id="app" :class="['app-container', deviceType, orientation]">
    <router-view />
    <MobileTabBar />
  </div>
</template>

<script setup lang="ts">
import MobileTabBar from './components/MobileTabBar.vue'
import { useResponsive } from './composables/useResponsive'

const { deviceType, orientation } = useResponsive()
</script>

<style lang="scss">
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.app-container {
  &.mobile {
    // 移动端优化
    -webkit-tap-highlight-color: transparent;
    -webkit-touch-callout: none;
    user-select: none;
  }
}

// Element Plus 移动端适配
@media (max-width: 768px) {
  .el-dialog {
    width: 90% !important;
    margin: 10vh auto !important;
    max-height: 80vh;
    overflow-y: auto;
  }
  
  .el-message-box {
    width: 90% !important;
  }
  
  .el-table {
    font-size: 14px;
  }
  
  .el-form-item__label {
    font-size: 14px;
  }
  
  .el-input__inner {
    font-size: 16px; // 防止 iOS 缩放
  }
}

// 横屏优化
@media (orientation: landscape) and (max-width: 1024px) {
  .el-dialog {
    max-height: 90vh;
    margin: 5vh auto !important;
  }
}
</style>
