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
        <input
          ref="fileInputRef"
          type="file"
          multiple
          class="hidden-file-input"
          accept=".txt,.md,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.html,.htm,.csv,.json,.xml,.log,.rtf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp,.gif,.py,.js,.ts,.java,.go,.sql,.yaml,.yml,.ini,.toml,.rst,.tex"
          @change="onFileSelected"
        />
        <el-button type="primary" size="small" :icon="'Upload'" @click="pickFiles">
          选择文档（可多选）
        </el-button>
        <el-button
          v-if="queue.length"
          type="success"
          size="small"
          :icon="'UploadFilled'"
          :loading="uploading"
          @click="handleBatchUpload"
        >
          上传 {{ queue.length }} 个文件
        </el-button>
        <el-button
          v-if="queue.length && !uploading"
          size="small"
          plain
          @click="clearQueue"
        >
          清空
        </el-button>
      </div>

      <!-- 待上传队列 -->
      <div v-if="queue.length" class="queue-panel">
        <div class="queue-title">待上传（{{ queue.length }}）</div>
        <div class="queue-list">
          <div v-for="(q, i) in queue" :key="q.key" class="queue-item">
            <el-icon class="qi-icon"><Document /></el-icon>
            <span class="qi-name text-ellipsis" :title="q.file.name">{{ q.file.name }}</span>
            <span class="qi-size">{{ fmtSize(q.file.size) }}</span>
            <span v-if="q.status === 'uploading'" class="qi-status uploading">
              <el-icon class="is-loading"><Loading /></el-icon>
              上传中
            </span>
            <span v-else-if="q.status === 'done'" class="qi-status done">
              <el-icon><CircleCheckFilled /></el-icon>
              {{ q.chunkCount }} 分片
            </span>
            <span v-else-if="q.status === 'failed'" class="qi-status failed" :title="q.error">
              <el-icon><CircleCloseFilled /></el-icon>
              失败
            </span>
            <el-button
              v-if="q.status !== 'uploading'"
              link
              size="small"
              type="danger"
              class="qi-rm"
              @click="removeFromQueue(i)"
            >
              移除
            </el-button>
          </div>
        </div>
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
import {computed, onMounted, reactive, ref} from 'vue'
import {ElMessage, ElMessageBox} from 'element-plus'
import {CircleCheckFilled, CircleCloseFilled, Document, Loading} from '@element-plus/icons-vue'
import {kbApi} from '@/api'
import type {DocumentItem, KnowledgeBase} from '@/types'
import {formatDate} from '@/utils/format'

/** 队列里单个文件的状态 */
interface QueueItem {
  key: string
  file: File
  status: 'queued' | 'uploading' | 'done' | 'failed'
  chunkCount?: number
  error?: string
}

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

/* ---- 上传队列（支持批量上传） ---- */
const fileInputRef = ref<HTMLInputElement | null>(null)
const queue = ref<QueueItem[]>([])

function pickFiles() {
  if (uploading.value) return
  fileInputRef.value?.click()
}

function onFileSelected(ev: Event) {
  const input = ev.target as HTMLInputElement
  if (!input.files || input.files.length === 0) return
  const added: QueueItem[] = []
  const seen = new Set(queue.value.map((q) => q.file.name))
  for (const f of Array.from(input.files)) {
    if (seen.has(f.name)) continue
    seen.add(f.name)
    added.push({
      key: `${f.name}-${f.size}-${f.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
      file: f,
      status: 'queued',
    })
  }
  queue.value.push(...added)
  // 重置 input 以便下次能再次选同名同大小的文件
  input.value = ''
}

function removeFromQueue(index: number) {
  queue.value.splice(index, 1)
}

function clearQueue() {
  queue.value = []
}

/** 大小格式化（B/KB/MB） */
function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

/**
 * 批量上传：一次请求提交队列里所有文件，单文件失败不影响其它。
 */
async function handleBatchUpload() {
  if (!currentKb.value || queue.value.length === 0) return
  // 锁定所有 queued → uploading
  const snapshot = queue.value.slice()
  for (const q of snapshot) {
    if (q.status === 'queued') q.status = 'uploading'
  }
  uploading.value = true
  uploadMsg.value = ''
  uploadError.value = false
  try {
    const res = await kbApi.uploadDocuments(
      currentKb.value.id,
      snapshot.map((q) => q.file),
      uploadVisibility.value,
    )
    // 把每个结果回写到对应的 queue item
    const byName = new Map<string, (typeof res.results)[number]>()
    for (const r of res.results) byName.set(r.filename, r)
    for (const q of snapshot) {
      const r = byName.get(q.file.name)
      if (!r || !r.ok) {
        q.status = 'failed'
        q.error = r?.error || '未知错误'
        continue
      }
      q.status = 'done'
      q.chunkCount = r.chunk_count
    }
    const s = res.summary
    if (s.failed === 0) {
      uploadMsg.value = `批量上传完成：${s.success} 个成功，共 ${s.success} 个`
      uploadError.value = false
      ElMessage.success(`成功上传 ${s.success} 个文档`)
    } else {
      uploadMsg.value = `批量上传：成功 ${s.success} / 失败 ${s.failed}（点击每行的 ✕ 查看错误）`
      uploadError.value = true
      ElMessage.warning(`成功 ${s.success}、失败 ${s.failed}`)
    }
    // 成功完成的从队列移除；失败保留以便用户重试
    queue.value = queue.value.filter((q) => q.status !== 'done')
    loadDocs(1)
    load()
  } catch (e: unknown) {
    uploadMsg.value = (e as Error).message || '批量上传失败'
    uploadError.value = true
    // 全部标失败
    for (const q of snapshot) {
      if (q.status === 'uploading') {
        q.status = 'failed'
        q.error = uploadMsg.value
      }
    }
  } finally {
    uploading.value = false
  }
}

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

.hidden-file-input {
  display: none;
}

.queue-panel {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
  margin-bottom: 12px;
  overflow: hidden;
}

.queue-title {
  padding: 8px 12px;
  font-size: 12px;
  color: #909399;
  border-bottom: 1px solid #ebeef5;
  background: #fff;
}

.queue-list {
  max-height: 220px;
  overflow-y: auto;
}

.queue-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px dashed #ebeef5;
  font-size: 13px;
  color: #606266;
}

.queue-item:last-child {
  border-bottom: 0;
}

.qi-icon {
  color: #409eff;
  flex: 0 0 auto;
}

.qi-name {
  flex: 1;
  min-width: 0;
}

.qi-size {
  color: #909399;
  font-size: 12px;
  flex: 0 0 auto;
}

.qi-status {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  flex: 0 0 auto;
}

.qi-status.uploading {
  color: #409eff;
}

.qi-status.done {
  color: #67c23a;
}

.qi-status.failed {
  color: #f56c6c;
}

.qi-rm {
  flex: 0 0 auto;
}

.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
