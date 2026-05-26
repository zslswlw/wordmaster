<template>
  <div class="register-page">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>

    <div class="register-container">
      <div class="form-card animate-fade-in-scale">
        <div class="form-header">
          <div class="logo-wrapper">
            <div class="logo-icon">
              <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
                <path d="M24 4L4 14v20l20 10 20-10V14L24 4z" stroke="currentColor" stroke-width="2" fill="none"/>
                <path d="M4 14l20 10m0 0v20m0-20l20-10" stroke="currentColor" stroke-width="2"/>
                <circle cx="24" cy="24" r="6" fill="currentColor"/>
              </svg>
            </div>
          </div>
          <h2>创建账号</h2>
          <p>开始您的词汇学习之旅</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          class="register-form"
        >
          <el-form-item label="用户名" prop="username">
            <div class="input-wrapper">
              <el-icon class="input-icon"><User /></el-icon>
              <el-input
                v-model="form.username"
                placeholder="请输入用户名（3-20个字符）"
                size="large"
                @keyup.enter="handleRegister"
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
                placeholder="请输入密码（至少6个字符）"
                size="large"
                show-password
                @keyup.enter="handleRegister"
                class="custom-input"
              />
            </div>
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <div class="input-wrapper">
              <el-icon class="input-icon"><Key /></el-icon>
              <el-input
                v-model="form.confirmPassword"
                type="password"
                placeholder="请再次输入密码"
                size="large"
                show-password
                @keyup.enter="handleRegister"
                class="custom-input"
              />
            </div>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              @click="handleRegister"
              class="register-btn"
            >
              <span v-if="!loading">创建账号</span>
              <span v-else>注册中...</span>
            </el-button>
          </el-form-item>

          <div class="form-footer">
            <span>已有账号？</span>
            <el-button link type="primary" @click="goToLogin" class="login-link">
              立即登录
            </el-button>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authAPI } from '../api'
import { User, Lock, Key } from '@element-plus/icons-vue'

const router = useRouter()
const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error('请再次输入密码'))
  } else if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应在3-20个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleRegister = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    loading.value = true
    try {
      await authAPI.register({
        username: form.username,
        password: form.password
      })
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } catch (error: any) {
      console.error('注册错误详情:', error)
      console.error('错误响应:', error.response)
      console.error('错误请求:', error.request)
      const errorMsg = error.response?.data?.detail || error.message || '注册失败'
      ElMessage.error(errorMsg)
    } finally {
      loading.value = false
    }
  })
}

const goToLogin = () => {
  router.push('/login')
}
</script>

<style scoped lang="scss">
.register-page {
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
    background: radial-gradient(circle, rgba(212, 160, 60, 0.08) 0%, transparent 70%);
    top: -100px;
    left: -100px;
    animation: float 8s ease-in-out infinite;
  }

  .circle-2 {
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(var(--color-primary-rgb), 0.06) 0%, transparent 70%);
    bottom: -50px;
    right: -50px;
    animation: float 10s ease-in-out infinite reverse;
  }

  .circle-3 {
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, rgba(var(--color-primary-rgb), 0.05) 0%, transparent 70%);
    top: 40%;
    right: 20%;
    animation: float 6s ease-in-out infinite;
  }
}

.register-container {
  display: flex;
  max-width: 440px;
  width: 100%;
  position: relative;
  z-index: 1;
}

.form-card {
  width: 100%;
  background: var(--color-bg-paper);
  border-radius: var(--radius-xl);
  padding: 40px;
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--color-border-light);
}

.form-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo-wrapper {
  margin-bottom: 20px;
}

.logo-icon {
  width: 72px;
  height: 72px;
  margin: 0 auto;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 8px 32px rgba(var(--color-primary-rgb), 0.25);
}

.form-header h2 {
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.form-header p {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.register-form {
  :deep(.el-form-item__label) {
    font-weight: 500;
    color: var(--color-text-secondary);
    padding-bottom: 8px;
  }

  :deep(.el-form-item) {
    margin-bottom: 16px;
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

.register-btn {
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

.login-link {
  font-weight: 500;
  font-size: 0.875rem;

  &:hover {
    color: var(--color-primary);
  }
}

/* 移动端适配 */
@media (max-width: 768px) {
  .register-page {
    padding: 16px;
    align-items: flex-start;
    padding-top: 40px;
  }

  .form-card {
    padding: 32px 24px;
  }

  .logo-icon {
    width: 64px;
    height: 64px;
  }

  .form-header h2 {
    font-size: 1.375rem;
  }

  .register-btn {
    height: 48px;
    font-size: 1rem;
  }
}

/* 横屏适配 */
@media (max-width: 768px) and (orientation: landscape) {
  .register-page {
    padding-top: 16px;
    align-items: center;
  }

  .form-card {
    max-width: 400px;
    padding: 24px;
  }

  .logo-icon {
    width: 48px;
    height: 48px;
  }

  .form-header {
    margin-bottom: 16px;

    h2 {
      font-size: 1.25rem;
    }

    p {
      font-size: 0.8125rem;
    }
  }

  .register-form {
    :deep(.el-form-item) {
      margin-bottom: 12px;
    }
  }
}

/* 小屏手机 */
@media (max-width: 375px) {
  .form-card {
    padding: 24px 20px;
  }
}
</style>
