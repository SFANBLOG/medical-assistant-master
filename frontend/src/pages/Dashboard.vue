<template>
  <div>
    <el-row :gutter="16">
      <el-col v-for="c in cards" :key="c.label" :span="6">
        <el-card shadow="hover" class="stat">
          <div class="num">{{ c.value }}</div>
          <div class="label">{{ c.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>欢迎使用医智助手</template>
          <p>当前角色：<b>{{ roleLabel }}</b>。您可以在「智能咨询」中基于知识库进行医学问答，
          系统在检索时会按您的角色权限过滤可见文档（患者/群众/护士仅可见公开知识库与公开文档）。</p>
          <el-alert type="warning" :closable="false" title="免责声明">
            本系统回答仅用于医疗健康信息辅助理解，不构成诊断、处方或治疗建议；实际医疗问题应咨询专业医生。
          </el-alert>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>数据分布</template>
          <div ref="chart" style="height:260px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, nextTick } from 'vue'
import * as echarts from 'echarts'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const store = useAuthStore()
const roleLabel = computed(() => ({ patient: '患者', doctor: '医生', nurse: '护士', public: '群众', admin: '管理员' }[store.role] || store.role))
const stats = ref({})
const chart = ref(null)

const cards = computed(() => [
  { label: '知识库', value: stats.value.knowledge_bases || 0 },
  { label: '文档', value: stats.value.documents || 0 },
  { label: '咨询会话', value: stats.value.conversations || 0 },
  { label: '我的角色', value: roleLabel.value }
])

onMounted(async () => {
  try { const r = await api.dashboard(); if (r.ok) stats.value = r.data } catch (e) {}
  await nextTick()
  if (chart.value) {
    const c = echarts.init(chart.value)
    c.setOption({
      tooltip: {}, legend: { data: ['数量'] },
      xAxis: { type: 'category', data: ['知识库', '文档', '会话', '住院', '消费', '挂号', '护理', '排班'] },
      yAxis: { type: 'value' },
      series: [{ name: '数量', type: 'bar', data: [
        stats.value.knowledge_bases || 0, stats.value.documents || 0, stats.value.conversations || 0,
        stats.value.hospitalizations || 0, stats.value.bills || 0, stats.value.appointments || 0,
        stats.value.nursing_records || 0, stats.value.schedules || 0
      ], itemStyle: { color: '#409eff' } }]
    })
  }
})
</script>

<style scoped>
.stat { text-align: center; }
.num { font-size: 28px; font-weight: 800; color: #409eff; }
.label { color: #909399; margin-top: 4px; }
</style>
