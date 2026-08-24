<template>
  <div v-if="role === 'user'" style="display: flex; justify-content: flex-end; margin-bottom: 16px">
    <div class="chat-bubble chat-bubble-user">{{ content }}</div>
  </div>
  <div v-else style="display: flex; margin-bottom: 16px">
    <div class="chat-bubble chat-bubble-assistant">
      <MarkdownView v-if="renderedContent" :content="renderedContent" />
      <span v-else style="color: #999">思考中{{ streaming ? '…' : '' }}</span>
      <div v-if="dedupedCitations.length" class="citation-row">
        <CitationCard
          v-for="(c, i) in dedupedCitations"
          :key="c.document_id + '-' + i"
          :index="i"
          :citation="c"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {computed} from 'vue'
import MarkdownView from './MarkdownView.vue'
import CitationCard from './CitationCard.vue'
import type {Citation} from '../types'

const props = defineProps<{
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  streaming?: boolean
}>()

// 参考文档去重：同一文档（document_id）的多个切片只展示一次，
// 保留相似度最高的切片，并维持首次出现的顺序。
const dedupedCitations = computed<Citation[]>(() => {
  const list = props.citations ?? []
  const seen = new Map<number | string, number>() // key -> 在 deduped 中的序号(1-based)
  const result: Citation[] = []
  for (const c of list) {
    const key: number | string = c.document_id ?? c.title
    const existingIdx = seen.get(key)
    if (existingIdx === undefined) {
      seen.set(key, result.length + 1)
      result.push(c)
    } else {
      // 保留相似度更高的切片
      const cur = result[existingIdx - 1]
      if ((c.similarity ?? 0) > (cur.similarity ?? 0)) result[existingIdx - 1] = c
    }
  }
  return result
})

  // 将答案中的 [n] 引用编号重映射到去重后的文档序号，保持引用与卡片一致。
const renderedContent = computed(() => {
  const list = props.citations ?? []
  const seen = new Map<number | string, number>()
  const originalToNew: Record<number, number> = {}
  list.forEach((c, i) => {
    const key: number | string = c.document_id ?? c.title
    let idx = seen.get(key)
    if (idx === undefined) {
      idx = seen.size + 1 // 以唯一文档计数作为新序号
      seen.set(key, idx)
    }
    originalToNew[i + 1] = idx
  })
  if (!Object.keys(originalToNew).length) return props.content
  return (props.content || '').replace(/\[(\d+)\]/g, (_m, n) => {
    const nn = originalToNew[Number(n)]
    return nn ? `[${nn}]` : _m
  })
})
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
