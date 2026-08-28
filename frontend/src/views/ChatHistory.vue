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
        v-if="!loading && !filtered.length"
        description="暂无咨询记录"
      />
      <div
        v-for="item in filtered"
        :key="item.id"
        class="history-item"
        :class="item.role"
      >
        <div class="history-avatar" :class="item.role">
          <el-icon v-if="item.role === 'user'" :size="16"><UserFilled /></el-icon>
          <el-icon v-else :size="16"><FirstAidKit /></el-icon>
        </div>
        <div class="history-content">
          <div class="history-meta">
            <el-tag size="small" :type="item.role === 'user' ? 'primary' : 'success'">
              {{ item.role === 'user' ? '我' : 'AI 回答' }}
            </el-tag>
            <span v-if="item.conv_title" class="history-conv">{{ item.conv_title }}</span>
            <span class="history-time">{{ formatTime(item.created_at) }}</span>
          </div>
          <div class="history-text" :class="{ collapsed: !expanded[item.id!] }">
            {{ item.content }}
          </div>
          <el-link
            v-if="item.content.length > 200"
            type="primary"
            :underline="false"
            size="small"
            class="expand-btn"
            @click="toggleExpand(item.id!)"
          >
            {{ expanded[item.id!] ? '收起' : '展开全文' }}
          </el-link>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { chatApi } from '@/api'
import type { Message } from '@/types'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const history = ref<Message[]>([])
const filterRole = ref<'all' | 'user' | 'assistant'>('all')
const expanded = ref<Record<number, boolean>>({})

const filtered = computed(() => {
  if (filterRole.value === 'all') return history.value
  return history.value.filter((m) => m.role === filterRole.value)
})

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

function toggleExpand(id: number) {
  expanded.value[id] = !expanded.value[id]
}

const formatTime = formatDateTime

onMounted(loadHistory)
</script>

<style scoped>
.history-item {
  display: flex;
  gap: 12px;
  padding: 14px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.history-item:last-child {
  border-bottom: none;
}

.history-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.history-avatar.user {
  background: #409eff;
}

.history-avatar.assistant {
  background: #67c23a;
}

.history-content {
  flex: 1;
  min-width: 0;
}

.history-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.history-conv {
  font-size: 12px;
  color: #909399;
}

.history-time {
  font-size: 12px;
  color: #c0c4cc;
}

.history-text {
  font-size: 14px;
  color: #303133;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.history-text.collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.expand-btn {
  margin-top: 4px;
}
</style>
