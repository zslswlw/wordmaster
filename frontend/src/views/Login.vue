<template>
  <div class="login-page">
    <div class="login-box">
      <div class="brand">
        <h1>WordMaster</h1>
        <p>背单词系统</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="login-form">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" size="large" class="t-input" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" size="large" show-password class="t-input" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" @click.prevent="handleLogin" class="submit-btn">
            登录
          </el-button>
        </el-form-item>
        <div class="footer">
          <span>还没有账号？</span>
          <el-button link type="primary" @click="goToRegister">立即注册</el-button>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authAPI } from '../api'

const router = useRouter()
const formRef = ref()
const loading = ref(false)

const form = reactive({ username: '', password: '' })

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
    const { data } = await authAPI.login({ username: form.username, password: form.password })
    localStorage.setItem('token', data.access_token)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (error: any) {
    const msg = error.response?.data?.detail || '登录失败'
    ElMessage.error(msg)
  } finally { loading.value = false }
}

const goToRegister = () => router.push('/register')
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-base);
  padding: 24px;
}

.login-box {
  width: 100%;
  max-width: 380px;
}

.brand {
  text-align: center;
  margin-bottom: 40px;
  h1 { font-size: 1.75rem; font-weight: 700; color: var(--color-text-primary); margin: 0; }
  p { font-size: 0.9375rem; color: var(--color-text-muted); margin: 4px 0 0; }
}

.login-form {
  :deep(.el-form-item__label) { font-weight: 500; color: var(--color-text-secondary); padding-bottom: 6px; }
  :deep(.el-form-item) { margin-bottom: 20px; }
  :deep(.el-input__wrapper) { border-radius: 8px; height: 48px; }
}

.submit-btn {
  width: 100%;
  height: 48px;
  font-size: 1rem;
  font-weight: 600;
  border-radius: 8px;
  background: var(--color-primary);
  border: none;
  &:hover { background: var(--color-primary-hover); }
}

.footer {
  text-align: center;
  margin-top: 24px;
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

@media (max-width: 480px) {
  .login-page { padding: 16px; align-items: flex-start; padding-top: 80px; }
}
</style>
