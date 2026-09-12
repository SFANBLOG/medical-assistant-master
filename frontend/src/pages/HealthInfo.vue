<template>
  <div>
    <el-alert :closable="false" type="info" title="健康资讯 / 就诊指南">
      以下为公开的医学知识库主题，您可点击「去咨询」进入智能问答，获取基于知识库的可追溯解答。
    </el-alert>
    <el-row :gutter="16" style="margin-top:16px">
      <el-col v-for="k in kbs" :key="k.id" :span="6">
        <el-card shadow="hover" class="info-card" @click="go(k)">
          <div class="t">{{ k.name }}</div>
          <div class="d">{{ k.description || '医学知识科普' }}</div>
          <el-button size="small" type="primary" plain>去咨询</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const kbs = ref([])
const router = useRouter()

onMounted(async () => {
  try { const r = await api.listKB(); if (r.ok) kbs.value = r.data.filter((k) => k.visibility === 'public') } catch (e) {}
})

function go(k) { router.push('/consult') }
</script>

<style scoped>
.info-card { cursor: pointer; margin-bottom: 8px; }
.t { font-weight: 700; margin-bottom: 6px; }
.d { color: #909399; font-size: 13px; margin-bottom: 10px; min-height: 38px; }
</style>
