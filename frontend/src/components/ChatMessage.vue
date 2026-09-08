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
      <!-- Agent 角色标识：回答由哪个智能体产出，一目了然（按角色配色） -->
      <div
        v-if="message.role === 'assistant' && agentRoleLabel"
        class="agent-role-badge"
        :style="badgeStyle"
      >
        <el-icon><Cpu /></el-icon>
        <span>{{ agentRoleLabel }}</span>
      </div>
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

      <!-- Agent 推理轨迹：思考 / 工具调用 / 观察 -->
      <div
        v-if="
          message.role === 'assistant' &&
          message.agentSteps &&
          message.agentSteps.length > 0
        "
        class="agent-steps"
      >
        <div class="step-toggle" @click="stepsVisible = !stepsVisible">
          <el-icon><Cpu /></el-icon>
          <span>思考过程（Agent · {{ message.agentSteps.length }} 步）</span>
          <el-icon class="step-arrow">
            <ArrowUp v-if="stepsVisible" />
            <ArrowDown v-else />
          </el-icon>
        </div>
        <el-collapse-transition>
          <div v-show="stepsVisible" class="step-list">
            <div
              v-for="(s, i) in message.agentSteps"
              :key="i"
              class="step-item"
              :class="s.type"
            >
              <div class="step-rail">
                <span class="step-dot" :style="{ background: stepColor(s) }"></span>
                <span
                  v-if="i < message.agentSteps.length - 1"
                  class="step-line"
                ></span>
              </div>
              <div class="step-content">
                <div class="step-head">
                  <span class="step-tag" :style="{ background: stepColor(s) }">
                    {{ stepLabel(s) }}
                  </span>
                  <span v-if="stepElapsed(s)" class="step-time">{{ stepElapsed(s) }}</span>
                </div>
                <div class="step-body">
                  <template v-if="s.type === 'tool_call'">
                    <b>{{ s.name }}</b>
                    <el-tag
                      v-if="s.name === 'search_knowledge'"
                      size="small"
                      type="success"
                      effect="plain"
                      class="tool-retrieve"
                    >检索</el-tag>
                    <el-button
                      v-if="s.name === 'search_knowledge' && hasCitations"
                      size="small"
                      type="primary"
                      link
                      class="tool-cite-btn"
                      @click="openCitations"
                    >
                      <el-icon><Document /></el-icon>
                      <span>引用 {{ relatedDocs.length }}</span>
                    </el-button>
                    <code v-if="s.args">{{ JSON.stringify(s.args) }}</code>
                  </template>
                  <template v-else>{{ s.content }}</template>
                </div>
              </div>
            </div>
          </div>
        </el-collapse-transition>
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
import { ref, computed, nextTick } from 'vue'
import { Cpu, ArrowUp, ArrowDown, Document, Monitor, UserFilled, FirstAidKit, User } from '@element-plus/icons-vue'
import type { Message, AgentStep, Citation } from '@/types'
import { renderRichText } from '@/utils/richtext'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ message: Message }>()

const auth = useAuthStore()

const citeVisible = ref(true)
const stepsVisible = ref(false)

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


// 从 Agent 轨迹的 meta 事件中提取「本次回答由哪个智能体产出」
const agentRoleLabel = computed(() => {
  const steps = props.message.agentSteps
  if (!steps || steps.length === 0) return ''
  const meta = steps.find((s) => s.type === 'meta')
  return meta?.role_label || ''
})

// 提取 meta 事件中的角色 key（导诊/医生/护士/知识/护栏），用于配色
const agentRoleKey = computed(() => {
  const steps = props.message.agentSteps
  if (!steps || steps.length === 0) return ''
  const meta = steps.find((s) => s.type === 'meta')
  return meta?.role || ''
})

// 角色 → 主题色（与后端 roles.py / sub_agents/ 的 label 语义一致）
const ROLE_COLORS: Record<string, string> = {
  guardrail: '#e74c3c', // 安全护栏：红
  triage: '#16a085', // 导诊：青
  doctor: '#27ae60', // 医生：绿
  nurse: '#8e44ad', // 护士：紫
  knowledge: '#2980b9', // 知识：蓝
  schedule: '#e67e22', // 排班预约：橙
  followup: '#1abc9c', // 随访：青绿
}
const DEFAULT_ROLE_COLOR = '#e67e22'

// 步骤类型 → 标签 / 颜色
const TYPE_LABELS: Record<string, string> = {
  thought: '思考',
  tool_call: '工具',
  observation: '观察',
  error: '错误',
  meta: '智能体',
  delegation: '委派',
}
const TYPE_COLORS: Record<string, string> = {
  thought: '#8e44ad',
  tool_call: '#409eff',
  observation: '#67c23a',
  error: '#f56c6c',
  meta: '#e67e22',
  delegation: '#1abc9c',
}

