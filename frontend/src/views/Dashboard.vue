<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">{{ role === 'admin' ? '数据总览' : '我的数据仪表盘' }}</h2>
      <div class="spacer"></div>
      <el-button :icon="'Refresh'" circle @click="loadAll" />
    </div>

    <!-- 统计卡片 -->
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

    <!-- 图表区 -->
    <el-row :gutter="14" class="chart-row">
      <!-- 咨询趋势折线图（所有角色） -->
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <h3 class="card-title">近 30 天咨询活跃度</h3>
          <EChart :option="trendOption" />
        </el-card>
      </el-col>

      <!-- 按角色展示的图表 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <h3 class="card-title">{{ chartTitleRight }}</h3>
          <EChart v-if="rightChartOption" :option="rightChartOption" />
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="bottomChartOption" :gutter="14" class="chart-row">
      <el-col :span="24">
        <el-card shadow="never">
          <h3 class="card-title">{{ chartTitleBottom }}</h3>
          <EChart :option="bottomChartOption" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 患者快捷入口 -->
    <el-row v-if="role === 'patient' || role === 'public'" :gutter="14" class="chart-row">
      <el-col :span="24">
        <el-card shadow="never">
          <h3 class="card-title">快捷操作</h3>
          <div class="quick-actions">
            <div class="quick-item" @click="router.push('/chat')">
              <el-icon :size="26"><ChatDotRound /></el-icon>
              <span>智能咨询</span>
            </div>
            <div class="quick-item" @click="router.push('/appointment')">
              <el-icon :size="26"><Calendar /></el-icon>
              <span>预约挂号</span>
            </div>
            <div class="quick-item" @click="router.push('/health-records')">
              <el-icon :size="26"><Files /></el-icon>
              <span>健康档案</span>
            </div>
            <div class="quick-item" @click="router.push('/health-info')">
              <el-icon :size="26"><Reading /></el-icon>
              <span>健康资讯</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { dashboardApi, chatApi } from '@/api'
import type {
  SystemOverview,
  UserStats,
  RevenueStats,
  DeptDistItem,
  BillCategoryItem,
} from '@/types'
import { useAuthStore } from '@/stores/auth'
import EChart from '@/components/EChart.vue'

const auth = useAuthStore()
const router = useRouter()
const role = computed(() => auth.role)

const overview = ref<SystemOverview>({})
const userStats = ref<UserStats | null>(null)
const revenue = ref<RevenueStats | null>(null)
const deptDist = ref<DeptDistItem[]>([])
const billCat = ref<BillCategoryItem[]>([])
const trend = ref<{ dates: string[]; counts: number[] }>({ dates: [], counts: [] })

/* ---------- 统计卡片 ---------- */
const statCards = computed(() => {
  const o = overview.value
  const cards: { label: string; value: string | number; icon: string; color: string }[] = []

  if (role.value === 'admin') {
    cards.push(
      { label: '用户总数', value: userStats.value?.total ?? '-', icon: 'User', color: '#409eff' },
      { label: '知识库', value: o.knowledge_bases?.kb_count ?? '-', icon: 'Collection', color: '#67c23a' },
      { label: '文档数量', value: o.knowledge_bases?.doc_count ?? '-', icon: 'Document', color: '#e6a23c' },
      { label: '咨询会话', value: o.chat?.conversations ?? '-', icon: 'ChatDotRound', color: '#909399' },
      { label: '消息总数', value: o.chat?.messages ?? '-', icon: 'Message', color: '#f56c6c' },
      { label: '引用次数', value: o.chat?.citations ?? '-', icon: 'Link', color: '#b37feb' },
      { label: '收入总额', value: fmtMoney(revenue.value?.total), icon: 'Money', color: '#13c2c2' },
      { label: '住院人次', value: o.business?.hospitalizations ?? '-', icon: 'FirstAidKit', color: '#eb2f96' },
    )
  } else if (role.value === 'doctor' || role.value === 'nurse') {
    cards.push(
      { label: '住院人次', value: o.business?.hospitalizations ?? '-', icon: 'FirstAidKit', color: '#409eff' },
      { label: '消费记录', value: o.business?.bills ?? '-', icon: 'Money', color: '#67c23a' },
      { label: '预约挂号', value: o.business?.appointments ?? '-', icon: 'Calendar', color: '#e6a23c' },
      { label: '护理记录', value: o.business?.nursing_records ?? '-', icon: 'Postcard', color: '#f56c6c' },
      { label: '排班总数', value: o.business?.schedules ?? '-', icon: 'Clock', color: '#909399' },
      { label: '咨询会话', value: o.chat?.conversations ?? '-', icon: 'ChatDotRound', color: '#13c2c2' },
      { label: '问答消息', value: o.chat?.messages ?? '-', icon: 'Message', color: '#b37feb' },
      { label: '收入总额', value: fmtMoney(revenue.value?.total), icon: 'Money', color: '#eb2f96' },
    )
  } else {
    // patient / public
    cards.push(
      { label: '住院次数', value: o.hospitalization_count ?? 0, icon: 'FirstAidKit', color: '#409eff' },
      { label: '消费笔数', value: o.bill_count ?? 0, icon: 'Money', color: '#67c23a' },
      { label: '预约次数', value: o.appointment_count ?? 0, icon: 'Calendar', color: '#e6a23c' },
      { label: '咨询次数', value: o.conversation_count ?? 0, icon: 'ChatDotRound', color: '#909399' },
      { label: '已支付', value: fmtMoney(o.total_paid), icon: 'CircleCheck', color: '#13c2c2' },
      { label: '待支付', value: fmtMoney(o.total_unpaid), icon: 'Warning', color: '#f56c6c' },
    )
  }
  return cards
})

