<template>
  <div>
    <el-card shadow="never">
      <template #header>咨询历史</template>
      <el-empty v-if="!list.length" description="暂无咨询记录" />
      <el-table v-else :data="list" @row-click="open">
        <el-table-column prop="title" label="咨询主题" min-width="240" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default><el-button text type="primary">查看</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="visible" :title="cur.title" width="720px">
      <div v-for="(m, i) in msgs" :key="i" :class="['bubble', m.role]">
        <b>{{ m.role === 'user' ? '我' : '医智助手' }}：</b>{{ m.content }}
      </div>
      <template #footer><el-button @click="visible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const list = ref([])
const visible = ref(false)
const cur = ref({})
const msgs = ref([])

onMounted(async () => {
  try { const r = await api.history(); if (r.ok) list.value = r.data } catch (e) {}
})

async function open(row) {
  cur.value = row
  try {
    const r = await api.conversation(row.id)
    if (r.ok) msgs.value = r.data.messages
  } catch (e) {}
  visible.value = true
}
</script>

<style scoped>
.bubble { padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; line-height: 1.7; white-space: pre-wrap; }
.bubble.user { background: #ecf5ff; }
.bubble.assistant { background: #f4f4f5; }
</style>
