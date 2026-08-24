<template>
  <div class="markdown-body" v-html="html"></div>
</template>

<script setup lang="ts">
import {computed} from 'vue'
import {marked} from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{ content: string }>()

marked.setOptions({ gfm: true, breaks: true })

// 规范大模型常见的 Markdown 不规范写法，避免 # 等符号被原样显示：
// 1) 标题 # 后缺少空格（中文模型常写成 #标题）
// 2) 无序列表 -/* 后缺少空格（常写成 -项目）
function normalizeMarkdown(md: string): string {
  if (!md) return md
  return md
    .replace(/^(#{1,6})([^#\s])/gm, '$1 $2')
    .replace(/^([-*+])([^-\s])/gm, '$1 $2')
}

const html = computed(() =>
  DOMPurify.sanitize(marked.parse(normalizeMarkdown(props.content)) as string),
)
</script>
