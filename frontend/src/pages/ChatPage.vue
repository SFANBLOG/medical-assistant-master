<template>
  <el-card class="chat-card" :body-style="{ padding: 0, display: 'flex', flexDirection: 'column' }">
    <template #header>
      <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px">
        <span>
          <el-icon style="margin-right: 6px"><ChatDotRound /></el-icon>
          智能医疗咨询
          <el-tag v-if="offline" type="warning" size="small" style="margin-left: 8px">离线兜底模式</el-tag>
          <el-tag v-else-if="streaming" type="success" size="small" style="margin-left: 8px">生成中</el-tag>
        </span>
        <span style="display: flex; gap: 8px">
          <el-select v-model="kbId" placeholder="选择知识库" style="width: 260px" :loading="loading">
            <el-option :value="0" label="全部知识库（自动匹配）" />
            <el-option v-for="k in kbs" :key="k.id" :value="k.id" :label="`${k.name}${k.visibility === 'public' ? '（公开）' : '（私有）'}`" />
          </el-select>
          <el-button type="primary" plain @click="newChat"><el-icon><Plus /></el-icon>&nbsp;新建会话</el-button>
        </span>
      </div>
    </template>

    <div ref="scrollRef" class="chat-body">
      <el-empty v-if="!messages.length && !streaming" description="输入你的医疗问题，例如：高血压患者饮食需要注意什么？" :image-size="90" />
      <ChatMessage v-for="m in messages" :key="m.id" :role="m.role" :content="m.content" :citations="m.citations" />
      <ChatMessage v-if="streaming" role="assistant" :content="streaming.content" :citations="streaming.citations" streaming />
    </div>

    <div class="chat-input">
      <div style="display: flex; gap: 8px">
        <el-input v-model="input" type="textarea" :rows="2" resize="none"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行" :disabled="!!streaming" @keydown="onKeydown" />
        <el-button type="primary" :loading="!!streaming" style="height: auto" @click="send">
          <el-icon v-if="!streaming"><Promotion /></el-icon>&nbsp;发送
        </el-button>
      </div>
      <p v-if="conversationId" style="color: #999; font-size: 12px; margin: 6px 0 0">
        当前会话 ID：{{ conversationId.slice(0, 8) }}…
      </p>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import ChatMessage from '../components/ChatMessage.vue'
import { chatApi, kbApi } from '../api/endpoints'
import type { Citation, KnowledgeBase, Message } from '../types'

interface DisplayMessage {
  id: number | string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
}

const route = useRoute()
const kbs = ref<KnowledgeBase[]>([])
const kbId = ref<number>(0)
const messages = ref<DisplayMessage[]>([])
const streaming = ref<DisplayMessage | null>(null)
const input = ref('')
const conversationId = ref<string | null>(null)
const offline = ref(false)
const loading = ref(true)
const scrollRef = ref<HTMLDivElement>()

onMounted(() => {
  kbApi
    .list()
    .then((items) => {
      kbs.value = items
    })
    .catch((e) => ElMessage.error((e as Error).message))
    .finally(() => (loading.value = false))

  // 从历史记录带会话参数进入时加载会话
  const convFromUrl = route.query.conversation as string | undefined
  if (convFromUrl) {
    chatApi
      .detail(convFromUrl)
      .then((detail) => {
        conversationId.value = detail.conversation.id
        kbId.value = detail.conversation.kb_id ?? 0
        messages.value = detail.messages.map((m: Message) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          citations: m.citations ?? [],
        }))
      })
      .catch((e) => ElMessage.error((e as Error).message))
  }
})

watch([messages, streaming], () => {
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
})

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

async function send() {
  const question = input.value.trim()
  if (!question || streaming.value) return
  input.value = ''
  messages.value.push({ id: `u-${Date.now()}`, role: 'user', content: question, citations: [] })
  const placeholder: DisplayMessage = { id: 'streaming', role: 'assistant', content: '', citations: [] }
  streaming.value = placeholder
  offline.value = false

  const token = localStorage.getItem('mia_token')
  try {
    const resp = await fetch('/api/chat/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ conversation_id: conversationId.value, kb_id: kbId.value, question }),
    })
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}))
      throw new Error(body.error || `请求失败 (${resp.status})`)
    }
    if (!resp.body) throw new Error('响应不支持流式读取')

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let full = ''
    let doneCitations: Citation[] = []
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const frames = buf.split('\n\n')
      buf = frames.pop() ?? ''
      for (const frame of frames) {
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const evt = JSON.parse(line.slice(5).trim())
          if (evt.type === 'meta') offline.value = evt.mode === 'offline'
          else if (evt.type === 'delta') {
            full += evt.content
            streaming.value = { ...placeholder, content: full }
          } else if (evt.type === 'done') {
            doneCitations = evt.citations ?? []
            conversationId.value = evt.conversation_id
          }
        }
      }
    }
    messages.value.push({ id: `d-${Date.now()}`, role: 'assistant', content: full, citations: doneCitations })
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    streaming.value = null
  }
}

function newChat() {
  conversationId.value = null
  messages.value = []
  offline.value = false
}
</script>

<style scoped>
.chat-card {
  display: flex;
  flex-direction: column;
}
.chat-body {
  height: calc(100vh - 260px);
  min-height: 320px;
  overflow-y: auto;
  padding: 16px;
}
.chat-input {
  padding: 12px;
  border-top: 1px solid #f0f0f0;
}
</style>
