<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h1>背单词系统</h1>
        <p>高效记忆，轻松学习</p>
      </div>
      
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="login-form"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click.prevent="handleLogin"
            class="login-btn"
          >
            登 录
          </el-button>
        </el-form-item>
        
        <div class="login-footer">
          <span>还没有账号？</span>
          <el-button link type="primary" @click="goToRegister">
            立即注册
          </el-button>
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
    console.error('登录错误详情:', error)
    console.error('错误响应:', error.response)
    console.error('错误请求:', error.request)
    
    let errorMsg = '登录失败，请稍后重试'
    if (error.response) {
      // 服务器返回了错误响应
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
      // 请求已发送但没有收到响应
      errorMsg = '无法连接到服务器，请检查网络连接'
    } else {
      // 请求配置出错
      errorMsg = error.message || '登录失败'
    }
    
    // 使用 nextTick 确保消息在 DOM 更新后显示
    ElMessage.error(errorMsg)
  } finally {
    loading.value = false
  }
}

const goToRegister = () => {
  router.push('/register')
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-box {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  margin: 0 0 8px 0;
  font-size: 28px;
  color: #303133;
  font-weight: 600;
}

.login-header p {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.login-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #606266;
}

.login-btn {
  width: 100%;
  margin-top: 8px;
  height: 44px;
  font-size: 16px;
}

.login-footer {
  text-align: center;
  margin-top: 24px;
  color: #606266;
  font-size: 14px;
}
</style>
