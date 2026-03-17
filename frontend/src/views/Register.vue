<template>
  <div class="register-container">
    <div class="register-box">
      <div class="register-header">
        <div class="logo-icon">
          <el-icon :size="48" color="#667eea"><Collection /></el-icon>
        </div>
        <h1>注册账号</h1>
        <p>创建您的背单词账户</p>
      </div>
      
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="register-form"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名（3-20个字符）"
            size="large"
            @keyup.enter="handleRegister"
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
            placeholder="请输入密码（至少6个字符）"
            size="large"
            show-password
            @keyup.enter="handleRegister"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            size="large"
            show-password
            @keyup.enter="handleRegister"
          >
            <template #prefix>
              <el-icon><Key /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleRegister"
            class="register-btn"
          >
            注 册
          </el-button>
        </el-form-item>
        
        <div class="register-footer">
          <span>已有账号？</span>
          <el-button link type="primary" @click="goToLogin">
            立即登录
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
import { User, Lock, Key, Collection } from '@element-plus/icons-vue'

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
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.register-box {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.register-header {
  text-align: center;
  margin-bottom: 32px;
  
  .logo-icon {
    width: 80px;
    height: 80px;
    background: linear-gradient(135deg, #667eea20 0%, #764ba220 100%);
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 16px;
  }
  
  h1 {
    margin: 0 0 8px 0;
    font-size: 28px;
    color: #303133;
    font-weight: 600;
  }
  
  p {
    margin: 0;
    color: #909399;
    font-size: 14px;
  }
}

.register-form {
  :deep(.el-form-item__label) {
    font-weight: 500;
    color: #606266;
  }
  
  :deep(.el-input__inner) {
    font-size: 16px; // 防止 iOS 缩放
  }
}

.register-btn {
  width: 100%;
  margin-top: 8px;
  height: 44px;
  font-size: 16px;
  border-radius: 22px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  
  &:hover {
    opacity: 0.9;
  }
}

.register-footer {
  text-align: center;
  margin-top: 24px;
  color: #606266;
  font-size: 14px;
}

// 移动端适配
@media (max-width: 768px) {
  .register-container {
    padding: 16px;
    align-items: flex-start;
    padding-top: 40px;
  }
  
  .register-box {
    padding: 32px 24px;
    border-radius: 12px;
  }
  
  .register-header {
    margin-bottom: 24px;
    
    .logo-icon {
      width: 64px;
      height: 64px;
      border-radius: 16px;
    }
    
    h1 {
      font-size: 24px;
    }
  }
  
  .register-btn {
    height: 48px;
    font-size: 17px;
  }
}

// 手机横屏适配
@media (max-width: 768px) and (orientation: landscape) {
  .register-container {
    padding-top: 16px;
    align-items: center;
  }
  
  .register-box {
    max-width: 400px;
    padding: 20px 24px;
  }
  
  .register-header {
    margin-bottom: 12px;
    
    .logo-icon {
      width: 40px;
      height: 40px;
      margin-bottom: 8px;
      
      :deep(.el-icon) {
        font-size: 24px !important;
      }
    }
    
    h1 {
      font-size: 18px;
      margin-bottom: 4px;
    }
    
    p {
      font-size: 12px;
    }
  }
  
  :deep(.el-form-item) {
    margin-bottom: 8px;
  }
  
  :deep(.el-form-item__label) {
    font-size: 12px;
    line-height: 24px;
    padding-bottom: 4px;
  }
  
  :deep(.el-input__inner) {
    height: 36px;
  }
  
  .register-btn {
    height: 36px;
    margin-top: 4px;
    font-size: 15px;
  }
  
  .register-footer {
    margin-top: 12px;
    font-size: 13px;
  }
}

// 小屏手机适配
@media (max-width: 375px) {
  .register-box {
    padding: 24px 20px;
  }
  
  .register-header h1 {
    font-size: 22px;
  }
}
</style>
