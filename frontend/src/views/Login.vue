<template>
  <div class="login-page">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
      <div class="pattern"></div>
    </div>

    <div class="login-container">
      <!-- 左侧品牌区 -->
      <div class="brand-section">
        <div class="brand-content animate-fade-in-up">
          <div class="logo-wrapper">
            <div class="logo-icon">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                <path d="M24 4L4 14v20l20 10 20-10V14L24 4z" stroke="currentColor" stroke-width="2" fill="none"/>
                <path d="M4 14l20 10m0 0v20m0-20l20-10" stroke="currentColor" stroke-width="2"/>
                <circle cx="24" cy="24" r="6" fill="currentColor"/>
              </svg>
            </div>
          </div>
          <h1 class="brand-title">WordMaster</h1>
          <p class="brand-slogan">掌握词汇，掌控未来</p>
          <div class="decorative-line"></div>
          <p class="brand-desc">
            科学的记忆方法，配合艾宾浩斯遗忘曲线，<br/>
            让背单词变得高效且有趣。
          </p>
        </div>
        <div class="floating-words">
          <span class="word-badge" style="--delay: 0s">CET-6</span>
          <span class="word-badge" style="--delay: 0.5s">Vocabulary</span>
          <span class="word-badge" style="--delay: 1s">Master</span>
        </div>
      </div>

      <!-- 右侧登录表单区 -->
      <div class="form-section">
        <div class="form-card animate-fade-in-scale delay-2">
          <div class="form-header">
            <h2>欢迎回来</h2>
            <p>请登录您的账户继续学习</p>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            class="login-form"
          >
            <el-form-item label="用户名" prop="username">
              <div class="input-wrapper">
                <el-icon class="input-icon"><User /></el-icon>
                <el-input
                  v-model="form.username"
                  placeholder="请输入用户名"
                  size="large"
                  class="custom-input"
                />
              </div>
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <div class="input-wrapper">
                <el-icon class="input-icon"><Lock /></el-icon>
                <el-input
                  v-model="form.password"
                  type="password"
                  placeholder="请输入密码"
                  size="large"
                  show-password
                  class="custom-input"
                />
              </div>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="loading"
                @click.prevent="handleLogin"
                class="login-btn"
              >
                <span v-if="!loading">登 录</span>
                <span v-else>登录中...</span>
              </el-button>
            </el-form-item>

            <div class="form-footer">
              <span>还没有账号？</span>
              <el-button link type="primary" @click="goToRegister" class="register-link">
                立即注册
              </el-button>
            </div>
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authAPI } from '../api'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应在3-20个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6个字符', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const { data } = await authAPI.login({
      username: form.username,
      password: form.password
    })
    localStorage.setItem('token', data.access_token)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (error: any) {
    let errorMsg = '登录失败，请稍后重试'
    if (error.response) {
      if (error.response.status === 401) {
        errorMsg = error.response.data?.detail || '用户名或密码错误'
      } else if (error.response.status === 404) {
        errorMsg = '登录服务不可用，请检查网络连接'
      } else if (error.response.status === 500) {
        errorMsg = '服务器内部错误，请稍后重试'
      } else {
        errorMsg = error.response.data?.detail || `请求失败 (${error.response.status})`
      }
    } else if (error.request) {
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      errorMsg = error.message || '登录失败'
    }

    ElMessage.error(errorMsg)
  } finally {
    loading.value = false
  }
}

const goToRegister = () => {
  router.push('/register')
}
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-base);
  position: relative;
  overflow: hidden;
  padding: 20px;
}

/* 背景装饰 */
.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;

  .circle {
    position: absolute;
    border-radius: 50%;
    opacity: 0.5;
  }

  .circle-1 {
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(var(--color-primary-rgb), 0.08) 0%, transparent 70%);
    top: -100px;
    right: -100px;
    animation: float 8s ease-in-out infinite;
  }

  .circle-2 {
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(212, 160, 60, 0.06) 0%, transparent 70%);
    bottom: -50px;
    left: -50px;
    animation: float 10s ease-in-out infinite reverse;
  }

  .circle-3 {
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, rgba(var(--color-primary-rgb), 0.05) 0%, transparent 70%);
    top: 50%;
    left: 30%;
    animation: float 6s ease-in-out infinite;
  }

  .pattern {
    position: absolute;
    inset: 0;
    background-image:
      radial-gradient(circle at 25% 25%, rgba(var(--color-primary-rgb), 0.03) 0%, transparent 50%),
      radial-gradient(circle at 75% 75%, rgba(212, 160, 60, 0.03) 0%, transparent 50%);
  }
}

.login-container {
  display: flex;
  max-width: 1000px;
  width: 100%;
  background: var(--color-bg-paper);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  overflow: hidden;
  position: relative;
  z-index: 1;
}