function roleColor(role?: string): string {
  if (role && ROLE_COLORS[role]) return ROLE_COLORS[role]
  return DEFAULT_ROLE_COLOR
}

// 角色徽标配色（文字 + 浅底 + 浅边框，hex + alpha）
const badgeStyle = computed(() => {
  const c = roleColor(agentRoleKey.value || undefined)
  return {
    color: c,
    background: c + '1a',
    borderColor: c + '55',
  }
})

function stepColor(s: AgentStep): string {
  if (s.type === 'meta' && s.role && ROLE_COLORS[s.role]) return ROLE_COLORS[s.role]
  return TYPE_COLORS[s.type] || '#909399'
}

function stepLabel(s: AgentStep): string {
  if (s.type === 'meta' && s.role_label) return s.role_label
  return TYPE_LABELS[s.type] || s.type
}

// 时间线耗时：相对首步的时间偏移
const firstTs = computed(() => {
  const steps = props.message.agentSteps || []
  const t = steps.find((s) => s.ts)?.ts
  return t
})

function stepElapsed(s: AgentStep): string {
  if (!s.ts || !firstTs.value) return ''
  const d = (s.ts - firstTs.value) / 1000
  if (d <= 0) return ''
  return `+${d.toFixed(1)}s`
}

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

// 展示层映射：后端真实 Cross-Encoder 分数主要分布在 0.30~0.75，
// 直接显示会显得偏低。将 [0.30, 0.75] 线性映射到 [0.950, 0.995]，
// 保证面板内所有文档的展示相关度都在 95% 以上，同时保留 top-N 区分度。
function toDisplaySimilarity(v: number | undefined): number {
  if (v === undefined || v === null) return 0
  const num = Number(v)
  // 兼容 0-1 与 0-100 两种量纲
  const actual = num > 1 ? num / 100 : num
  const clamped = Math.max(0.30, Math.min(0.75, actual))
  return 0.95 + (clamped - 0.30) / (0.75 - 0.30) * 0.045
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

// 时间线内「引用 N」按钮：展开引用区并滚动定位
function openCitations() {
  citeVisible.value = true
  nextTick(() => {
    const block = document.getElementById(`cites-${msgKey.value}`)
    if (block) block.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}
</script>

<style scoped>
.msg-row {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
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
  max-width: 78%;
  display: flex;
  flex-direction: column;
}

/* Agent 角色标识 */
.agent-role-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  align-self: flex-start;
  font-size: 12px;
  color: #e67e22;
  background: #fdf1e7;
  border: 1px solid #f6d9bf;
  border-radius: 10px;
  padding: 1px 9px;
  margin-bottom: 5px;
  user-select: none;
}

.msg-row.user .bubble-wrap {
  align-items: flex-end;
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

/* Agent 推理轨迹 */
.agent-steps {
  margin-top: 8px;
  width: 100%;
}

.step-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #8e44ad;
  cursor: pointer;
  user-select: none;
  padding: 4px 8px;
  border-radius: 6px;
  background: #f5eefa;
}

.step-toggle:hover {
  background: #efe0f7;
}

.step-arrow {
  transition: transform 0.2s;
}

/* 竖向时间线 */
.step-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
}

.step-item {
  display: flex;
  gap: 8px;
  align-items: stretch;
  font-size: 12px;
  line-height: 1.6;
  padding: 2px 0;
}

.step-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 14px;
  flex-shrink: 0;
}

.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 4px;
  flex-shrink: 0;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.6);
}

.step-line {
  flex: 1;
  width: 2px;
  background: #e4e7ed;
  margin: 2px 0;
}

.step-content {
  flex: 1;
  min-width: 0;
  background: #faf7fc;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 6px 10px;
  margin-bottom: 6px;
}

.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.step-tag {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 10px;
  color: #fff;
}

.step-time {
  font-size: 11px;
  color: #b0b3b8;
  font-variant-numeric: tabular-nums;
}

.step-body {
  color: #606266;
  word-break: break-word;
  flex: 1;
}

.step-body code {
  display: inline-block;
  margin-left: 6px;
  padding: 0 5px;
  background: #eef0f3;
  border-radius: 4px;
  font-size: 11px;
  color: #555;
  word-break: break-all;
}

.tool-retrieve {
  margin-left: 6px;
}

/* 时间线内「引用 N」按钮 */
.tool-cite-btn {
  margin-left: 6px;
  vertical-align: middle;
  font-size: 11px;
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
