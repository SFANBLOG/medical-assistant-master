<template>
  <el-card>
    <template #header>咨询历史</template>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px">
      <el-input v-model="q" placeholder="搜索会话标题" clearable style="width: 260px" @keyup.enter="doSearch" />
      <el-button type="primary" plain @click="doSearch">搜索</el-button>
      <el-tag>{{ total }} 条</el-tag>
    </div>
    <el-table :data="items" v-loading="loading" row-key="id">
      <el-table-column label="标题" min-width="200">
        <template #default="{ row }">
          <strong><el-icon style="margin-right: 6px"><Message /></el-icon>{{ row.title }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="知识库" prop="kb_name" width="180">
        <template #default="{ row }">{{ row.kb_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="消息数" prop="message_count" width="90" align="center" />
      <el-table-column label="更新时间" prop="updated_at" width="170" />
      <el-table-column label="操作" width="230">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="router.push(`/chat?conversation=${row.id}`)">
            继续咨询
          </el-button>
          <el-button size="small" type="primary" link @click="router.push(`/chat/history/${row.id}`)">
            查看记录
          </el-button>
          <el-button size="small" type="danger" link @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="prev, pager, next, total"
      style="margin-top: 16px; justify-content: flex-end" @current-change="load" />
  </el-card>
</template>

<script setup lang="ts">
import {onMounted, ref} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessage, ElMessageBox} from 'element-plus'
import {chatApi} from '../api/endpoints'
import type {Conversation} from '../types'

const router = useRouter()
const items = ref<Conversation[]>([])
const total = ref(0)
const q = ref('')
const page = ref(1)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await chatApi.conversations({ q: q.value, page: page.value, page_size: 10 })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function doSearch() {
  page.value = 1
  load()
}

async function remove(id: string) {
  try {
    await ElMessageBox.confirm('确定删除该会话？', '提示', { type: 'warning' })
    await chatApi.remove(id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error((e as Error).message)
  }
}
</script>
