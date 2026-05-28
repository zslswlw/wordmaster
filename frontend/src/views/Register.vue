<template>
  <div class="register-page">
    <div class="register-box">
      <div class="brand">
        <h1>创建账号</h1>
        <p>开始你的词汇学习之旅</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="register-form">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="3-20个字符" size="large" class="t-input" @keyup.enter="handleRegister" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少6个字符" size="large" show-password class="t-input" @keyup.enter="handleRegister" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" placeholder="再次输入密码" size="large" show-password class="t-input" @keyup.enter="handleRegister" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" @click="handleRegister" class="submit-btn">注册</el-button>
        </el-form-item>
        <div class="footer">
          <span>已有账号？</span>
          <el-button link type="primary" @click="goToLogin">立即登录</el-button>
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

const form = reactive({ username: '', password: '', confirmPassword: '' })

const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
  if (!value) callback(new Error('请再次输入密码'))
  else if (value !== form.password) callback(new Error('两次输入的密码不一致'))
  else callback()
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
      await authAPI.register({ username: form.username, password: form.password })
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '注册失败')
    } finally { loading.value = false }
  })
}

const goToLogin = () => router.push('/login')
</script>

<style scoped lang="scss">
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-base);
  padding: 24px;
}

.register-box {
  width: 100%;
  max-width: 380px;
}

.brand {
  text-align: center;
  margin-bottom: 36px;
  h1 { font-size: 1.75rem; font-weight: 700; color: var(--color-text-primary); margin: 0; }
  p { font-size: 0.9375rem; color: var(--color-text-muted); margin: 4px 0 0; }
}

.register-form {
  :deep(.el-form-item__label) { font-weight: 500; color: var(--color-text-secondary); padding-bottom: 6px; }
  :deep(.el-form-item) { margin-bottom: 18px; }
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
  .register-page { padding: 16px; align-items: flex-start; padding-top: 60px; }
}
</style>
