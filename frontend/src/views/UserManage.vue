<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">系统用户管理</h2>
      <div class="spacer"></div>
      <el-select v-model="roleFilter" placeholder="全部角色" clearable style="width: 130px">
        <el-option v-for="(label, value) in ROLE_LABELS" :key="value" :label="label" :value="value" />
      </el-select>
      <el-input
        v-model="searchText"
        placeholder="搜索用户名"
        clearable
        :prefix-icon="'Search'"
        style="width: 180px"
      />
      <el-button type="primary" :icon="'Plus'" @click="openCreate">创建用户</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="filteredList" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" min-width="110" />
        <el-table-column prop="display_name" label="姓名" min-width="100">
          <template #default="{ row }">{{ row.display_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag size="small" :class="`role-tag-${row.role}`" effect="plain">
              {{ ROLE_LABELS[row.role] || row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button
              link
              type="danger"
              size="small"
              :disabled="row.id === 1"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="total, prev, pager, next"
        :total="total"
        :page-size="query.size"
        :current-page="query.page"
        @current-change="(p) => load(p)"
      />
    </el-card>

    <!-- 创建/编辑用户 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑用户' : '创建用户'"
      width="460px"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="editing" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item :label="editing ? '重置密码' : '密码'" :required="!editing">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="editing ? '留空则不修改密码' : '至少 6 个字符'"
          />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.display_name" placeholder="显示名称" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option v-for="(label, value) in ROLE_LABELS" :key="value" :label="label" :value="value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {computed, onMounted, reactive, ref, watch} from 'vue'
import {ElMessage, ElMessageBox} from 'element-plus'
import {authApi, ROLE_LABELS} from '@/api'
import type {Role, User} from '@/types'
import {formatDateTime} from '@/utils/format'

const loading = ref(false)
const saving = ref(false)
const list = ref<User[]>([])
const total = ref(0)
const query = reactive({ page: 1, size: 50 })
const roleFilter = ref('')
const searchText = ref('')

const dialogVisible = ref(false)
const editing = ref(false)
const form = reactive<{
  id?: number
  username: string
  password: string
  display_name: string
  role: Role
}>({ username: '', password: '', display_name: '', role: 'patient' })

const filteredList = computed(() => {
  const kw = searchText.value.trim()
  if (!kw) return list.value
  return list.value.filter((u) => u.username.includes(kw) || (u.display_name || '').includes(kw))
})

async function load(page = 1) {
  loading.value = true
  query.page = page
  try {
    const params: Record<string, unknown> = { page: query.page, size: query.size }
    if (roleFilter.value) params.role = roleFilter.value
    const res = await authApi.listUsers(params)
    list.value = res.list || []
    total.value = res.total
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  Object.assign(form, { username: '', password: '', display_name: '', role: 'patient' })
  dialogVisible.value = true
}

function openEdit(row: User) {
  editing.value = true
  Object.assign(form, {
    id: row.id,
    username: row.username,
    password: '',
    display_name: row.display_name || '',
    role: row.role,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.username.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!editing.value && form.password.length < 6) {
    ElMessage.warning('密码至少 6 个字符')
    return
  }
  saving.value = true
  try {
    if (editing.value && form.id) {
      const payload: { display_name?: string; role?: Role; password?: string } = {
        display_name: form.display_name,
        role: form.role,
      }
      if (form.password) payload.password = form.password
      await authApi.updateUser(form.id, payload)
      ElMessage.success('更新成功')
    } else {
      await authApi.createUser({
        username: form.username,
        password: form.password,
        role: form.role,
        display_name: form.display_name,
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    load(query.page)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: User) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.display_name || row.username}」吗？`,
      '提示',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await authApi.deleteUser(row.id)
    ElMessage.success('已删除')
    load(query.page)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '删除失败')
  }
}

function fmtTime(t?: string) {
  return formatDateTime(t)
}

watch(roleFilter, () => load(1))

onMounted(() => {
  load(1)
})
</script>

<style scoped>
.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
