<template>
  <div v-if="role === 'user'" style="display: flex; justify-content: flex-end; margin-bottom: 16px">
    <div class="chat-bubble chat-bubble-user">{{ content }}</div>
  </div>
  <div v-else style="display: flex; margin-bottom: 16px">
    <div class="chat-bubble chat-bubble-assistant">
      <MarkdownView v-if="content" :content="content" />
      <span v-else style="color: #999">思考中{{ streaming ? '…' : '' }}</span>
      <div v-if="citations && citations.length" class="citation-row">
        <CitationCard v-for="(c, i) in citations" :key="i" :index="i" :citation="c" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import MarkdownView from './MarkdownView.vue'
import CitationCard from './CitationCard.vue'
import type {Citation} from '../types'

defineProps<{
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  streaming?: boolean
}>()
</script>

<style scoped>
.chat-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  max-width: 85%;
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-bubble-user {
  background: #1677ff;
  color: #fff;
  max-width: 70%;
}
.chat-bubble-assistant {
  background: #fff;
  border: 1px solid #f0f0f0;
}
.citation-row {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
