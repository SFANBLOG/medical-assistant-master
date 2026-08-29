<template>
  <div v-loading="loading">
    <h4 class="page-title">医生工作台</h4>
    <el-row :gutter="16">
      <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="知识库（全系统）" :value="stats?.kb_count ?? 0" /></el-card></el-col>
      <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="文档" :value="stats?.doc_count ?? 0" /></el-card></el-col>
      <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="向量切片" :value="stats?.chunk_count ?? 0" /></el-card></el-col>
      <el-col :xs="12" :md="8" :lg="6"><el-card><el-statistic title="全系统咨询会话" :value="stats?.conversation_count ?? 0" /></el-card></el-col>
      <el-col :xs="12" :md="8" :lg="6"><el-card><el-statistic title="消息总数" :value="stats?.message_count ?? 0" /></el-card></el-col>
    </el-row>
    <el-card style="margin-top: 16px">
      <template #header>最近咨询（全系统）</template>
      <el-table :data="recent" size="small" row-key="id">
        <el-table-column label="用户" prop="username" width="140" />
        <el-table-column label="身份" width="90">
          <template #default="{ row }"><el-tag>{{ ROLE_LABELS[row.role] }}</el-tag></template>
        </el-table-column>
        <el-table-column label="咨询标题" prop="title" min-width="200" show-overflow-tooltip />
        <el-table-column label="知识库" width="160">
          <template #default="{ row }">{{ row.kb_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {onMounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import {dashboardApi} from '../api/endpoints'
import type {DashboardStats, RecentConversation} from '../types'
import {ROLE_LABELS} from '../types'

const stats = ref<DashboardStats | null>(null)
const recent = ref<RecentConversation[]>([])
const loading = ref(true)

function formatTime(v: string) {
  return v ? v.replace('T', ' ').slice(0, 19) : ''
}

onMounted(() => {
  Promise.all([dashboardApi.stats(), dashboardApi.recent()])
    .then(([s, r]) => {
      stats.value = s
      recent.value = r
    })
    .catch((e) => ElMessage.error((e as Error).message))
    .finally(() => (loading.value = false))
})
</script>
