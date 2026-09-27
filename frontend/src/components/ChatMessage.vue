<template>
  <div class="msg-row" :class="message.role">
    <div class="avatar" :class="[message.role, message.role === 'user' ? `role-${auth.role}` : '']">
      <!-- 用户头像：根据角色显示不同图标 -->
      <el-icon v-if="message.role === 'user'" :size="18">
        <component :is="userRoleIcon" />
      </el-icon>
      <!-- AI 助手头像：专业医疗智能图标 -->
      <el-icon v-else :size="18"><Monitor /></el-icon>
    </div>

    <div class="bubble-wrap">
      <div class="bubble" :class="message.role">
        <!-- 打字中 -->
        <div v-if="message.streaming && !message.content" class="typing">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
        <!-- 内容：流式输出阶段按纯文本展示，避免半截标签；结束后渲染为结构化富文本 -->
        <div v-else-if="message.streaming" class="content">{{ message.content }}</div>
        <div v-else class="content rich" v-html="renderedHtml" @click="onContentClick"></div>
        <div v-if="message.error" class="err-tip">（本次回答可能不完整）</div>
      </div>

      <!-- 相关文档：回答生成后，列出与用户问题最相关的检索来源 -->
      <div
        v-if="
          message.role === 'assistant' &&
          relatedDocs.length > 0
        "
        class="citations"
        :id="'cites-' + msgKey"
      >
        <div class="cite-toggle" @click="citeVisible = !citeVisible">
          <el-icon><Document /></el-icon>
          <span>相关文档（与您问题最相关 · {{ relatedDocs.length }}）</span>
          <el-icon class="cite-arrow">
            <ArrowUp v-if="citeVisible" />
            <ArrowDown v-else />
          </el-icon>
        </div>
        <el-collapse-transition>
          <div v-show="citeVisible" class="cite-list">
            <div
              v-for="(c, i) in relatedDocs"
              :key="i"
              class="cite-item"
              :id="'cite-' + msgKey + '-' + i"
            >
              <div class="cite-head">
                <span class="cite-idx">[{{ i + 1 }}]</span>
                <span class="cite-title">{{ c.title || `文档 ${c.doc_id}` }}</span>
                <el-tag size="small" type="success" effect="plain">
                  相关度 {{ formatSimilarity(c.similarity) }}
                </el-tag>
              </div>
              <div class="cite-text">{{ c.source_text }}</div>
            </div>
          </div>
        </el-collapse-transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {computed, nextTick, ref} from 'vue'
import {ArrowDown, ArrowUp, Document, FirstAidKit, Monitor, User, UserFilled} from '@element-plus/icons-vue'
import type {Citation, Message} from '@/types'
import {renderRichText} from '@/utils/richtext'
import {useAuthStore} from '@/stores/auth'

const props = defineProps<{ message: Message }>()

const auth = useAuthStore()

const citeVisible = ref(true)

// 用户角色 → 图标映射（使用 Element Plus 实际存在的图标）
const USER_ROLE_ICONS: Record<string, any> = {
  patient: UserFilled,   // 患者：实心人形
  doctor: UserFilled,    // 医生：实心人形（用颜色区分）
  nurse: FirstAidKit,    // 护士：急救箱
  public: User,          // 群众：空心人形
  admin: UserFilled,     // 管理员：实心人形
}

const userRoleIcon = computed(() => USER_ROLE_ICONS[auth.role] || UserFilled)

// 同一会话内多条消息可能无 id，用稳定 key 给引用锚点命名，避免冲突
const msgKey = computed(() => props.message.id ?? 'm')

// 按文档标题聚合引用：保留首次出现顺序（与 LLM 正文 [n] 脚注顺序一致），
// 每篇文档取最相关的那一条片段作为代表。
const relatedDocs = computed(() => {
  const list = props.message.citations || []
  const seen = new Set<string>()
  const docs: Citation[] = []
  for (const c of list) {
    const title = c.title || `文档 ${c.doc_id}`
    if (seen.has(title)) continue
    seen.add(title)
    docs.push({ ...c, title })
  }
  // 显示所有引用文档（不再过滤低分文档）
  return docs
})

// 是否有可高亮/跳转的引用
const hasCitations = computed(() => relatedDocs.value.length > 0)

// 仅在回答完整（非流式）时渲染结构化富文本，避免流式半截标签导致排版错乱
const renderedHtml = computed(() => {
  if (props.message.streaming) return ''
  // 把正文中的 [1] [2] 等脚注标记高亮为可点击引用
  return highlightCitationMarkers(renderRichText(props.message.content))
})

/**
 * 将正文里的 [n]（n=1..99）数字脚注包裹为可点击的高亮脚注。
 * 输入为已 HTML 转义的安全文本，仅做最轻量的正则包裹，不引入任意标签。
 */
function highlightCitationMarkers(html: string): string {
  if (!hasCitations.value) return html
  return html.replace(/\[(\d{1,2})\]/g, (_m, n: string) => {
    return `<sup class="cite-ref" data-idx="${n}">[${n}]</sup>`
  })
}

