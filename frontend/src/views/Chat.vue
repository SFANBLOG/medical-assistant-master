<template>
  <div class="chat-page">
    <!-- 移动端遮罩 -->
    <div
      v-if="showMobileList && isMobile"
      class="mask"
      @click="showMobileList = false"
    ></div>

    <!-- 会话列表 -->
    <div class="conv-panel" :class="{ show: showMobileList }">
      <div class="conv-header">
        <span class="conv-title">会话列表</span>
        <el-button type="primary" size="small" :icon="'Plus'" @click="newConversation">
          新对话
        </el-button>
      </div>
      <el-scrollbar class="conv-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: currentConv?.id === conv.id }"
          @click="selectConversation(conv)"
        >
          <div class="conv-item-main">
            <div class="conv-item-title text-ellipsis">{{ conv.title }}</div>
            <div class="conv-item-time">{{ formatTime(conv.updated_at || conv.created_at) }}</div>
          </div>
          <el-icon
            v-if="currentConv?.id !== conv.id"
            class="conv-del"
            @click.stop="handleDeleteConversation(conv)"
          >
            <Delete />
          </el-icon>
        </div>
        <el-empty
          v-if="!conversations.length"
          description="暂无会话，点击「新对话」开始"
          :image-size="60"
        />
      </el-scrollbar>
    </div>

    <!-- 聊天区 -->
    <div class="chat-main">
      <!-- 顶栏 -->
      <div class="chat-topbar">
        <el-button
          v-if="isMobile"
          text
          class="mobile-toggle"
          @click="showMobileList = true"
        >
          <el-icon :size="18"><Menu /></el-icon>
        </el-button>
        <div class="conv-name text-ellipsis">
          {{ currentConv ? currentConv.title : '新对话' }}
        </div>
        <div class="topbar-right">
          <span class="kb-label">知识库</span>
          <el-select
            v-model="selectedKbId"
            placeholder="选择知识库"
            clearable
            size="small"
            style="width: 180px"
            popper-class="kb-select-popper"
          >
            <!-- 通用知识库：固定排在最前，作为兜底选项 -->
            <el-option
              :key="GENERAL_KB_ID"
              :value="GENERAL_KB_ID"
              :label="GENERAL_KB_LABEL"
            >
              <span class="kb-option-row">
                <el-icon class="kb-option-icon"><Files /></el-icon>
                <span>{{ GENERAL_KB_LABEL }}</span>
                <el-tag size="small" type="success" effect="plain" class="kb-option-tag">
                  兜底
                </el-tag>
              </span>
            </el-option>
            <el-option
              v-for="kb in kbs"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            />
          </el-select>
          <!-- 通用知识库快捷按钮：忘记选具体 KB 时一键兜底 -->
          <el-button
            size="small"
            :type="selectedKbId === GENERAL_KB_ID ? 'primary' : 'default'"
            :plain="selectedKbId !== GENERAL_KB_ID"
            class="general-kb-btn"
            title="通用知识库：兜底检索所有可见知识库（适用于忘记选择具体知识库、不确定对应疾病的患者和群众）"
            @click="toggleGeneralKb"
          >
            <el-icon class="general-kb-btn-icon"><Files /></el-icon>
            <span class="general-kb-btn-text">通用</span>
          </el-button>
          <el-button
            v-if="currentConv"
            type="danger"
            text
            :icon="'Delete'"
            @click="handleDeleteConversation(currentConv)"
          >
            删除
          </el-button>
        </div>
      </div>

      <!-- 消息区 -->
      <div ref="chatBodyRef" class="chat-body">
        <div v-if="!messages.length" class="welcome">
          <div class="welcome-icon">
            <el-icon :size="44"><FirstAidKit /></el-icon>
          </div>
          <h2>你好，{{ displayName }}</h2>
          <p>我是医智助手智能问诊助理，可以帮你解答医疗健康问题。</p>

          <!-- 当前生效的知识库：让用户清楚自己在问哪个范围 -->
          <div class="welcome-kb">
            <span class="welcome-kb-label">当前检索范围</span>
            <el-tag
              :type="selectedKbId === undefined || selectedKbId === null ? 'info' : 'primary'"
              effect="light"
              round
              size="small"
            >
              {{ currentKbLabel }}
            </el-tag>
            <span
              v-if="selectedKbId === GENERAL_KB_ID || selectedKbId === undefined || selectedKbId === null"
              class="welcome-kb-tip"
            >
              {{ selectedKbId === GENERAL_KB_ID
                  ? '已启用通用检索，会基于所有可见知识库给出答案'
                  : '可在右上角选择「通用知识库」一键兜底检索' }}
            </span>
          </div>

          <div class="suggestions">
            <div
              v-for="s in suggestions"
              :key="s"
              class="suggestion"
              @click="inputText = s"
            >
              {{ s }}
            </div>
          </div>
        </div>
        <ChatMessage v-for="(m, i) in messages" :key="m.id || i" :message="m" />
      </div>

      <!-- 输入区 -->
      <div class="chat-input">
        <div class="input-box">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            :autosize="{ minRows: 2, maxRows: 6 }"
            resize="none"
            placeholder="请输入你的医疗健康问题，Enter 发送，Shift+Enter 换行"
            :disabled="sending"
            @keydown="handleKeydown"
          />
          <div class="input-footer">
            <span class="input-tip">内容仅供健康参考，不能替代专业医疗诊断</span>
            <el-button
              type="primary"
              :loading="sending"
              :disabled="!inputText.trim()"
              @click="sendMessage"
            >
              <el-icon class="send-icon"><Promotion /></el-icon>
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { chatApi, kbApi, chatStreamUrl, authHeaders } from '@/api'
import type { Conversation, Message, KnowledgeBase } from '@/types'
import { useAuthStore } from '@/stores/auth'
import ChatMessage from '@/components/ChatMessage.vue'

