<template>
  <el-card>
    <template #header>系统管理</template>
    <el-tabs v-model="tab">
      <el-tab-pane label="用户管理" name="users">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap">
          <el-input v-model="q" placeholder="搜索用户名/姓名" clearable style="width: 220px" @keyup.enter="doSearch" />
          <el-select v-model="roleFilter" clearable placeholder="按身份筛选" style="width: 140px" @change="doSearch">
            <el-option v-for="(label, value) in ROLE_LABELS" :key="value" :value="value" :label="label" />
          </el-select>
          <el-button type="primary" @click="createOpen = true"><el-icon><Plus /></el-icon>&nbsp;新建用户</el-button>
        </div>

        <el-table :data="items" v-loading="loading" row-key="id">
          <el-table-column label="ID" prop="id" width="60" />
          <el-table-column label="用户名" prop="username" width="150" />
          <el-table-column label="姓名" prop="display_name" width="130" />
          <el-table-column label="身份" width="90">
            <template #default="{ row }"><el-tag :type="ROLE_TAG_TYPES[row.role]">{{ ROLE_LABELS[row.role] }}</el-tag></template>
          </el-table-column>
          <el-table-column label="注册时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" link @click="removeUser(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="prev, pager, next, total"
          style="margin-top: 16px; justify-content: flex-end" @current-change="load" />

        <!-- 新建用户 -->
        <el-dialog v-model="createOpen" title="新建用户" width="440px">
          <el-form :model="createForm" label-position="top">
            <el-form-item label="用户名" required>
              <el-input v-model="createForm.username" placeholder="3-32 个字符" />
            </el-form-item>
            <el-form-item label="姓名/昵称">
              <el-input v-model="createForm.display_name" placeholder="选填" />
            </el-form-item>
            <el-form-item label="身份" required>
              <el-select v-model="createForm.role" style="width: 100%">
                <el-option v-for="(label, value) in ROLE_LABELS" :key="value" :value="value" :label="label" />
              </el-select>
            </el-form-item>
            <el-form-item label="密码" required>
              <el-input v-model="createForm.password" type="password" placeholder="至少 6 位" show-password />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="createOpen = false">取消</el-button>
            <el-button type="primary" @click="createUser">创建</el-button>
          </template>
        </el-dialog>

        <!-- 编辑用户 -->
        <el-dialog v-model="editOpen" title="编辑用户" width="440px">
          <el-form :model="editForm" label-position="top">
            <el-form-item label="身份" required>
              <el-select v-model="editForm.role" style="width: 100%">
                <el-option v-for="(label, value) in ROLE_LABELS" :key="value" :value="value" :label="label" />
              </el-select>
            </el-form-item>
            <el-form-item label="姓名/昵称">
              <el-input v-model="editForm.display_name" />
            </el-form-item>
            <el-form-item label="重置密码（留空则不修改）">
              <el-input v-model="editForm.reset_password" type="password" placeholder="至少 6 位" show-password />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="editOpen = false">取消</el-button>
            <el-button type="primary" @click="editUser">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <el-tab-pane label="系统看板" name="stats">
        <el-row :gutter="16">
          <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="用户总数" :value="stats?.user_count ?? 0" /></el-card></el-col>
          <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="知识库" :value="stats?.kb_count ?? 0" /></el-card></el-col>
          <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="文档" :value="stats?.doc_count ?? 0" /></el-card></el-col>
          <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="向量切片" :value="stats?.chunk_count ?? 0" /></el-card></el-col>
          <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="咨询会话" :value="stats?.conversation_count ?? 0" /></el-card></el-col>
          <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="消息总数" :value="stats?.message_count ?? 0" /></el-card></el-col>
          <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="住院记录" :value="stats?.hospitalization_count ?? 0" /></el-card></el-col>
          <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="消费总额(元)" :value="stats?.bill_total ?? 0" /></el-card></el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup lang="ts">
import {onMounted, reactive, ref} from 'vue'
import {ElMessage, ElMessageBox} from 'element-plus'
import {adminApi} from '@/api/endpoints'
import type {AdminUserRow, Role} from '@/types'
import {ROLE_LABELS, ROLE_TAG_TYPES} from '@/types'

interface AdminStats {
  user_count: number
  kb_count: number
  doc_count: number
  chunk_count: number
  conversation_count: number
  message_count: number
  hospitalization_count: number
  bill_total: number
}

const tab = ref('users')
const items = ref<AdminUserRow[]>([])
const total = ref(0)
const roleFilter = ref('')
const q = ref('')
const page = ref(1)
const loading = ref(false)

const createOpen = ref(false)
const createForm = reactive({ username: '', display_name: '', role: 'patient' as Role, password: '' })

const editOpen = ref(false)
const editId = ref<number | null>(null)
const editForm = reactive({ role: 'patient' as Role, display_name: '', reset_password: '' })

const stats = ref<AdminStats | null>(null)

function formatTime(v: string) {
  return v ? v.replace('T', ' ').slice(0, 19) : ''
}

async function load() {
  loading.value = true
  try {
    const d = await adminApi.users({ role: roleFilter.value || undefined, q: q.value, page: page.value, page_size: 10 })
    items.value = d.items
    total.value = d.total
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  adminApi.stats().then((s) => (stats.value = s as AdminStats)).catch(() => {})
})

function doSearch() {
  page.value = 1
  load()
}

async function createUser() {
  if (!createForm.username || !createForm.password) {
    ElMessage.warning('请填写用户名与密码')
    return
  }
  try {
    await adminApi.createUser({ ...createForm })
    ElMessage.success('用户已创建')
    createOpen.value = false
    createForm.username = ''
    createForm.display_name = ''
    createForm.password = ''
    load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

function openEdit(row: AdminUserRow) {
  editId.value = row.id
  editForm.role = row.role
  editForm.display_name = row.display_name
  editForm.reset_password = ''
  editOpen.value = true
}

async function editUser() {
  if (editId.value == null) return
  try {
    await adminApi.updateUser(editId.value, { ...editForm, reset_password: editForm.reset_password || undefined })
    ElMessage.success('用户已更新')
    editOpen.value = false
    load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function removeUser(r: AdminUserRow) {
  try {
    await ElMessageBox.confirm(`删除用户「${r.username}」？将同时级联删除其业务数据，该操作不可恢复。`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await adminApi.removeUser(r.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error((e as Error).message)
  }
}
</script>
