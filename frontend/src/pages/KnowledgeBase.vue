<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header>
        <div class="hd">
          <span>知识库管理</span>
          <div>
            <el-button type="primary" @click="showCreate = true">新建知识库</el-button>
            <el-button @click="doReindex" :loading="reindexing">重新索引</el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col v-for="k in kbs" :key="k.id" :span="8">
          <el-card shadow="hover" class="kb">
            <div class="kb-name">{{ k.name }}
              <el-tag size="small" :type="k.visibility === 'public' ? 'success' : 'warning'">
                {{ k.visibility === 'public' ? '公开' : '私有' }}
              </el-tag>
            </div>
            <div class="kb-meta">文档数：{{ k.doc_count }}</div>
            <el-upload
              :show-file-list="false"
              :before-upload="(f) => upload(f, k)"
              accept=".txt,.md,.pdf,.docx,.pptx"
            >
              <el-button size="small" type="primary">上传文档</el-button>
            </el-upload>
            <div class="hint">支持 txt / md / pdf / docx / pptx</div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="never">
      <template #header>文档列表</template>
      <el-table :data="docs" style="width:100%">
        <el-table-column prop="filename" label="文件名" min-width="200" />
        <el-table-column prop="file_type" label="类型" width="90" />
        <el-table-column label="可见性" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.visibility === 'public' ? 'success' : 'warning'">{{ row.visibility === 'public' ? '公开' : '私有' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" width="90" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'ready'" type="success">已就绪</el-tag>
            <el-tag v-else-if="row.status === 'failed'" type="danger">失败</el-tag>
            <el-tag v-else type="info">处理中</el-tag>
            <div v-if="row.status === 'failed'" class="err">{{ row.error }}</div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showCreate" title="新建知识库" width="420px">
      <el-form :model="form">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="form.visibility">
            <el-radio value="public">公开</el-radio>
            <el-radio value="private">私有</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const kbs = ref([])
const docs = ref([])
const showCreate = ref(false)
const reindexing = ref(false)
const form = ref({ name: '', description: '', visibility: 'public' })

onMounted(refresh)

async function refresh() {
  try { const r = await api.listKB(); if (r.ok) kbs.value = r.data } catch (e) {}
  try { const r = await api.listDocs(); if (r.ok) docs.value = r.data } catch (e) {}
}

async function create() {
  if (!form.value.name) return ElMessage.warning('请输入名称')
  const r = await api.createKB(form.value)
  if (r.ok) { ElMessage.success('创建成功'); showCreate.value = false; refresh() }
  else ElMessage.error(r.error || '创建失败')
}

async function upload(file, kb) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('kb_id', kb.id)
  fd.append('visibility', 'public')
  const r = await api.uploadDoc(fd)
  if (r.ok) ElMessage.success(`《${file.name}》处理完成（${r.data.chunk_count || 0} 块）`)
  else ElMessage.error((r.error || '上传失败') + (r.data?.error ? '：' + r.data.error : ''))
  refresh()
  return false // 阻止 el-upload 自动上传
}

async function doReindex() {
  reindexing.value = true
  try { const r = await api.reindex(); if (r.ok) ElMessage.success(`索引完成：${r.data.indexed} 篇`) } catch (e) {}
  finally { reindexing.value = false; refresh() }
}
</script>

<style scoped>
.hd { display: flex; justify-content: space-between; align-items: center; }
.kb { margin-bottom: 8px; }
.kb-name { font-weight: 700; display: flex; gap: 8px; align-items: center; }
.kb-meta { color: #909399; font-size: 13px; margin: 8px 0; }
.hint { color: #c0c4cc; font-size: 12px; margin-top: 6px; }
.err { color: #f56c6c; font-size: 12px; margin-top: 4px; }
</style>