// 直接显示后端返回的原始相似度分数（不再映射）
function toDisplaySimilarity(v: number | undefined): number {
  if (v === undefined || v === null) return 0
  const num = Number(v)
  // 兼容 0-1 与 0-100 两种量纲
  return num > 1 ? num / 100 : num
}

function formatSimilarity(v: number | undefined): string {
  const display = toDisplaySimilarity(v)
  if (display === 0) return '-'
  return `${(display * 100).toFixed(1)}%`
}

// 点击事件委托：点击正文中的 [n] 脚注 → 展开引用区并滚动/闪烁到对应卡片
function onContentClick(e: MouseEvent) {
  const el = (e.target as HTMLElement).closest('.cite-ref') as HTMLElement | null
  if (!el) return
  const idx = Number(el.getAttribute('data-idx'))
  if (idx) highlightCite(idx)
}

// 滚动到指定引用卡片并短暂高亮
function highlightCite(idx: number) {
  citeVisible.value = true
  nextTick(() => {
    const target = document.getElementById(`cite-${msgKey.value}-${idx - 1}`)
    if (!target) return
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    target.classList.add('cite-flash')
    window.setTimeout(() => target.classList.remove('cite-flash'), 1300)
  })
}
</script>

<style scoped>
.msg-row {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
  align-items: flex-start;
}

.msg-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

/* 用户头像：根据角色显示不同颜色 */
.avatar.user {
  background: #409eff;  /* 默认蓝色（患者/群众） */
}

.avatar.user.role-doctor {
  background: #67c23a;  /* 医生：绿色 */
}

.avatar.user.role-nurse {
  background: #e6a23c;  /* 护士：橙色 */
}

.avatar.user.role-admin {
  background: #9c27b0;  /* 管理员：紫色 */
}

/* AI 助手头像：专业医疗智能渐变色 */
.avatar.assistant {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.bubble-wrap {
  /* 与底部输入框同宽居中后，气泡上限放宽至 88%，长消息视觉上与输入框接近等宽 */
  max-width: 88%;
  display: flex;
  flex-direction: column;
}

.msg-row.user .bubble-wrap {
  align-items: flex-end;
  /* 宽度自适应内容：短问题显示为紧凑气泡，避免拉满成整条“横幅” */
  width: fit-content;
  max-width: 88%;
}

.bubble {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.7;
  font-size: 14px;
  word-break: break-word;
}

.bubble.user {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 4px;
}

.bubble.assistant {
  background: #fff;
  border: 1px solid var(--el-border-color-lighter);
  border-top-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 结构化富文本（一、二、三 → 有序/无序列表、段落） */
.rich {
  white-space: normal;
}
.rich p {
  margin: 0 0 10px;
}
.rich p:last-child {
  margin-bottom: 0;
}
.rich-list {
  margin: 0 0 10px;
  padding-left: 22px;
}
.rich-list:last-child {
  margin-bottom: 0;
}
.rich ol.rich-list {
  list-style: decimal;
}
.rich ul.rich-list {
  list-style: disc;
}
.rich-list li {
  margin: 4px 0;
  line-height: 1.7;
}
/* 中文序号项：标题 + 正文两段式层级 */
.rich-list li .li-title {
  font-weight: 600;
  color: #303133;
}
.rich-list li .li-body {
  margin-top: 2px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}

.err-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #f56c6c;
}

/* 打字动画 */
.typing {
  display: inline-flex;
  gap: 5px;
  padding: 4px 0;
}

.typing .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #a0cfff;
  animation: typing-bounce 1.2s infinite ease-in-out;
}

.typing .dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing .dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

/* 引用 */
.citations {
  margin-top: 8px;
  width: 100%;
}

/* 正文中 [n] 脚注高亮 */
.cite-ref {
  display: inline-block;
  font-size: 11px;
  line-height: 1;
  font-weight: 600;
  color: #fff;
  background: #409eff;
  border-radius: 8px;
  padding: 1px 5px;
  margin: 0 1px;
  cursor: pointer;
  vertical-align: super;
  transition: transform 0.15s, box-shadow 0.15s;
  user-select: none;
}

.cite-ref:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(64, 158, 255, 0.5);
}

/* 被定位引用时的闪烁高亮 */
.cite-flash {
  animation: cite-flash 1.3s ease-out;
}

@keyframes cite-flash {
  0% {
    box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.55);
    background: #eaf3ff;
  }
  100% {
    box-shadow: 0 0 0 0 rgba(64, 158, 255, 0);
    background: #f7f9fc;
  }
}

.cite-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #409eff;
  cursor: pointer;
  user-select: none;
  padding: 4px 8px;
  border-radius: 6px;
  background: #ecf5ff;
}

.cite-toggle:hover {
  background: #d9ecff;
}

.cite-arrow {
  transition: transform 0.2s;
}

.cite-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cite-item {
  background: #f7f9fc;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 10px 12px;
}

.cite-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.cite-idx {
  font-weight: 600;
  color: #409eff;
}

.cite-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.cite-text {
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
  max-height: 72px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
</style>
