<template>
  <div class="login-wrap">
    <div class="login-hero">
      <div class="hero-content">
        <div class="hero-badge">
          <el-icon size="28" style="color: #fff"><FirstAidKit /></el-icon>
        </div>
        <h1 class="hero-title">复旦医学院<br>智慧医疗教学平台</h1>
        <p class="hero-desc">
          基于医疗知识库的智能问答系统，面向医生、护士、患者及管理人员，<br>
          提供权威、可溯源的健康科普与临床辅助咨询服务。
        </p>
        <div class="hero-features">
          <div class="hero-feature">
            <el-icon size="18"><Collection /></el-icon>
            <span>知识库管理</span>
          </div>
          <div class="hero-feature">
            <el-icon size="18"><ChatDotRound /></el-icon>
            <span>智能咨询</span>
          </div>
          <div class="hero-feature">
            <el-icon size="18"><Reading /></el-icon>
            <span>患者教育</span>
          </div>
        </div>
      </div>
    </div>

    <div class="login-panel">
      <el-card class="login-card">
        <div class="brand">
          <div class="brand-icon">🏥</div>
          <h2 class="brand-title">医智助手</h2>
          <p class="brand-sub">医疗知识库智能问答系统</p>
        </div>
        <el-form :model="form" label-position="top" @submit.prevent="onSubmit" class="login-form">
          <el-form-item label="用户名">
            <el-input v-model="form.username" placeholder="演示账号：patientdemo / doctordemo / admindemo"
              autocomplete="username" size="large" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" placeholder="演示密码：demo123" show-password
              autocomplete="current-password" size="large" @keyup.enter="onSubmit" />
          </el-form-item>
          <el-button type="primary" size="large" style="width: 100%; margin-top: 8px" :loading="loading" @click="onSubmit">
            登 录
          </el-button>
          <div class="login-extra">
            <span class="text-muted">还没有账号？</span>
            <el-link type="primary" @click="router.push('/register')">立即注册</el-link>
          </div>
          <el-divider content-position="center">演示账号</el-divider>
          <div class="demo-accounts">
            <el-tag v-for="a in demoAccounts" :key="a.role" size="small" effect="plain">{{ a.label }}</el-tag>
          </div>
        </el-form>
      </el-card>
      <p class="login-footer">© {{ year }} 复旦医学院智慧医疗教学演示平台 · 内容仅供教学演示，不构成诊疗建议</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import {reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessage} from 'element-plus'
import {useAuth} from '@/stores/auth'

const auth = useAuth()
const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const year = new Date().getFullYear()

const demoAccounts = [
  { role: 'admin', label: 'admindemo' },
  { role: 'doctor', label: 'doctordemo' },
  { role: 'nurse', label: 'nursedemo' },
  { role: 'patient', label: 'patientdemo' },
  { role: 'public', label: 'publicdemo' },
]

async function onSubmit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  background: #f8fafc;
}
.login-hero {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
  color: #fff;
  padding: 48px;
}
.hero-content {
  max-width: 520px;
}
.hero-badge {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}
.hero-title {
  font-size: 36px;
  line-height: 1.25;
  font-weight: 700;
  margin: 0 0 18px;
}
.hero-desc {
  font-size: 16px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.85);
  margin: 0 0 32px;
}
.hero-features {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.hero-feature {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  font-size: 14px;
}
.login-panel {
  width: 460px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  background: #fff;
}
.login-card {
  width: 100%;
  max-width: 400px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
  border: none;
}
.brand {
  text-align: center;
  margin-bottom: 24px;
}
.brand-icon {
  font-size: 42px;
  margin-bottom: 8px;
}
.brand-title {
  margin: 0 0 6px;
  font-size: 22px;
  color: #111827;
}
.brand-sub {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}
.login-form :deep(.el-form-item__label) {
  color: #374151;
  font-weight: 500;
}
.login-extra {
  text-align: center;
  margin-top: 16px;
  font-size: 13px;
}
.text-muted {
  color: #9ca3af;
  margin-right: 6px;
}
.demo-accounts {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}
.login-footer {
  margin-top: 24px;
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
  max-width: 400px;
}
@media (max-width: 900px) {
  .login-hero {
    display: none;
  }
  .login-panel {
    width: 100%;
    padding: 24px;
  }
}
</style>