/* 左侧品牌区 */
.brand-section {
  flex: 1;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  padding: 48px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
    opacity: 0.5;
  }
}

.brand-content {
  position: relative;
  z-index: 1;
  color: white;
  text-align: center;
}

.logo-wrapper {
  margin-bottom: 24px;
}

.logo-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  backdrop-filter: blur(10px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.brand-title {
  font-family: var(--font-display);
  font-size: 2.5rem;
  font-weight: 700;
  margin-bottom: 8px;
  color: white;
  letter-spacing: -0.02em;
}

.brand-slogan {
  font-size: 1.125rem;
  opacity: 0.9;
  margin-bottom: 24px;
  color: rgba(255, 255, 255, 0.9);
}

.decorative-line {
  width: 60px;
  height: 3px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: var(--radius-full);
  margin: 0 auto 24px;
}

.brand-desc {
  font-size: 0.9375rem;
  line-height: 1.7;
  opacity: 0.8;
  color: rgba(255, 255, 255, 0.85);
}

.floating-words {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 40px;
  position: relative;
  z-index: 1;
}

.word-badge {
  padding: 6px 16px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-full);
  font-size: 0.8125rem;
  font-weight: 500;
  color: white;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  animation: fadeInUp 0.6s ease backwards;
  animation-delay: var(--delay);
}

/* 右侧表单区 */
.form-section {
  flex: 1;
  padding: 48px 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-paper);
}

.form-card {
  width: 100%;
  max-width: 360px;
}

.form-header {
  text-align: center;
  margin-bottom: 32px;

  h2 {
    font-family: var(--font-display);
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 8px;
  }

  p {
    color: var(--color-text-muted);
    font-size: 0.9375rem;
  }
}

.login-form {
  :deep(.el-form-item__label) {
    font-weight: 500;
    color: var(--color-text-secondary);
    padding-bottom: 8px;
  }

  :deep(.el-form-item) {
    margin-bottom: 20px;
  }
}

.input-wrapper {
  position: relative;
  width: 100%;

  .input-icon {
    position: absolute;
    left: 14px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--color-text-muted);
    z-index: 1;
    font-size: 18px;
  }

  :deep(.el-input__wrapper) {
    padding-left: 42px !important;
    height: 48px;
  }

  :deep(.el-input__inner) {
    font-size: 16px;

    &::placeholder {
      color: var(--color-text-light);
    }
  }
}

.login-btn {
  width: 100%;
  height: 48px;
  font-size: 1rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border: none;
  color: white;
  margin-top: 8px;
  box-shadow: 0 4px 16px rgba(var(--color-primary-rgb), 0.3);
  transition: all var(--transition-base);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(var(--color-primary-rgb), 0.4);
  }

  &:active {
    transform: translateY(0);
  }
}

.form-footer {
  text-align: center;
  margin-top: 24px;
  color: var(--color-text-secondary);
  font-size: 0.875rem;

  span {
    color: var(--color-text-muted);
  }
}

.register-link {
  font-weight: 500;
  font-size: 0.875rem;

  &:hover {
    color: var(--color-primary);
  }
}

/* 移动端适配 */
@media (max-width: 768px) {
  .login-container {
    flex-direction: column;
    max-width: 420px;
  }

  .brand-section {
    padding: 40px 32px;

    .brand-title {
      font-size: 2rem;
    }

    .brand-desc {
      display: none;
    }
  }

  .form-section {
    padding: 32px 24px;
  }

  .floating-words {
    margin-top: 24px;
  }
}

/* 横屏适配 */
@media (max-width: 768px) and (orientation: landscape) {
  .login-page {
    padding: 16px;
    align-items: flex-start;
    padding-top: 20px;
  }

  .brand-section {
    padding: 24px 32px;

    .logo-icon {
      width: 48px;
      height: 48px;
    }

    .brand-title {
      font-size: 1.5rem;
      margin-bottom: 4px;
    }

    .brand-slogan {
      font-size: 0.875rem;
      margin-bottom: 12px;
    }

    .floating-words {
      margin-top: 16px;
    }

    .word-badge {
      padding: 4px 12px;
      font-size: 0.75rem;
    }
  }

  .form-section {
    padding: 20px 24px;
  }

  .form-header {
    margin-bottom: 20px;

    h2 {
      font-size: 1.5rem;
    }
  }

  .login-form {
    :deep(.el-form-item) {
      margin-bottom: 12px;
    }
  }
}

/* 小屏手机 */
@media (max-width: 375px) {
  .login-container {
    border-radius: var(--radius-lg);
  }

  .brand-section {
    padding: 32px 24px;
  }

  .form-section {
    padding: 24px 20px;
  }
}
</style>
