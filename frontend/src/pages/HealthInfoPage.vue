<template>
  <el-card>
    <template #header>健康资讯</template>
    <el-alert type="info" :closable="false" style="margin-bottom: 16px"
      title="平台共建的疾病科普知识库，供群众了解常见疾病的病因、症状与处理建议。" />
    <div v-loading="loading">
      <el-empty v-if="!loading && !kbs.length" description="暂无公开知识库" />
      <el-collapse v-model="active">
        <el-collapse-item v-for="kb in kbs" :key="kb.id" :name="String(kb.id)">
          <template #title>
            <span style="font-weight: 600">{{ kb.name }}</span>
            <el-tag size="small" style="margin-left: 8px">{{ kb.doc_count ?? 0 }} 篇文档</el-tag>
          </template>
          <p style="color: #666">{{ kb.description }}</p>
          <ul v-if="(docsMap[kb.id] || []).length" style="padding-left: 20px">
            <li v-for="doc in docsMap[kb.id] || []" :key="doc.id" style="margin-bottom: 6px">
              <el-icon style="margin-right: 6px"><Document /></el-icon>{{ cleanName(doc.filename) }}
              <el-tag size="small" type="info" style="margin-left: 8px">{{ doc.file_type }}</el-tag>
              <el-tag size="small" style="margin-left: 4px">{{ doc.chunk_count }} 个知识切片</el-tag>
            </li>
          </ul>
          <span v-else style="color: #999">该知识库暂无文档</span>
        </el-collapse-item>
      </el-collapse>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import {onMounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import {kbApi} from '../api/endpoints'
import type {DocumentItem, KnowledgeBase} from '../types'

const kbs = ref<KnowledgeBase[]>([])
const docsMap = ref<Record<number, DocumentItem[]>>({})
const active = ref<string[]>([])
const loading = ref(true)

function cleanName(name: string) {
  return name.replace(/^seed_[a-f0-9]{8}_/, '')
}

onMounted(async () => {
  try {
    const list = await kbApi.list()
    kbs.value = list
    active.value = list.map((kb) => String(kb.id))
    const entries = await Promise.all(
      list.map(async (kb) => {
        try {
          return [kb.id, await kbApi.documents(kb.id)] as const
        } catch {
          return [kb.id, [] as DocumentItem[]] as const
        }
      }),
    )
    docsMap.value = Object.fromEntries(entries)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
})
</script>
