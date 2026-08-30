<template>
  <el-card>
    <template #header>患者管理</template>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px">
      <el-input v-model="q" placeholder="搜索患者姓名或用户名" clearable style="width: 260px" @keyup.enter="doSearch" />
      <el-button type="primary" plain @click="doSearch">搜索</el-button>
      <el-tag>共 {{ total }} 位患者</el-tag>
    </div>
    <el-table :data="items" v-loading="loading" row-key="id">
      <el-table-column type="expand">
        <template #default="{ row }">
          <PatientHospitals :patient-id="row.id" />
        </template>
      </el-table-column>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="用户名" prop="username" width="140" />
      <el-table-column label="姓名" prop="display_name" width="120" />
      <el-table-column label="当前住院状态" width="220">
        <template #default="{ row }">
          <el-tag v-if="row.latest_admission" :type="row.latest_admission.status === 'in_hospital' ? 'primary' : 'info'">
            {{ row.latest_admission.status === 'in_hospital' ? '在院' : '已出院' }} · {{ row.latest_admission.department }}
          </el-tag>
          <el-tag v-else type="info">无住院记录</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="prev, pager, next, total"
      style="margin-top: 16px; justify-content: flex-end" @current-change="load" />
  </el-card>
</template>

<script setup lang="ts">
import {onMounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import PatientHospitals from '@/components/PatientHospitals.vue'
import {doctorApi} from '@/api/endpoints'
import type {PatientSummary} from '@/types'

const items = ref<PatientSummary[]>([])
const total = ref(0)
const q = ref('')
const page = ref(1)
const loading = ref(false)

function formatTime(v?: string) {
  return v ? v.replace('T', ' ').slice(0, 16) : '-'
}

async function load() {
  loading.value = true
  try {
    const data = await doctorApi.patients({ q: q.value, page: page.value, page_size: 10 })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function doSearch() {
  page.value = 1
  load()
}
</script>
