<template>
  <div class="visual-word-card" :class="{ loaded, error: hasError }">
    <div v-if="!loaded && !hasError" class="vcard-placeholder">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
    </div>
    <div v-else-if="hasError" class="vcard-placeholder error">
      <el-icon :size="24"><PictureFilled /></el-icon>
      <span class="vcard-error-text">图片加载失败</span>
    </div>
    <img
      v-show="loaded && !hasError"
      :src="src"
      :alt="alt"
      class="vcard-img"
      @load="onLoad"
      @error="onError"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Loading, PictureFilled } from '@element-plus/icons-vue'

const props = defineProps<{
  src: string
  alt?: string
}>()

const loaded = ref(false)
const hasError = ref(false)

watch(() => props.src, () => {
  loaded.value = false
  hasError.value = false
})

const onLoad = () => { loaded.value = true; hasError.value = false }
const onError = () => { loaded.value = false; hasError.value = true }
</script>

<style scoped lang="scss">
.visual-word-card {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background: var(--color-bg-muted);
  aspect-ratio: 1 / 1;
}

.vcard-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  gap: 6px;

  &.error {
    color: var(--color-text-light);
  }
}

.vcard-error-text {
  font-size: 0.6875rem;
}

.vcard-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
