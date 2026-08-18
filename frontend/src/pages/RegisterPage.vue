<template>
  <div class="login-wrap">
    <el-card class="register-card">
      <div class="brand">
        <h2 style="margin: 0 0 4px">注册账号</h2>
        <p style="color: #999; margin: 0">选择身份，开启医疗知识智能问答</p>
      </div>
      <el-form :model="form" label-position="top" :rules="rules" ref="formRef">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="3-32 个字符" />
        </el-form-item>
        <el-form-item label="昵称" prop="display_name">
          <el-input v-model="form.display_name" placeholder="选填，默认为用户名" />
        </el-form-item>
        <el-form-item label="身份" prop="role">
          <el-select v-model="form.role" placeholder="请选择身份" style="width: 100%">
            <el-option v-for="(label, value) in ROLE_LABELS" :key="value" :value="value" :label="label" />
          </el-select>
          <p v-if="form.role" style="font-size: 12px; color: #999; margin: 6px 0 0">
            {{ ROLE_HINTS[form.role] }}
          </p>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少 6 位" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="form.confirm" type="password" placeholder="再次输入密码" show-password />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="onSubmit">
          注册
        </el-button>
        <div style="text-align: center; margin-top: 16px">
          <span style="color: #999">已有账号？</span>
          <el-link type="primary" @click="router.push('/login')">去登录</el-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuth } from '../stores/auth'
import { ROLE_LABELS } from '../types'
import type { Role } from '../types'

const auth = useAuth()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({
  username: '',
  display_name: '',
  role: '' as Role | '',
  password: '',
  confirm: '',
})

const ROLE_HINTS: Record<Role, string> = {
  patient: '可查询住院与消费信息、预约挂号，并基于公开知识库进行智能咨询',
  doctor: '可创建/管理公开与私有知识库、上传文档、管理患者与住院信息',
  nurse: '可查看患者信息、记录护理记录、查看排班，并基于公开知识库进行咨询',
  public: '可浏览健康资讯、就诊指南，基于公开知识库进行智能咨询与预约挂号',
  admin: '可管理系统用户、全部知识库与全系统数据看板',
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度需在 3-32 个字符之间', trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择身份', trigger: 'change' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, cb) => {
        if (!value || form.password === value) cb()
        else cb(new Error('两次输入的密码不一致'))
      },
      trigger: 'blur',
    },
  ],
}

async function onSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.register(form.username, form.password, form.role as Role, form.display_name || undefined)
    ElMessage.success('注册成功')
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
.register-card {
  width: 420px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}
.brand {
  text-align: center;
  margin-bottom: 24px;
}
</style>
