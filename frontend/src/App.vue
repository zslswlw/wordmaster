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
#app {
  min-height: 100vh;
  background: var(--color-bg-base);
}

.app-container {
  &.mobile {
    -webkit-tap-highlight-color: transparent;
    -webkit-touch-callout: none;
    user-select: none;
  }
}
</style>
