<template>
  <div class="login-page">
    <div class="bg-decoration dec-1"></div>
    <div class="bg-decoration dec-2"></div>

    <div class="login-card">
      <div class="brand">
        <div class="brand-icon">
          <el-icon :size="34"><FirstAidKit /></el-icon>
        </div>
        <h1 class="brand-title">医智助手</h1>
        <p class="brand-sub">医疗知识库智能问答系统</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            :prefix-icon="'User'"
            clearable
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="'Lock'"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="loading"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form>

      <div class="demo-section">
        <div class="demo-title">演示账号一键登录</div>
        <div class="demo-grid">
          <div
            v-for="acc in demoAccounts"
            :key="acc.username"
            class="demo-item"
            @click="quickLogin(acc.username)"
          >
            <el-icon class="demo-icon" :class="'icon-' + acc.role">
              <component :is="acc.icon" />
            </el-icon>
            <span class="demo-label">{{ acc.label }}</span>
          </div>
        </div>
      </div>

      <div class="register-link">
        还没有账号？
        <el-link type="primary" @click="registerVisible = true">立即注册</el-link>
      </div>
    </div>

    <!-- 注册对话框 -->
    <el-dialog v-model="registerVisible" title="注册新账号" width="420px">
      <el-form :model="registerForm" label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="registerForm.username" placeholder="至少 3 个字符" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="至少 6 个字符"
            show-password
          />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="registerForm.display_name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="registerForm.role">
            <el-radio value="patient">患者</el-radio>
            <el-radio value="public">群众</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="registerVisible = false">取消</el-button>
        <el-button type="primary" :loading="registering" @click="handleRegister">
          注册并登录
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {reactive, ref} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessage, type FormInstance, type FormRules} from 'element-plus'
import {useAuthStore} from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

// 演示账号（密码统一 demo123）
const demoAccounts = [
  { label: '管理员', username: 'admindemo', role: 'admin', icon: 'Lock' },
  { label: '医生', username: 'doctordemo', role: 'doctor', icon: 'FirstAidKit' },
  { label: '护士', username: 'nursedemo', role: 'nurse', icon: 'Postcard' },
  { label: '患者', username: 'patientdemo', role: 'patient', icon: 'User' },
  { label: '群众', username: 'publicdemo', role: 'public', icon: 'UserFilled' },
]

async function doLogin(username: string, password: string) {
  if (loading.value) return
  loading.value = true
  try {
    await auth.login(username, password)
    ElMessage.success(`欢迎，${auth.user?.display_name || username}`)
    router.push(auth.defaultRoute)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '登录失败')
  } finally {
    loading.value = false
  }
}

function handleLogin() {
  formRef.value?.validate((valid) => {
    if (valid) doLogin(form.username, form.password)
  })
}

function quickLogin(username: string) {
  form.username = username
  form.password = 'demo123'
  doLogin(username, 'demo123')
}

// 注册
const registerVisible = ref(false)
const registering = ref(false)
const registerForm = reactive({
  username: '',
  password: '',
  role: 'patient' as 'patient' | 'public',
  display_name: '',
})

async function handleRegister() {
  if (registerForm.username.trim().length < 3) {
    ElMessage.warning('用户名至少 3 个字符')
    return
  }
  if (registerForm.password.length < 6) {
    ElMessage.warning('密码至少 6 个字符')
    return
  }
  registering.value = true
  try {
    await auth.register({ ...registerForm })
    ElMessage.success('注册成功，已自动登录')
    registerVisible.value = false
    router.push(auth.defaultRoute)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '注册失败')
  } finally {
    registering.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #eef5ff 0%, #dcebff 50%, #f0f7ff 100%);
}

.bg-decoration {
  position: absolute;
  border-radius: 50%;
  opacity: 0.5;
  filter: blur(60px);
}

.dec-1 {
  width: 400px;
  height: 400px;
  background: #a0cfff;
  top: -120px;
  right: -100px;
}

.dec-2 {
  width: 350px;
  height: 350px;
  background: #b3d8ff;
  bottom: -100px;
  left: -80px;
}

.login-card {
  width: 420px;
  max-width: calc(100vw - 32px);
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(64, 158, 255, 0.15);
  padding: 36px 32px 28px;
  position: relative;
  z-index: 1;
}

.brand {
  text-align: center;
  margin-bottom: 28px;
}

.brand-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 12px;
  border-radius: 16px;
  background: linear-gradient(135deg, #409eff, #79bbff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.4);
}

.brand-title {
  font-size: 26px;
  margin: 0;
  color: #303133;
  letter-spacing: 2px;
}

.brand-sub {
  font-size: 13px;
  color: #909399;
  margin: 8px 0 0;
}

.login-btn {
  width: 100%;
  letter-spacing: 4px;
}

.demo-section {
  margin-top: 24px;
}

.demo-title {
  font-size: 12px;
  color: #909399;
  text-align: center;
  margin-bottom: 12px;
}

.demo-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}

.demo-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 4px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.demo-item:hover {
  border-color: #409eff;
  background: #ecf5ff;
  transform: translateY(-2px);
}

.demo-icon {
  font-size: 20px;
}

.icon-admin {
  color: #f56c6c;
}
.icon-doctor {
  color: #409eff;
}
.icon-nurse {
  color: #67c23a;
}
.icon-patient {
  color: #e6a23c;
}
.icon-public {
  color: #909399;
}

.demo-label {
  font-size: 12px;
  color: #606266;
}

.register-link {
  text-align: center;
  margin-top: 18px;
  font-size: 13px;
  color: #909399;
}
</style>
