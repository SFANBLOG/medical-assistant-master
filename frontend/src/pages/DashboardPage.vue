<template>
  <div>
    <h4 class="page-title">数据仪表盘</h4>
    <el-row :gutter="16">
      <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="知识库" :value="stats?.kb_count ?? 0" /></el-card></el-col>
      <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="文档" :value="stats?.doc_count ?? 0" /></el-card></el-col>
      <el-col :xs="12" :md="8" :lg="4"><el-card><el-statistic title="向量切片" :value="stats?.chunk_count ?? 0" /></el-card></el-col>
      <el-col :xs="12" :md="8" :lg="6"><el-card><el-statistic title="咨询会话" :value="stats?.conversation_count ?? 0" /></el-card></el-col>
      <el-col :xs="12" :md="8" :lg="6"><el-card><el-statistic title="消息条数" :value="stats?.message_count ?? 0" /></el-card></el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :xs="24" :lg="14">
        <el-card header="各知识库文档数">
          <EChart v-if="stats" :option="barOption" height="280px" />
        </el-card>
      </el-col>
      <el-col v-if="stats?.role_breakdown" :xs="24" :lg="10">
        <el-card header="用户身份分布（全系统）">
          <EChart :option="pieOption" height="280px" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import {computed, onMounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import type {EChartsOption} from 'echarts'
import EChart from '../components/EChart.vue'
import {dashboardApi} from '../api/endpoints'
import type {DashboardStats} from '../types'
import {ROLE_LABELS} from '../types'

const stats = ref<DashboardStats | null>(null)

onMounted(() => {
  dashboardApi
    .stats()
    .then((s) => (stats.value = s))
    .catch((e) => ElMessage.error((e as Error).message))
})

const PIE_COLORS = ['#1677ff', '#fa541c', '#722ed1', '#52c41a', '#eb2f96']

const barOption = computed<EChartsOption>(() => ({
  tooltip: {},
  grid: { left: 8, right: 16, bottom: 8, top: 16, containLabel: true },
  xAxis: { type: 'category', data: (stats.value?.docs_by_kb ?? []).map((d) => d.name), axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', minInterval: 1 },
  series: [{ type: 'bar', data: (stats.value?.docs_by_kb ?? []).map((d) => d.doc_count), barMaxWidth: 40, itemStyle: { color: '#1677ff', borderRadius: [4, 4, 0, 0] } }],
}))

const pieOption = computed<EChartsOption>(() => ({
  tooltip: {},
  legend: { bottom: 0 },
  series: [
    {
      type: 'pie',
      radius: '62%',
      center: ['50%', '46%'],
      label: { formatter: '{b}\n{c}' },
      data: (stats.value?.role_breakdown ?? []).map((r, i) => ({
        name: (ROLE_LABELS as Record<string, string>)[r.role] ?? r.role,
        value: r.count,
        itemStyle: { color: PIE_COLORS[i % PIE_COLORS.length] },
      })),
    },
  ],
}))
</script>
