import { ref, computed, onMounted, onUnmounted } from 'vue'

// 断点定义
const breakpoints = {
  xs: 0,
  sm: 576,
  md: 768,
  lg: 992,
  xl: 1200,
  xxl: 1400
}

// 设备类型
export type DeviceType = 'mobile' | 'tablet' | 'desktop'

// 方向类型
export type Orientation = 'portrait' | 'landscape'

export function useResponsive() {
  // 视口尺寸
  const viewportWidth = ref(window.innerWidth)
  const viewportHeight = ref(window.innerHeight)
  
  // 计算属性
  const isMobile = computed(() => viewportWidth.value < breakpoints.md)
  const isTablet = computed(() => viewportWidth.value >= breakpoints.md && viewportWidth.value < breakpoints.lg)
  const isDesktop = computed(() => viewportWidth.value >= breakpoints.lg)
  
  const deviceType = computed<DeviceType>(() => {
    if (isMobile.value) return 'mobile'
    if (isTablet.value) return 'tablet'
    return 'desktop'
  })
  
  const orientation = computed<Orientation>(() => {
    return viewportWidth.value > viewportHeight.value ? 'landscape' : 'portrait'
  })
  
  const isLandscape = computed(() => orientation.value === 'landscape')
  const isPortrait = computed(() => orientation.value === 'portrait')
  
  // 是否是手机横屏
  const isMobileLandscape = computed(() => isMobile.value && isLandscape.value)
  // 是否是平板横屏
  const isTabletLandscape = computed(() => isTablet.value && isLandscape.value)
  
  // 断点检查
  const isGreaterThan = (bp: keyof typeof breakpoints) => viewportWidth.value >= breakpoints[bp]
  const isLessThan = (bp: keyof typeof breakpoints) => viewportWidth.value < breakpoints[bp]
  
  // 更新尺寸
  const updateSize = () => {
    viewportWidth.value = window.innerWidth
    viewportHeight.value = window.innerHeight
  }
  
  // 监听窗口变化
  onMounted(() => {
    window.addEventListener('resize', updateSize)
    window.addEventListener('orientationchange', updateSize)
  })
  
  onUnmounted(() => {
    window.removeEventListener('resize', updateSize)
    window.removeEventListener('orientationchange', updateSize)
  })
  
  return {
    viewportWidth,
    viewportHeight,
    isMobile,
    isTablet,
    isDesktop,
    deviceType,
    orientation,
    isLandscape,
    isPortrait,
    isMobileLandscape,
    isTabletLandscape,
    isGreaterThan,
    isLessThan
  }
}
