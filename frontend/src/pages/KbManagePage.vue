<template>
  <el-card>
    <template #header>
      <div style="display: flex; align-items: center; justify-content: space-between">
        <span>知识库管理</span>
        <el-button type="primary" @click="createOpen = true"><el-icon><Plus /></el-icon>&nbsp;新建知识库</el-button>
      </div>
    </template>

    <el-table :data="kbs" v-loading="loading" row-key="id">
      <el-table-column label="名称" min-width="200">
        <template #default="{ row }"><strong>{{ row.name }}</strong></template>
      </el-table-column>
      <el-table-column label="可见性" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.visibility === 'public'" type="success">公开</el-tag>
          <el-tag v-else type="info">私有</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="文档数" prop="doc_count" width="90" align="center" />
      <el-table-column label="向量切片" prop="chunk_count" width="100" align="center" />
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="210">
        <template #default="{ row }">
          <el-button size="small" @click="openDocs(row)">
            <el-icon><Document /></el-icon>&nbsp;管理文档
          </el-button>
          <el-button size="small" type="danger" link @click="removeKb(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建知识库 -->
    <el-dialog v-model="createOpen" title="新建知识库" width="480px">
      <el-form :model="createForm" label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="如：内分泌代谢疾病" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
        <el-form-item label="可见性">
          <el-select v-model="createForm.visibility" :disabled="!isDoctor" style="width: 100%">
            <el-option value="private" label="私有（仅自己可见）" />
            <el-option value="public" label="公开（所有人可见）" />
          </el-select>
          <p style="font-size: 12px; color: #999; margin: 6px 0 0">
            {{ isDoctor ? '医生可将知识库设为公开，供所有用户咨询' : '患者身份仅可创建私有知识库' }}
          </p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" @click="createKb">创建</el-button>
      </template>
    </el-dialog>

    <!-- 文档管理 -->
    <el-drawer v-model="drawerOpen" :title="drawerKb ? `管理文档 - ${drawerKb.name}` : '管理文档'" size="640px">
      <div style="display: flex; gap: 8px; margin-bottom: 12px">
        <el-radio-group v-model="uploadVisibility">
          <el-radio-button value="public">公开文档</el-radio-button>
          <el-radio-button value="private">私有文档</el-radio-button>
        </el-radio-group>
        <el-upload :show-file-list="false" :before-upload="handleUpload" :disabled="uploading" multiple>
          <el-button type="primary" :loading="uploading">
            <el-icon><Upload /></el-icon>&nbsp;上传文档
          </el-button>
        </el-upload>
      </div>
      <el-alert type="info" :closable="false" style="margin-bottom: 12px"
        :title="`公开文档存入「${drawerKb?.name}/公开/」，患者、群众可查询；私有文档存入「${drawerKb?.name}/私有/」，仅医生/管理员可见。支持 .txt / .md / .pdf / .docx / .pptx，单文件不超过 20MB。`" />
      <el-table :data="docs" v-loading="docsLoading" row-key="id" size="small">
        <el-table-column label="文件名" prop="filename" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" prop="file_type" width="70" />
        <el-table-column label="可见性" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.visibility === 'public'" size="small" type="success">公开</el-tag>
            <el-tag v-else size="small" type="info">私有</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tooltip v-if="row.status === 'failed' && row.error" :content="row.error" placement="top">
              <el-tag size="small" type="danger">失败</el-tag>
            </el-tooltip>
            <el-tag v-else-if="row.status === 'ready'" size="small" type="success">已完成</el-tag>
            <el-tag v-else size="small" type="info">处理中</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="切片数" prop="chunk_count" width="80" align="center" />
        <el-table-column label="上传时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="70">
          <template #default="{ row }">
            <el-button size="small" type="danger" link @click="removeDoc(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { kbApi } from '../api/endpoints'
import { useAuth } from '../stores/auth'
import type { DocumentItem, KnowledgeBase, Visibility } from '../types'

const auth = useAuth()
const isDoctor = auth.user?.role === 'doctor'
const kbs = ref<KnowledgeBase[]>([])
const loading = ref(false)
const createOpen = ref(false)
const createForm = reactive({ name: '', description: '', visibility: 'private' })

const drawerOpen = ref(false)
const drawerKb = ref<KnowledgeBase | null>(null)
const docs = ref<DocumentItem[]>([])
const docsLoading = ref(false)
const uploading = ref(false)
const uploadVisibility = ref<Visibility>('public')

function formatTime(v: string) {
  return v ? v.replace('T', ' ').slice(0, 19) : ''
}

async function load() {
  loading.value = true
  try {
    kbs.value = await kbApi.list()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function createKb() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  try {
    await kbApi.create({ name: createForm.name, description: createForm.description, visibility: createForm.visibility })
    ElMessage.success('创建成功')
    createOpen.value = false
    createForm.name = ''
    createForm.description = ''
    createForm.visibility = 'private'
    load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function removeKb(kb: KnowledgeBase) {
  try {
    await ElMessageBox.confirm(`删除知识库「${kb.name}」？将同时删除其全部文档与向量数据，该操作不可恢复。`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await kbApi.remove(kb.id)
    ElMessage.success('已删除')
    if (drawerKb.value?.id === kb.id) {
      drawerOpen.value = false
      drawerKb.value = null
    }
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error((e as Error).message)
  }
}

async function openDocs(kb: KnowledgeBase) {
  drawerKb.value = kb
  drawerOpen.value = true
  uploadVisibility.value = kb.visibility
  docsLoading.value = true
  try {
    docs.value = await kbApi.documents(kb.id)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    docsLoading.value = false
  }
}

async function loadDocs() {
  if (!drawerKb.value) return
  try {
    docs.value = await kbApi.documents(drawerKb.value.id)
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function handleUpload(file: File) {
  if (!drawerKb.value) return false
  uploading.value = true
  try {
    const doc = await kbApi.uploadDoc(drawerKb.value.id, file, uploadVisibility.value)
    if (doc.status === 'failed') {
      ElMessage.error(`「${doc.filename}」上传失败：${doc.error || '处理出错'}`)
    } else {
      ElMessage.success(`「${doc.filename}」处理完成，共 ${doc.chunk_count} 个向量切片`)
    }
    loadDocs()
    load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    uploading.value = false
  }
  return false
}

async function removeDoc(docId: number) {
  if (!drawerKb.value) return
  try {
    await ElMessageBox.confirm('确定删除该文档？', '提示', { type: 'warning' })
    await kbApi.deleteDoc(drawerKb.value.id, docId)
    ElMessage.success('已删除')
    loadDocs()
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error((e as Error).message)
  }
}
</script>
