<template>
  <div class="dashboard">
    <!-- 欢迎横幅 -->
    <el-card class="welcome-card" :body-style="{ padding: '24px' }">
      <div class="welcome-body">
        <div class="welcome-avatar">{{ greeting.icon }}</div>
        <div class="welcome-text">
          <h2 class="welcome-title">{{ greeting.title }}，{{ auth.user?.display_name || '用户' }}</h2>
          <p class="welcome-desc">{{ greeting.desc }}</p>
        </div>
        <div class="welcome-meta">
          <div class="welcome-date">{{ today }}</div>
          <el-tag :type="ROLE_TAG_TYPES[auth.user!.role]" size="large" round effect="plain">
            {{ ROLE_LABELS[auth.user!.role] }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 快捷入口 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col v-for="item in shortcuts" :key="item.path" :xs="12" :sm="8" :md="6" :lg="4">
        <el-card class="shortcut-card" shadow="hover" @click="router.push(item.path)">
          <div class="shortcut-icon" :style="{ background: item.color }">
            <el-icon size="22">
              <component :is="item.icon"/>
            </el-icon>
          </div>
          <div class="shortcut-label">{{ item.label }}</div>
          <div class="shortcut-hint">{{ item.hint }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 核心指标 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :xs="12" :md="8" :lg="4">
        <el-card>
          <el-statistic title="知识库" :value="stats?.kb_count ?? 0"/>
        </el-card>
      </el-col>
      <el-col :xs="12" :md="8" :lg="4">
        <el-card>
          <el-statistic title="文档" :value="stats?.doc_count ?? 0"/>
        </el-card>
      </el-col>
      <el-col :xs="12" :md="8" :lg="4">
        <el-card>
          <el-statistic title="向量切片" :value="stats?.chunk_count ?? 0"/>
        </el-card>
      </el-col>
      <el-col :xs="12" :md="8" :lg="6">
        <el-card>
          <el-statistic title="咨询会话" :value="stats?.conversation_count ?? 0"/>
        </el-card>
      </el-col>
      <el-col :xs="12" :md="8" :lg="6">
        <el-card>
          <el-statistic title="消息条数" :value="stats?.message_count ?? 0"/>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 最近咨询 -->
      <el-col :xs="24" :lg="isStaff ? 14 : 24">
        <el-card header="最近咨询">
          <el-table v-if="recent.length" :data="recent" size="small" v-loading="recentLoading">
            <el-table-column label="标题" prop="title" min-width="160" show-overflow-tooltip/>
            <el-table-column label="用户" min-width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="ROLE_TAG_TYPES[row.role]">{{ ROLE_LABELS[row.role] }}</el-tag>
                {{ row.username }}
              </template>
            </el-table-column>
            <el-table-column label="知识库" prop="kb_name" min-width="120" show-overflow-tooltip/>
            <el-table-column label="时间" width="150">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无最近咨询"/>
        </el-card>
      </el-col>

      <!-- 公告 / 系统提示 -->
      <el-col :xs="24" :lg="10" style="margin-top: 16px" :lg-offset="0">
        <el-card header="平台公告">
          <el-timeline>
            <el-timeline-item v-for="(n, i) in notices" :key="i" :type="n.type" :timestamp="n.date">
              {{ n.content }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表（仅医护/管理员） -->
    <el-row v-if="isStaff" :gutter="16" style="margin-top: 16px">
      <el-col :xs="24" :lg="14">
        <el-card header="各知识库文档数">
          <EChart v-if="stats" :option="barOption" height="280px"/>
        </el-card>
      </el-col>
      <el-col v-if="stats?.role_breakdown" :xs="24" :lg="10">
        <el-card header="用户身份分布（全系统）">
          <EChart :option="pieOption" height="280px"/>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import {computed, onMounted, ref} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessage} from 'element-plus'
import type {EChartsOption} from 'echarts'
import EChart from '@/components/EChart.vue'
import {dashboardApi} from '@/api/endpoints'
import {useAuth} from '@/stores/auth'
import type {DashboardStats, RecentConversation, Role} from '@/types'
import {ROLE_LABELS, ROLE_TAG_TYPES} from '@/types'

const auth = useAuth()
const router = useRouter()
const role = computed<Role>(() => auth.user?.role ?? 'public')
const isStaff = computed(() => role.value === 'doctor' || role.value === 'admin')

const stats = ref<DashboardStats | null>(null)
const recent = ref<RecentConversation[]>([])
const recentLoading = ref(false)

onMounted(() => {
  dashboardApi
      .stats()
      .then((s) => (stats.value = s))
      .catch((e) => ElMessage.error((e as Error).message))
  if (isStaff.value) {
    recentLoading.value = true
    dashboardApi
        .recent()
        .then((items) => (recent.value = items))
        .catch(() => {
        })
        .finally(() => (recentLoading.value = false))
  }
})

const today = computed(() => {
  const d = new Date()
  const w = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'][d.getDay()]
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${w}`
})

const greeting = computed(() => {
  const hour = new Date().getHours()
  const period = hour < 12 ? '上午好' : hour < 18 ? '下午好' : '晚上好'
  const map: Record<Role, { title: string; desc: string; icon: string }> = {
    admin: {
      title: `${period}，管理员`,
      desc: '欢迎进入复旦医学院智慧医疗平台。您可进行系统管理、知识库维护与用户管理。',
      icon: '⚙️'
    },
    doctor: {
      title: `${period}，医生`,
      desc: '欢迎进入复旦医学院智慧医疗平台。您可使用智能咨询、管理知识库与开展患者教育。',
      icon: '👨‍⚕️'
    },
    nurse: {
      title: `${period}，护士`,
      desc: '欢迎进入复旦医学院智慧医疗平台。您可使用智能咨询并查看公开知识库。',
      icon: '👩‍⚕️'
    },
    patient: {
      title: `${period}，患者`,
      desc: '欢迎进入复旦医学院智慧医疗平台。您可随时进行智能健康咨询并浏览公开知识库。',
      icon: '🏥'
    },
    public: {
      title: `${period}，欢迎`,
      desc: '欢迎进入复旦医学院智慧医疗平台。您可进行智能健康咨询并浏览公开知识库。',
      icon: '🌿'
    },
  }
  return map[role.value]
})

interface Shortcut {
  path: string
  label: string
  hint: string
  icon: string
  color: string
}

const shortcuts = computed<Shortcut[]>(() => {
  const common: Shortcut[] = [
    {path: '/chat', label: '智能咨询', hint: '开始新一轮问答', icon: 'ChatDotRound', color: '#1677ff'},
    {path: '/chat/history', label: '咨询历史', hint: '查看过往记录', icon: 'Clock', color: '#52c41a'},
  ]
  const roleMap: Record<Role, Shortcut[]> = {
    admin: [
      {path: '/kb', label: '知识库管理', hint: '维护疾病文档', icon: 'Collection', color: '#722ed1'},
      {path: '/admin', label: '系统管理', hint: '用户与系统看板', icon: 'Setting', color: '#fa8c16'},
    ],
    doctor: [
      {path: '/kb', label: '知识库管理', hint: '上传/管理疾病文档', icon: 'Collection', color: '#722ed1'},
      {path: '/health', label: '患者教育', hint: '健康资讯与宣教', icon: 'Reading', color: '#eb2f96'},
    ],
    nurse: [
      {path: '/kb', label: '知识库查看', hint: '浏览公开疾病文档', icon: 'Collection', color: '#722ed1'},
    ],
    patient: [
      {path: '/kb', label: '知识库查看', hint: '浏览公开疾病文档', icon: 'Collection', color: '#722ed1'},
    ],
    public: [
      {path: '/kb', label: '知识库查看', hint: '浏览公开疾病文档', icon: 'Collection', color: '#722ed1'},
    ],
  }
  return [...common, ...roleMap[role.value]]
})

const notices = [
  {
    type: 'primary',
    date: '2026-08-26',
    content: '平台已完成知识库重构：管理员与医生可创建公有/私有知识库，患者/群众/护士可浏览公开知识库。'
  },
  {type: 'success', date: '2026-08-25', content: '新增 12 类疾病、480 篇医学文档，覆盖呼吸、心血管、消化、神经等系统。'},
  {
    type: 'warning',
    date: '2026-08-24',
    content: '系统内容仅用于健康科普与教学演示，不构成诊疗建议。如有不适，请及时就医。'
  },
]

function formatTime(v: string) {
  return v ? v.replace('T', ' ').slice(0, 19) : ''
}

const PIE_COLORS = ['#1677ff', '#fa541c', '#722ed1', '#52c41a', '#eb2f96']

const barOption = computed<EChartsOption>(() => ({
  tooltip: {},
  grid: {left: 8, right: 16, bottom: 8, top: 16, containLabel: true},
  xAxis: {type: 'category', data: (stats.value?.docs_by_kb ?? []).map((d) => d.name), axisLabel: {fontSize: 11}},
  yAxis: {type: 'value', minInterval: 1},
  series: [{
    type: 'bar',
    data: (stats.value?.docs_by_kb ?? []).map((d) => d.doc_count),
    barMaxWidth: 40,
    itemStyle: {color: '#1677ff', borderRadius: [4, 4, 0, 0]}
  }],
}))

const pieOption = computed<EChartsOption>(() => ({
  tooltip: {},
  legend: {bottom: 0},
  series: [
    {
      type: 'pie',
      radius: '62%',
      center: ['50%', '46%'],
      label: {formatter: '{b}\n{c}'},
      data: (stats.value?.role_breakdown ?? []).map((r, i) => ({
        name: (ROLE_LABELS as Record<string, string>)[r.role] ?? r.role,
        value: r.count,
        itemStyle: {color: PIE_COLORS[i % PIE_COLORS.length]},
      })),
    },
  ],
}))
</script>

<style scoped>
.welcome-card {
  background: linear-gradient(90deg, #eff6ff 0%, #ffffff 100%);
  border: 1px solid #dbeafe;
}

.welcome-body {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
}

.welcome-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  box-shadow: 0 4px 12px rgba(29, 78, 216, 0.12);
}

.welcome-text {
  flex: 1;
}

.welcome-title {
  margin: 0 0 6px;
  font-size: 20px;
  color: #1e3a8a;
}

.welcome-desc {
  margin: 0;
  color: #4b5563;
  font-size: 14px;
}

.welcome-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.welcome-date {
  color: #6b7280;
  font-size: 13px;
}

.shortcut-card {
  cursor: pointer;
  text-align: center;
  transition: transform 0.15s;
}

.shortcut-card:hover {
  transform: translateY(-3px);
}

.shortcut-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  margin: 0 auto 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.shortcut-label {
  font-weight: 600;
  color: #111827;
  font-size: 14px;
}

.shortcut-hint {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}
</style>
