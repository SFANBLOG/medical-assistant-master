<template>
  <el-tooltip placement="top" effect="dark">
    <template #content>
      <div style="max-width: 320px; max-height: 240px; overflow: auto">
        <div style="font-weight: 600; margin-bottom: 4px">{{ citation.title }}</div>
        <div style="white-space: pre-wrap; font-size: 12px">{{ citation.source_text.slice(0, 400) }}</div>
      </div>
    </template>
    <el-tag :type="tagType" style="cursor: pointer">
      [{{ index + 1 }}] {{ citation.title }}
      <span style="opacity: 0.7; margin-left: 6px">相似度 {{ (citation.similarity * 100).toFixed(1) }}%</span>
    </el-tag>
  </el-tooltip>
</template>

<script setup lang="ts">
import {computed} from 'vue'
import type {Citation} from '@/types'

const props = defineProps<{ index: number; citation: Citation }>()

const TAG_TYPES = ['primary', 'cyan', 'info', 'warning', 'danger', 'success'] as const

const tagType = computed(() => TAG_TYPES[props.index % TAG_TYPES.length])
</script>
