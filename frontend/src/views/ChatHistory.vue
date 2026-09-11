<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">咨询历史</h2>
      <div class="spacer"></div>
      <el-radio-group v-model="filterRole" size="small">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="user">我问</el-radio-button>
        <el-radio-button value="assistant">AI 回答</el-radio-button>
      </el-radio-group>
      <el-button :icon="'Refresh'" circle @click="loadHistory" />
    </div>

    <el-card shadow="never">
      <el-empty
        v-if="!loading && !groupedConversations.length"
        description="暂无咨询记录"
      />
      <!-- 按会话分组 -->
      <div
        v-for="group in groupedConversations"
        :key="group.convId"
        class="conv-group"
      >
        <div class="conv-group-header">
          <el-icon :size="16"><ChatLineSquare /></el-icon>
          <span class="conv-group-title">{{ group.title }}</span>
          <span class="conv-group-time">{{ formatTime(group.messages[0]?.created_at) }}</span>
        </div>
        <div class="conv-group-messages">
          <ChatMessage
            v-for="(m, i) in filterMessages(group.messages)"
            :key="m.id || i"
            :message="m"
          />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {computed, onMounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import {ChatLineSquare} from '@element-plus/icons-vue'
import {chatApi} from '@/api'
import type {Message} from '@/types'
import {formatDateTime} from '@/utils/format'
import ChatMessage from '@/components/ChatMessage.vue'

const loading = ref(false)
const history = ref<Message[]>([])
const filterRole = ref<'all' | 'user' | 'assistant'>('all')

// 按会话分组
const groupedConversations = computed(() => {
  const groups = new Map<string, { convId: string; title: string; messages: Message[] }>()
  for (const m of history.value) {
    const convId = m.conversation_id || 'unknown'
    if (!groups.has(convId)) {
      groups.set(convId, {
        convId,
        title: m.conv_title || `会话 #${convId.slice(0, 8)}`,
        messages: [],
      })
    }
    groups.get(convId)!.messages.push(m)
  }
  // 按最新消息时间倒序
  return Array.from(groups.values()).sort((a, b) => {
    const ta = a.messages[a.messages.length - 1]?.created_at || ''
    const tb = b.messages[b.messages.length - 1]?.created_at || ''
    return tb.localeCompare(ta)
  })
})

function filterMessages(messages: Message[]): Message[] {
  if (filterRole.value === 'all') return messages
  return messages.filter((m) => m.role === filterRole.value)
}

async function loadHistory() {
  loading.value = true
  try {
    history.value = await chatApi.getHistory({ limit: 100 })
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

const formatTime = formatDateTime

onMounted(loadHistory)
</script>

<style scoped>
.conv-group {
  margin-bottom: 24px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}

.conv-group:last-child {
  margin-bottom: 0;
}

.conv-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.conv-group-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.conv-group-time {
  font-size: 12px;
  color: #909399;
}

.conv-group-messages {
  padding: 16px;
}
</style>