const auth = useAuthStore()
const displayName = computed(
  () => auth.user?.display_name || auth.user?.username || '用户',
)

// ---- 知识库：通用选项哨兵 ----
// kb_id=0 是一个约定值，后端 retriever 会识别为「按角色搜索全部可访问知识库」，
// 用于兜底：用户忘记选具体知识库、不确定疾病分类的患者/群众也能拿到合适答案。
const GENERAL_KB_ID = 0 as const
const GENERAL_KB_LABEL = '通用知识库（兜底）'

const isMobile = ref(false)
const showMobileList = ref(false)

function checkMobile() {
  isMobile.value = window.innerWidth < 768
}
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  loadConversations()
  loadKbs()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', checkMobile)
})

const conversations = ref<Conversation[]>([])
const currentConv = ref<Conversation | null>(null)
const messages = ref<Message[]>([])
// kb 选项：通用知识库 id 固定为 0，作为兜底选项排在最前
const kbs = ref<KnowledgeBase[]>([])
const selectedKbId = ref<number | undefined | null>(undefined)
const inputText = ref('')
const sending = ref(false)
const chatBodyRef = ref<HTMLElement>()

const suggestions = [
  '感冒发烧应该注意什么？',
  '高血压患者的日常饮食建议',
  '糖尿病患者可以吃水果吗？',
  '体检报告中的脂肪肝严重吗？',
]

// 当前生效的 KB 名（含通用兜底/未选状态）
const currentKbLabel = computed(() => {
  const v = selectedKbId.value
  if (v === GENERAL_KB_ID) return GENERAL_KB_LABEL
  if (v === undefined || v === null) return '通用知识库（默认）'
  const hit = kbs.value.find((k) => k.id === v)
  return hit ? hit.name : `知识库#${v}`
})

/** 一键切换到通用知识库（已选中则取消，回到默认）。 */
function toggleGeneralKb() {
  if (selectedKbId.value === GENERAL_KB_ID) {
    selectedKbId.value = undefined
  } else {
    selectedKbId.value = GENERAL_KB_ID
    ElMessage.info('已启用通用知识库，将基于所有可见知识库给出回答')
  }
}

/* ---------- 数据加载 ---------- */
async function loadConversations() {
  try {
    conversations.value = await chatApi.listConversations()
  } catch {
    /* 列表失败不阻塞页面 */
  }
}

async function loadKbs() {
  try {
    const res = await kbApi.listKb({ page: 1, size: 100 })
    kbs.value = res.list || []
  } catch {
    /* 忽略 */
  }
}

