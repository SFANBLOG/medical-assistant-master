<template>
  <div class="msg-row" :class="message.role">
    <div class="avatar" :class="message.role">
      <el-icon v-if="message.role === 'user'" :size="18"><UserFilled /></el-icon>
      <el-icon v-else :size="18"><FirstAidKit /></el-icon>
    </div>

    <div class="bubble-wrap">
      <div class="bubble" :class="message.role">
        <!-- 打字中 -->
        <div v-if="message.streaming && !message.content" class="typing">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
        <!-- 内容 -->
        <div v-else class="content">{{ message.content }}</div>
        <div v-if="message.error" class="err-tip">（本次回答可能不完整）</div>
      </div>

      <!-- 引用来源 -->
      <div
        v-if="
          message.role === 'assistant' &&
          message.citations &&
          message.citations.length > 0
        "
        class="citations"
      >
        <div class="cite-toggle" @click="citeVisible = !citeVisible">
          <el-icon><Document /></el-icon>
          <span>引用来源（{{ message.citations.length }}）</span>
          <el-icon class="cite-arrow">
            <ArrowUp v-if="citeVisible" />
            <ArrowDown v-else />
          </el-icon>
        </div>
        <el-collapse-transition>
          <div v-show="citeVisible" class="cite-list">
            <div
              v-for="(c, i) in message.citations"
              :key="i"
              class="cite-item"
            >
              <div class="cite-head">
                <span class="cite-idx">[{{ i + 1 }}]</span>
                <span class="cite-title">{{ c.title || `文档 ${c.doc_id}` }}</span>
                <el-tag size="small" type="info" effect="plain">
                  相似度 {{ formatSimilarity(c.similarity) }}
                </el-tag>
              </div>
              <div class="cite-text">{{ c.source_text }}</div>
            </div>
          </div>
        </el-collapse-transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { Message } from '@/types'

defineProps<{ message: Message }>()

const citeVisible = ref(true)

function formatSimilarity(v: number | undefined): string {
  if (v === undefined || v === null) return '-'
  const num = Number(v)
  // 兼容 0-1 与 0-100 两种量纲
  const pct = num > 1 ? num : num * 100
  return `${pct.toFixed(1)}%`
}
</script>

<style scoped>
.msg-row {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  align-items: flex-start;
}

.msg-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.avatar.user {
  background: #409eff;
}

.avatar.assistant {
  background: linear-gradient(135deg, #409eff, #79bbff);
}

.bubble-wrap {
  max-width: 78%;
  display: flex;
  flex-direction: column;
}

.msg-row.user .bubble-wrap {
  align-items: flex-end;
}

.bubble {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.7;
  font-size: 14px;
  word-break: break-word;
}

.bubble.user {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 4px;
}

.bubble.assistant {
  background: #fff;
  border: 1px solid var(--el-border-color-lighter);
  border-top-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
}

.err-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #f56c6c;
}

/* 打字动画 */
.typing {
  display: inline-flex;
  gap: 5px;
  padding: 4px 0;
}

.typing .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #a0cfff;
  animation: typing-bounce 1.2s infinite ease-in-out;
}

.typing .dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing .dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

/* 引用 */
.citations {
  margin-top: 8px;
  width: 100%;
}

.cite-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #409eff;
  cursor: pointer;
  user-select: none;
  padding: 4px 8px;
  border-radius: 6px;
  background: #ecf5ff;
}

.cite-toggle:hover {
  background: #d9ecff;
}

.cite-arrow {
  transition: transform 0.2s;
}

.cite-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cite-item {
  background: #f7f9fc;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 10px 12px;
}

.cite-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.cite-idx {
  font-weight: 600;
  color: #409eff;
}

.cite-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.cite-text {
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
  max-height: 72px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
</style>