/* ---------- 图表选项 ---------- */
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

/** 右侧图表：admin 用户角色分布饼图；doctor 科室分布柱状图；nurse/patient 无右侧（用消息趋势卡片补充占位） */
const rightChartOption = computed(() => {
  if (role.value === 'admin' && userStats.value) {
    const map: Record<string, string> = {
      patient: '患者', doctor: '医生', nurse: '护士', public: '群众', admin: '管理员',
    }
    const data = Object.entries(userStats.value.by_role || {}).map(([k, v]) => ({
      name: map[k] || k,
      value: v,
    }))
    return pieOption(data, '用户角色分布')
  }
  if (role.value === 'doctor' && deptDist.value.length) {
    return barOption(deptDist.value.map((d) => d.department), deptDist.value.map((d) => d.count))
  }
  return null
})

const chartTitleRight = computed(() => {
  if (role.value === 'admin') return '用户角色分布'
  if (role.value === 'doctor') return '住院科室分布'
  return '咨询活跃度'
})

/** 底部图表：admin 科室分布；doctor 消费类别分布 */
const bottomChartOption = computed(() => {
  if (role.value === 'admin' && deptDist.value.length) {
    return barOption(deptDist.value.map((d) => d.department), deptDist.value.map((d) => d.count))
  }
  if (role.value === 'doctor' && billCat.value.length) {
    return pieOption(
      billCat.value.map((b) => ({ name: b.category, value: b.total })),
      '消费类别占比',
    )
  }
  return null
})

const chartTitleBottom = computed(() => {
  if (role.value === 'admin') return '住院科室分布'
  if (role.value === 'doctor') return '消费类别分布'
  return ''
})

function pieOption(data: { name: string; value: number }[], title: string) {
  return {
    title: { text: title, left: 'center', top: 0, textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['38%', '65%'],
        center: ['50%', '52%'],
        data,
        label: { formatter: '{b}\n{c}', fontSize: 11 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' } },
      },
    ],
  }
}

function barOption(categories: string[], values: number[]) {
  return {
    title: { text: '住院科室分布', left: 'center', top: 0, textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 40, bottom: 50 },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: { rotate: 35, fontSize: 11 },
    },
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

/* ---------- 数据加载 ---------- */
async function loadAll() {
  try {
    const results = await Promise.allSettled([
      dashboardApi.overview(),
      loadRoleData(),
      loadTrend(),
    ])
    if (results[0].status === 'fulfilled') overview.value = results[0].value
  } catch {
    /* 兜底 */
  }
}

async function loadRoleData() {
  const r = role.value
  const tasks: Promise<unknown>[] = []
  if (r === 'admin') {
    tasks.push(
      dashboardApi.users().then((d) => (userStats.value = d)),
      dashboardApi.departmentDistribution().then((d) => (deptDist.value = d)),
      dashboardApi.billCategoryDistribution().then((d) => (billCat.value = d)),
      dashboardApi.revenue().then((d) => (revenue.value = d)),
    )
  } else if (r === 'doctor') {
    tasks.push(
      dashboardApi.departmentDistribution().then((d) => (deptDist.value = d)),
      dashboardApi.billCategoryDistribution().then((d) => (billCat.value = d)),
      dashboardApi.revenue().then((d) => (revenue.value = d)),
    )
  }
  const results = await Promise.allSettled(tasks)
  results.forEach((res) => {
    if (res.status === 'rejected') {
      ElMessage.warning((res.reason as Error).message || '部分统计数据加载失败')
    }
  })
}

/** 近 30 天咨询趋势：按日期聚合消息数量 */
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

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.chart-row {
  margin-top: 14px;
}

.quick-actions {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.quick-item {
  width: 110px;
  padding: 18px 8px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #409eff;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-item span {
  font-size: 13px;
  color: #606266;
}

.quick-item:hover {
  border-color: #409eff;
  background: #ecf5ff;
  transform: translateY(-2px);
}

.quick-item:hover span {
  color: #409eff;
}
</style>
