<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">全系统数据看板</h2>
      <div class="spacer"></div>
      <el-button :icon="'Refresh'" circle @click="loadAll" />
    </div>

    <!-- 核心统计卡片 -->
    <el-row :gutter="14">
      <el-col v-for="card in statCards" :key="card.label" :xs="12" :sm="8" :md="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-icon" :style="{ background: card.color }">
            <el-icon><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-label">{{ card.label }}</div>
            <div class="stat-value">{{ card.value }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表 -->
    <el-row :gutter="14" class="chart-row">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <h3 class="card-title">用户角色分布</h3>
          <EChart v-if="userPieOption" :option="userPieOption" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <h3 class="card-title">住院科室分布</h3>
          <EChart v-if="deptBarOption" :option="deptBarOption" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="chart-row">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <h3 class="card-title">消费类别分布</h3>
          <EChart v-if="billPieOption" :option="billPieOption" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <h3 class="card-title">近 30 天咨询活跃度</h3>
          <EChart v-if="trendOption" :option="trendOption" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { dashboardApi, chatApi } from '@/api'
import type {
  SystemOverview,
  UserStats,
  KbStats,
  BusinessStats,
  ChatStats,
  RevenueStats,
  DeptDistItem,
  BillCategoryItem,
} from '@/types'
import EChart from '@/components/EChart.vue'

const overview = ref<SystemOverview>({})
const userStats = ref<UserStats | null>(null)
const kbStats = ref<KbStats | null>(null)
const business = ref<BusinessStats | null>(null)
const chatStats = ref<ChatStats | null>(null)
const revenue = ref<RevenueStats | null>(null)
const deptDist = ref<DeptDistItem[]>([])
const billCat = ref<BillCategoryItem[]>([])
const trend = ref<{ dates: string[]; counts: number[] }>({ dates: [], counts: [] })

const statCards = computed(() => {
  const o = overview.value
  return [
    { label: '用户总数', value: userStats.value?.total ?? '-', icon: 'User', color: '#409eff' },
    { label: '知识库', value: kbStats.value?.kb_count ?? '-', icon: 'Collection', color: '#67c23a' },
    { label: '文档总数', value: kbStats.value?.doc_count ?? '-', icon: 'Document', color: '#e6a23c' },
    { label: '向量分片', value: kbStats.value?.total_chunks ?? '-', icon: 'Grid', color: '#909399' },
    { label: '咨询会话', value: chatStats.value?.conversations ?? '-', icon: 'ChatDotRound', color: '#f56c6c' },
    { label: '消息总数', value: chatStats.value?.messages ?? '-', icon: 'Message', color: '#b37feb' },
    { label: '住院人次', value: business.value?.hospitalizations ?? '-', icon: 'FirstAidKit', color: '#13c2c2' },
    { label: '消费记录', value: business.value?.bills ?? '-', icon: 'Money', color: '#eb2f96' },
    { label: '预约挂号', value: business.value?.appointments ?? '-', icon: 'Calendar', color: '#fa8c16' },
    { label: '护理记录', value: business.value?.nursing_records ?? '-', icon: 'Postcard', color: '#52c41a' },
    { label: '排班总数', value: business.value?.schedules ?? '-', icon: 'Clock', color: '#722ed1' },
    { label: '收入总额', value: fmtMoney(revenue.value?.total), icon: 'Money', color: '#13c2c2' },
  ]
})

const userPieOption = computed(() => {
  if (!userStats.value) return null
  const map: Record<string, string> = {
    patient: '患者', doctor: '医生', nurse: '护士', public: '群众', admin: '管理员',
  }
  const data = Object.entries(userStats.value.by_role || {}).map(([k, v]) => ({
    name: map[k] || k,
    value: v,
  }))
  return pieOption(data)
})

const deptBarOption = computed(() => {
  if (!deptDist.value.length) return null
  return barOption(deptDist.value.map((d) => d.department), deptDist.value.map((d) => d.count))
})

const billPieOption = computed(() => {
  if (!billCat.value.length) return null
  return pieOption(billCat.value.map((b) => ({ name: b.category, value: b.total })))
})

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 20, top: 30, bottom: 40 },
  xAxis: { type: 'category', data: trend.value.dates, boundaryGap: false },
  yAxis: { type: 'value', minInterval: 1 },
  series: [
    {
      name: '消息数',
      type: 'line',
      smooth: true,
      symbolSize: 5,
      data: trend.value.counts,
      itemStyle: { color: '#409eff' },
      lineStyle: { color: '#409eff', width: 2 },
      areaStyle: { color: 'rgba(64,158,255,0.12)' },
    },
  ],
}))

function pieOption(data: { name: string; value: number }[]) {
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['38%', '65%'],
        center: ['50%', '52%'],
        data,
        label: { formatter: '{b}\n{c}', fontSize: 11 },
      },
    ],
  }
}

function barOption(categories: string[], values: number[]) {
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 50 },
    xAxis: { type: 'category', data: categories, axisLabel: { rotate: 35, fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        data: values,
        barMaxWidth: 32,
        itemStyle: { color: '#409eff', borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
}

async function loadAll() {
  const tasks = [
    dashboardApi.overview().then((d) => (overview.value = d)),
    dashboardApi.users().then((d) => (userStats.value = d)),
    dashboardApi.knowledgeBases().then((d) => (kbStats.value = d)),
    dashboardApi.business().then((d) => (business.value = d)),
    dashboardApi.chat().then((d) => (chatStats.value = d)),
    dashboardApi.revenue().then((d) => (revenue.value = d)),
    dashboardApi.departmentDistribution().then((d) => (deptDist.value = d)),
    dashboardApi.billCategoryDistribution().then((d) => (billCat.value = d)),
    loadTrend(),
  ]
  const results = await Promise.allSettled(tasks)
  results.forEach((res) => {
    if (res.status === 'rejected') {
      ElMessage.warning((res.reason as Error).message || '部分数据加载失败')
    }
  })
}

async function loadTrend() {
  try {
    const hist = await chatApi.getHistory({ limit: 1000 })
    const dateMap = new Map<string, number>()
    const now = new Date()
    for (let i = 29; i >= 0; i--) {
      const d = new Date(now)
      d.setDate(d.getDate() - i)
      dateMap.set(fmtDate(d), 0)
    }
    for (const m of hist) {
      if (m.created_at) {
        const d = new Date(m.created_at)
        if (!isNaN(d.getTime())) {
          const key = fmtDate(d)
          if (dateMap.has(key)) dateMap.set(key, (dateMap.get(key) || 0) + 1)
        }
      }
    }
    trend.value = {
      dates: Array.from(dateMap.keys()),
      counts: Array.from(dateMap.values()),
    }
  } catch {
    /* 忽略 */
  }
}

function fmtDate(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

function fmtMoney(v?: number): string {
  if (v === undefined || v === null) return '-'
  return `¥${Number(v).toFixed(2)}`
}

onMounted(loadAll)
</script>

<style scoped>
.chart-row {
  margin-top: 14px;
}
</style>
