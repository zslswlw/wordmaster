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
@import './styles/aesthetic.css';

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-body);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  min-height: 100vh;
  background: var(--color-bg-base);
}

.app-container {
  min-height: 100vh;

  &.mobile {
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
    border-radius: var(--radius-xl) !important;
  }

  .el-message-box {
    width: 90% !important;
    border-radius: var(--radius-lg) !important;
  }

  .el-table {
    font-size: 14px;
  }

  .el-form-item__label {
    font-size: 14px;
  }

  .el-input__inner {
    font-size: 16px;
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
