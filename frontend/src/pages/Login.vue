<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <div class="title">医智助手</div>
      <div class="subtitle">医疗知识库智能问答系统</div>
      <el-form :model="form" @submit.prevent="doLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-button type="primary" style="width:100%" :loading="loading" @click="doLogin">登录</el-button>
      </el-form>
      <div class="demos">
        <div>演示账号（密码 demo123）：</div>
        <el-tag v-for="d in demos" :key="d.u" class="demo-tag" @click="fill(d.u)">{{ d.u }}（{{ d.r }}）</el-tag>
      </div>
    </el-card>
    <div class="app-footer login-footer">© 2026 医智助手 · 教学演示系统</div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const store = useAuthStore()
const router = useRouter()
const form = reactive({ username: 'patientdemo', password: 'demo123' })
const loading = ref(false)
const demos = [
  { u: 'patientdemo', r: '患者' }, { u: 'doctordemo', r: '医生' },
  { u: 'nursedemo', r: '护士' }, { u: 'publicdemo', r: '群众' }, { u: 'admindemo', r: '管理员' }
]

function fill(u) { form.username = u; form.password = 'demo123' }

async function doLogin() {
  loading.value = true
  try {
    const r = await api.login(form.username, form.password)
    if (r.ok) {
      store.setAuth(r.data.token, r.data.user)
      ElMessage.success('登录成功')
      router.push('/dashboard')
    } else {
      ElMessage.error(r.error || '登录失败')
    }
  } catch (e) {
    ElMessage.error('登录失败：' + (e.response?.data?.error || e.message))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; background: linear-gradient(135deg,#409eff,#67c23a); }
.login-card { width: 360px; padding: 10px 20px; }
.title { font-size: 26px; font-weight: 800; text-align: center; color: #303133; }
.subtitle { text-align: center; color: #909399; margin-bottom: 16px; }
.demos { margin-top: 14px; font-size: 12px; color: #606266; }
.demo-tag { margin: 4px 4px 0 0; cursor: pointer; }
.login-footer { position: fixed; bottom: 0; width: 100%; }
</style>
