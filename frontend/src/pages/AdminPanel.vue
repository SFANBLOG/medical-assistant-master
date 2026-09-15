<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header>
        <div class="hd"><span>系统用户管理</span>
          <el-button type="primary" @click="showAdd = true">新增用户</el-button></div>
      </template>
      <el-table :data="users" style="width:100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="display_name" label="姓名" />
        <el-table-column prop="role" label="角色" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>全系统数据看板</template>
      <el-row :gutter="16">
        <el-col v-for="s in statCards" :key="s.k" :span="6">
          <el-statistic :title="s.t" :value="s.v" />
        </el-col>
      </el-row>
    </el-card>

    <el-dialog v-model="showAdd" title="新增用户" width="420px">
      <el-form :model="form">
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.display_name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role"><el-option v-for="r in roles" :key="r" :label="r" :value="r" /></el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="add">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const users = ref([])
const roles = ['patient', 'doctor', 'nurse', 'public', 'admin']
const showAdd = ref(false)
const form = ref({ username: '', display_name: '', role: 'patient' })
const stats = ref({})

const statCards = computed(() => [
  { k: 'kb', t: '知识库', v: stats.value.knowledge_bases || 0 },
  { k: 'doc', t: '文档', v: stats.value.documents || 0 },
  { k: 'conv', t: '会话', v: stats.value.conversations || 0 },
  { k: 'user', t: '用户', v: stats.value.users || users.value.length }
])

async function load() {
  try { const r = await api.adminUsers(); if (r.ok) users.value = r.data } catch (e) {}
  try { const r = await api.dashboard(); if (r.ok) stats.value = r.data } catch (e) {}
}
onMounted(load)

async function add() {
  if (!form.value.username) return ElMessage.warning('请输入用户名')
  const r = await api.adminCreateUser(form.value)
  if (r.ok) { ElMessage.success('创建成功'); showAdd.value = false; load() }
  else ElMessage.error(r.error || '失败')
}

async function del(row) {
  await ElMessageBox.confirm(`确认删除用户 ${row.username}？`, '提示', { type: 'warning' })
  const r = await api.adminDeleteUser(row.id)
  if (r.ok) { ElMessage.success('已删除'); load() } else ElMessage.error(r.error || '失败')
}
</script>

<style scoped>.hd { display: flex; justify-content: space-between; }</style>