/* ---------- 会话操作 ---------- */
function newConversation() {
  currentConv.value = null
  messages.value = []
  inputText.value = ''
  // selectedKbId 故意保留，跨会话复用同一检索范围
  showMobileList.value = false
}

async function selectConversation(conv: Conversation) {
  currentConv.value = conv
  // 历史会话记录了具体的 kb_id；null/undefined 表示当时用的就是通用兜底
  selectedKbId.value = conv.kb_id ?? undefined
  messages.value = []
  showMobileList.value = false
  try {
    const detail = await chatApi.getConversation(conv.id)
    messages.value = (detail.messages || []).map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content || '',
    }))
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '加载会话失败')
  }
  scrollToBottom()
}

async function handleDeleteConversation(conv: Conversation) {
  try {
    await ElMessageBox.confirm('确定删除该会话吗？删除后不可恢复。', '提示', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await chatApi.deleteConversation(conv.id)
    conversations.value = conversations.value.filter((c) => c.id !== conv.id)
    if (currentConv.value?.id === conv.id) {
      newConversation()
    }
    ElMessage.success('会话已删除')
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '删除失败')
  }
}

/* ---------- 发送消息（SSE 流式） ---------- */
// 计算最终发送到后端的 kb_id。
// - undefined/null  → 让后端沿用会话/角色默认值（与原有行为一致）
// - GENERAL_KB_ID(0)→ 后端按角色检索全部可访问知识库（兜底）
// - 其他正整数      → 指定单一知识库
function _resolveKbId(): number | null {
  const v = selectedKbId.value
  if (v === undefined || v === null) return null
  return typeof v === 'number' ? v : null
}

async function ensureConversation(): Promise<string> {
  if (currentConv.value) return currentConv.value.id
  const q = inputText.value.trim()
  const kb_id = _resolveKbId()
  const res = await chatApi.createConversation({
    kb_id,
    title: q.slice(0, 30) || '新对话',
  })
  const conv: Conversation = {
    id: res.id,
    user_id: res.user_id ?? 0,
    kb_id,
    title: res.title || '新对话',
  }
  currentConv.value = conv
  conversations.value.unshift(conv)
  return conv.id
}

