<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <div class="brand">
        <div style="font-size: 40px">🏥</div>
        <h2 style="margin: 8px 0 4px">医智助手</h2>
        <p style="color: #999; margin: 0">医疗知识库智能问答系统</p>
      </div>
      <el-form :model="form" label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="演示账号：patientdemo / doctordemo / admindemo"
            autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="演示密码：demo123" show-password
            autocomplete="current-password" @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="onSubmit">
          登录
        </el-button>
        <div style="text-align: center; margin-top: 16px">
          <span style="color: #999">还没有账号？</span>
          <el-link type="primary" @click="router.push('/register')">立即注册</el-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessage} from 'element-plus'
import {useAuth} from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

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
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f4fd 0%, #f0fff4 100%);
}
.login-card {
  width: 380px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}
.brand {
  text-align: center;
  margin-bottom: 24px;
}
</style>
