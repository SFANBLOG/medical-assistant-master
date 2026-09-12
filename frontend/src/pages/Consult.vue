<template>
  <div class="consult">
    <el-row :gutter="16">
      <el-col :span="16">
        <el-card shadow="never" class="chat-card">
          <div class="q-box">
            <el-input v-model="question" type="textarea" :rows="3" placeholder="请输入您的医学咨询问题，例如：感冒有哪些常见症状？" />
            <div class="q-actions">
              <el-select v-model="kbId" placeholder="不限知识库" clearable style="width:240px">
                <el-option v-for="k in kbs" :key="k.id" :label="k.name + (k.visibility === 'private' ? '（私有）' : '（公开）')" :value="k.id" />
              </el-select>
              <el-button type="primary" :loading="loading" @click="ask">发送咨询</el-button>
              <el-button @click="reset">清空</el-button>
            </div>
          </div>

          <div v-if="answer || loading" class="answer">
            <div class="a-title">回答（流式）</div>
            <div class="a-body">{{ answer }}<span v-if="loading" class="cursor">▍</span></div>
          </div>
          <el-empty v-else description="向医智助手提问，获取基于知识库的可追溯回答" />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never" class="cite-card">
          <template #header>引用来源（按相似度排序）</template>
          <el-alert v-if="!citations.length" :closable="false" type="info" title="暂无引用" />
          <div v-for="(c, i) in citations" :key="i" class="cite">
            <div class="cite-head">
              <span class="idx">{{ i + 1 }}</span>
              <span class="ct">{{ c.title }}</span>
              <el-tag :type="c.similarity >= 0.95 ? 'success' : 'info'" size="small">
                相似度 {{ (c.similarity * 100).toFixed(1) }}%
              </el-tag>
            </div>
            <div class="snippet">{{ c.snippet }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api, consultStream } from '../api'

const question = ref('')
const answer = ref('')
const loading = ref(false)
const citations = ref([])
const kbs = ref([])
const kbId = ref(null)

onMounted(async () => {
  try { const r = await api.listKB(); if (r.ok) kbs.value = r.data } catch (e) {}
})

async function ask() {
  if (!question.value.trim()) return ElMessage.warning('请输入问题')
  loading.value = true
  answer.value = ''
  citations.value = []
  try {
    await consultStream(question.value, kbId.value, (ev) => {
      if (ev.type === 'retrieval') citations.value = ev.chunks || []
      else if (ev.type === 'token') answer.value += ev.content
      else if (ev.type === 'done') { /* 完成 */ }
    })
  } catch (e) {
    ElMessage.error('咨询失败：' + e.message)
  } finally {
    loading.value = false
  }
}

function reset() { question.value = ''; answer.value = ''; citations.value = [] }
</script>

<style scoped>
.chat-card { min-height: 420px; }
.q-actions { display: flex; gap: 10px; margin-top: 10px; }
.answer { margin-top: 16px; border-top: 1px dashed #ebeef5; padding-top: 12px; }
.a-title { font-weight: 600; color: #409eff; margin-bottom: 6px; }
.a-body { white-space: pre-wrap; line-height: 1.7; }
.cursor { color: #409eff; }
.cite { border: 1px solid #ebeef5; border-radius: 6px; padding: 8px; margin-bottom: 8px; }
.cite-head { display: flex; align-items: center; gap: 8px; }
.idx { background: #409eff; color: #fff; border-radius: 50%; width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.ct { font-weight: 600; flex: 1; }
.snippet { color: #606266; font-size: 13px; margin-top: 6px; line-height: 1.6; max-height: 90px; overflow: auto; }
</style>
