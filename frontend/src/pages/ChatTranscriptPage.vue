<template>
  <el-card>
    <template #header>
      <div style="display: flex; align-items: center; justify-content: space-between">
        <span>咨询记录（只读）</span>
        <el-button @click="router.back()"><el-icon><ArrowLeft /></el-icon>&nbsp;返回</el-button>
      </div>
    </template>
    <div v-loading="loading">
      <div style="margin-bottom: 12px">
        <el-tag>{{ messages.length }} 条消息</el-tag>
        <span style="color: #999; margin-left: 8px; font-size: 12px">注：回答基于知识库检索生成，仅作健康信息参考。</span>
      </div>
      <ChatMessage v-for="m in messages" :key="m.id" :role="m.role" :content="m.content" :citations="m.citations ?? []" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import {onMounted, ref} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {ElMessage} from 'element-plus'
import ChatMessage from '../components/ChatMessage.vue'
import {chatApi} from '../api/endpoints'
import type {Message} from '../types'

const route = useRoute()
const router = useRouter()
const messages = ref<Message[]>([])
const loading = ref(true)

onMounted(() => {
  const id = route.params.id as string
  chatApi
    .detail(id)
    .then((detail) => (messages.value = detail.messages))
    .catch((e) => ElMessage.error((e as Error).message))
    .finally(() => (loading.value = false))
})
</script>