async function sendMessage() {
  const q = inputText.value.trim()
  if (!q || sending.value) return

  inputText.value = ''
  sending.value = true

  const userMsg: Message = { role: 'user', content: q }
  const aiMsg = reactive<Message>({
    role: 'assistant',
    content: '',
    streaming: true,
    citations: [],
  })
  messages.value.push(userMsg, aiMsg)
  scrollToBottom()

  try {
    const convId = await ensureConversation()
    await streamChat(convId, q, aiMsg)
  } catch (e: unknown) {
    aiMsg.streaming = false
    aiMsg.error = true
    aiMsg.content = (e as Error).message || '发送失败'
    ElMessage.error((e as Error).message || '发送失败')
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

async function streamChat(convId: string, question: string, aiMsg: Message) {
  const resp = await fetch(chatStreamUrl(convId), {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      question,
      kb_id: _resolveKbId(),
    }),
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`请求失败（${resp.status}）`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let sepIdx: number
    while ((sepIdx = buffer.indexOf('\n\n')) >= 0) {
      const rawEvent = buffer.slice(0, sepIdx).trim()
      buffer = buffer.slice(sepIdx + 2)
      if (!rawEvent.startsWith('data:')) continue

      const jsonStr = rawEvent.slice(5).trim()
      let data: Record<string, unknown>
      try {
        data = JSON.parse(jsonStr)
      } catch {
        continue
      }

      if (Array.isArray(data.citations)) {
        aiMsg.citations = data.citations as Message['citations']
      }
      if (typeof data.content === 'string' && data.content) {
        aiMsg.content += data.content
        scrollToBottom()
      }
      if (typeof data.error === 'string') {
        aiMsg.error = true
        if (!aiMsg.content) aiMsg.content = data.error
      }
      if (data.done === true) {
        aiMsg.streaming = false
      }
    }
  }

  // 流结束兜底：做一次展示层净化，剥离可能残留的 markdown/列表符号
  aiMsg.content = cleanDisplayedAnswer(aiMsg.content)
  aiMsg.streaming = false

  // 刷新会话标题与列表排序
  await loadConversations()
  const updated = conversations.value.find((c) => c.id === convId)
  if (updated && currentConv.value) {
    currentConv.value = updated
  }
}

/**
 * 展示层兜底清洗：剥除遗留的 ** # ` 等 markdown 与列表符号。
 * 后端已经做过一轮清洗；这里是防御性的二次处理（应对历史消息）。
 */
function cleanDisplayedAnswer(text: string): string {
  if (!text) return text
  let s = text
  s = s.replace(/\*\*(.+?)\*\*/g, '$1')
  s = s.replace(/__(.+?)__/g, '$1')
  s = s.replace(/`([^`]+)`/g, '$1')
  s = s.replace(/^\s{0,3}#{1,6}\s*/gm, '')
  s = s.replace(/^\s*(?:[-*•]|\d{1,3}\.)\s+/gm, '')
  s = s.replace(/\n{3,}/g, '\n\n')
  return s.trim()
}

/* ---------- 其他 ---------- */
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    sendMessage()
  }
}

function scrollToBottom() {
  nextTick(() => {
    const el = chatBodyRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function formatTime(t?: string): string {
  if (!t) return ''
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  if (sameDay) return `${hh}:${mm}`
  return `${d.getMonth() + 1}/${d.getDate()}`
}
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  min-height: 0;
  position: relative;
}

/* ---- 会话列表 ---- */
.conv-panel {
  width: 260px;
  min-width: 260px;
  background: #fff;
  border-right: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
  z-index: 20;
}

.conv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.conv-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.conv-list {
  flex: 1;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 14px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.15s;
}

.conv-item:hover {
  background: #f5f7fa;
}

.conv-item.active {
  background: #ecf5ff;
  border-left-color: #409eff;
}

.conv-item-main {
  flex: 1;
  min-width: 0;
}

.conv-item-title {
  font-size: 14px;
  color: #303133;
}

.conv-item-time {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 3px;
}

.conv-del {
  color: #c0c4cc;
  visibility: hidden;
  flex-shrink: 0;
}

.conv-item:hover .conv-del {
  visibility: visible;
}

.conv-del:hover {
  color: #f56c6c;
}

/* ---- 聊天主区 ---- */
.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #f7f9fc;
}

.chat-topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
  min-height: 50px;
}

.conv-name {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kb-label {
  font-size: 13px;
  color: #909399;
}

/* 通用知识库下拉选项 */
.kb-option-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.kb-option-icon {
  color: #67c23a;
}
.kb-option-tag {
  margin-left: 4px;
}

/* 通用知识库快捷按钮 */
.general-kb-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.general-kb-btn-icon {
  margin-right: 2px;
}
@media (max-width: 600px) {
  .general-kb-btn-text {
    display: none;
  }
}

.mobile-toggle {
  display: none;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
}

/* 欢迎区 */
.welcome {
  max-width: 560px;
  margin: 60px auto;
  text-align: center;
}

.welcome-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto;
  border-radius: 20px;
  background: linear-gradient(135deg, #409eff, #79bbff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 20px rgba(64, 158, 255, 0.35);
}

.welcome h2 {
  margin: 16px 0 8px;
  color: #303133;
}

.welcome p {
  color: #909399;
  font-size: 14px;
}

.welcome-kb {
  margin: 18px auto 0;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
}
.welcome-kb-label {
  font-size: 12px;
  color: #909399;
}
.welcome-kb-tip {
  font-size: 12px;
  color: #67c23a;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-top: 20px;
}

.suggestion {
  padding: 8px 14px;
  background: #fff;
  border: 1px solid var(--el-border-color-light);
  border-radius: 18px;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion:hover {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}

/* 输入区 */
.chat-input {
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid var(--el-border-color-light);
}

.input-box {
  max-width: 900px;
  margin: 0 auto;
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.input-tip {
  font-size: 12px;
  color: #c0c4cc;
}

.send-icon {
  margin-right: 4px;
}

/* 遮罩 */
.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 15;
}

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .conv-panel {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    transform: translateX(-100%);
    transition: transform 0.3s;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.12);
  }

  .conv-panel.show {
    transform: translateX(0);
  }

  .mobile-toggle {
    display: inline-flex;
  }

  .kb-label {
    display: none;
  }

  .chat-body {
    padding: 16px 12px;
  }

  .bubble-wrap {
    max-width: 88%;
  }
}
</style>
