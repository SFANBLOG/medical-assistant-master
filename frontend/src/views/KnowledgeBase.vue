<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">知识库管理</h2>
      <div class="spacer"></div>
      <el-input
        v-model="searchText"
        placeholder="搜索知识库"
        clearable
        :prefix-icon="'Search'"
        style="width: 200px"
      />
      <el-button type="primary" :icon="'Plus'" @click="createVisible = true">
        创建知识库
      </el-button>
    </div>

    <!-- 知识库卡片 -->
    <el-row :gutter="16">
      <el-col
        v-for="kb in filteredKbs"
        :key="kb.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
        class="kb-col"
      >
        <el-card shadow="hover" class="kb-card">
          <div class="kb-head">
            <div class="kb-icon">
              <el-icon :size="22"><Collection /></el-icon>
            </div>
            <el-tag size="small" :type="kb.visibility === 'public' ? 'success' : 'info'">
              {{ kb.visibility === 'public' ? '公开' : '私有' }}
            </el-tag>
          </div>
          <h3 class="kb-name text-ellipsis" :title="kb.name">{{ kb.name }}</h3>
          <p class="kb-desc">{{ kb.description || '暂无描述' }}</p>
          <div class="kb-meta">
            <span>文档 {{ kb.doc_count ?? 0 }}</span>
            <span>{{ kb.owner_name || '系统' }}</span>
            <span>{{ fmtDate(kb.created_at) }}</span>
          </div>
          <div class="kb-actions">
            <el-button size="small" type="primary" plain @click="openDocs(kb)">
              管理文档
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDeleteKb(kb)">
              删除
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-if="!filteredKbs.length" description="暂无知识库" />

    <!-- 创建知识库 -->
    <el-dialog v-model="createVisible" title="创建知识库" width="460px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="简要描述" />
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="createForm.visibility">
            <el-radio value="public">公开</el-radio>
            <el-radio value="private">私有</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 文档管理抽屉 -->
    <el-drawer v-model="docsVisible" :title="`文档管理 · ${currentKb?.name || ''}`" size="560px">
      <div class="doc-toolbar">
        <span class="doc-vis-label">上传可见性</span>
        <el-select v-model="uploadVisibility" size="small" style="width: 100px">
          <el-option label="公开" value="public" />
          <el-option label="私有" value="private" />
        </el-select>
        <el-upload
          :show-file-list="false"
          :http-request="handleUpload"
          :disabled="uploading"
          accept=".txt,.md,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.html,.htm,.csv,.json,.xml,.log,.rtf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp,.gif,.py,.js,.ts,.java,.go,.sql,.yaml,.yml,.ini,.toml,.rst,.tex"
        >
          <el-button type="primary" size="small" :loading="uploading" :icon="'Upload'">
            上传文档
          </el-button>
        </el-upload>
      </div>
      <el-alert
        v-if="uploadMsg"
        :title="uploadMsg"
        :type="uploadError ? 'error' : 'success'"
        :closable="true"
        show-icon
        class="upload-alert"
        @close="uploadMsg = ''"
      />

      <el-table :data="docList" v-loading="docsLoading" stripe size="small">
        <el-table-column prop="filename" label="文件名" min-width="160" show-overflow-tooltip />
        <el-table-column prop="file_type" label="类型" width="70" />
        <el-table-column prop="chunk_count" label="分片" width="70" align="center" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === 'ready' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'"
            >
              {{ row.status === 'ready' ? '就绪' : row.status === 'failed' ? '失败' : '处理中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="60">
          <template #default="{ row }">
            <el-button link type="danger" size="small" @click="handleDeleteDoc(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="total, prev, pager, next"
        :total="docTotal"
        :page-size="docQuery.size"
        :current-page="docQuery.page"
        @current-change="(p) => loadDocs(p)"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { kbApi } from '@/api'
import type { KnowledgeBase, DocumentItem } from '@/types'
import { formatDate } from '@/utils/format'

const loading = ref(false)
const searchText = ref('')
const kbs = ref<KnowledgeBase[]>([])

const filteredKbs = computed(() => {
  const kw = searchText.value.trim()
  if (!kw) return kbs.value
  return kbs.value.filter((kb) => kb.name.includes(kw))
})

/* 创建 */
const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({
  name: '',
  description: '',
  visibility: 'private' as 'public' | 'private',
})

/* 文档管理 */
const docsVisible = ref(false)
const currentKb = ref<KnowledgeBase | null>(null)
const docList = ref<DocumentItem[]>([])
const docTotal = ref(0)
const docQuery = reactive({ page: 1, size: 10 })
const docsLoading = ref(false)
const uploading = ref(false)
const uploadVisibility = ref<'public' | 'private'>('public')
const uploadMsg = ref('')
const uploadError = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await kbApi.listKb({ page: 1, size: 100 })
    kbs.value = res.list || []
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  creating.value = true
  try {
    await kbApi.createKb({ ...createForm })
    ElMessage.success('创建成功')
    createVisible.value = false
    createForm.name = ''
    createForm.description = ''
    load()
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleDeleteKb(kb: KnowledgeBase) {
  try {
    await ElMessageBox.confirm(
      `确定删除知识库「${kb.name}」吗？其下所有文档将一并删除，不可恢复。`,
      '提示',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await kbApi.deleteKb(kb.id)
    ElMessage.success('已删除')
    if (currentKb.value?.id === kb.id) docsVisible.value = false
    load()
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '删除失败')
  }
}

/* ---- 文档 ---- */
async function openDocs(kb: KnowledgeBase) {
  currentKb.value = kb
  docsVisible.value = true
  uploadMsg.value = ''
  loadDocs(1)
}

async function loadDocs(page = 1) {
  if (!currentKb.value) return
  docsLoading.value = true
  docQuery.page = page
  try {
    const res = await kbApi.listDocuments(currentKb.value.id, {
      page: docQuery.page,
      size: docQuery.size,
    })
    docList.value = res.list || []
    docTotal.value = res.total
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '加载文档失败')
  } finally {
    docsLoading.value = false
  }
}

async function handleUpload(options: {
  file: File
  onSuccess?: (body: unknown) => void
  onError?: (err: Error) => void
}) {
  if (!currentKb.value) return
  uploading.value = true
  uploadMsg.value = ''
  uploadError.value = false
  const fd = new FormData()
  fd.append('file', options.file)
  fd.append('visibility', uploadVisibility.value)
  try {
    const res = await kbApi.uploadDocument(currentKb.value.id, fd)
    uploadMsg.value = `「${options.file.name}」上传成功，已切分为 ${res.chunk_count} 个分片`
    uploadError.value = false
    options.onSuccess?.(res)
    loadDocs(1)
    load()
  } catch (e: unknown) {
    uploadMsg.value = (e as Error).message || '上传失败'
    uploadError.value = true
    options.onError?.(e as Error)
  } finally {
    uploading.value = false
  }
}

async function handleDeleteDoc(doc: DocumentItem) {
  try {
    await ElMessageBox.confirm(`确定删除文档「${doc.filename}」吗？`, '提示', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await kbApi.deleteDocument(doc.id)
    ElMessage.success('已删除')
    loadDocs(docQuery.page)
    load()
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '删除失败')
  }
}

const fmtDate = formatDate

onMounted(load)
</script>

<style scoped>
.kb-col {
  margin-bottom: 16px;
}

.kb-card {
  border-radius: 10px;
  cursor: default;
  transition: all 0.2s;
}

.kb-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}

.kb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.kb-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #ecf5ff;
  color: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kb-name {
  font-size: 16px;
  color: #303133;
  margin: 0 0 6px;
}

.kb-desc {
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
  min-height: 40px;
  margin: 0 0 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kb-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #c0c4cc;
  margin-bottom: 12px;
}

.kb-actions {
  display: flex;
  gap: 8px;
}

.doc-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.doc-vis-label {
  font-size: 13px;
  color: #909399;
}

.upload-alert {
  margin-bottom: 12px;
}

.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
