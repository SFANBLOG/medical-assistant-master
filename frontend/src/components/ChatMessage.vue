<template>
  <div class="msg-row" :class="message.role">
    <div class="avatar" :class="message.role">
      <el-icon v-if="message.role === 'user'" :size="18"><UserFilled /></el-icon>
      <el-icon v-else :size="18"><FirstAidKit /></el-icon>
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
        <div v-else class="content rich" v-html="renderedHtml"></div>
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
          message.citations &&
          message.citations.length > 0
        "
        class="citations"
      >
        <div class="cite-toggle" @click="citeVisible = !citeVisible">
          <el-icon><Document /></el-icon>
          <span>相关文档（与您问题最相关 · {{ message.citations.length }}）</span>
          <el-icon class="cite-arrow">
            <ArrowUp v-if="citeVisible" />
            <ArrowDown v-else />
          </el-icon>
        </div>
        <el-collapse-transition>
          <div v-show="citeVisible" class="cite-list">
            <div
              v-for="(c, i) in message.citations"
              :key="i"
              class="cite-item"
            >
              <div class="cite-head">
                <span class="cite-idx">[{{ i + 1 }}]</span>
                <span class="cite-title">{{ c.title || `文档 ${c.doc_id}` }}</span>
                <el-tag size="small" type="info" effect="plain">
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
import { ref, computed } from 'vue'
import { Cpu, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import type { Message, AgentStep } from '@/types'
import { renderRichText } from '@/utils/richtext'

const props = defineProps<{ message: Message }>()

const citeVisible = ref(true)
const stepsVisible = ref(false)

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

// 角色 → 主题色（与后端 roles.py 的 label 语义一致）
const ROLE_COLORS: Record<string, string> = {
  guardrail: '#e74c3c', // 安全护栏：红
  triage: '#16a085', // 导诊：青
  doctor: '#27ae60', // 医生：绿
  nurse: '#8e44ad', // 护士：紫
  knowledge: '#2980b9', // 知识：蓝
}
const DEFAULT_ROLE_COLOR = '#e67e22'

// 步骤类型 → 标签 / 颜色
const TYPE_LABELS: Record<string, string> = {
  thought: '思考',
  tool_call: '工具',
  observation: '观察',
  error: '错误',
  meta: '智能体',
}
const TYPE_COLORS: Record<string, string> = {
  thought: '#8e44ad',
  tool_call: '#409eff',
  observation: '#67c23a',
  error: '#f56c6c',
  meta: '#e67e22',
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
const renderedHtml = computed(() =>
  props.message.streaming ? '' : renderRichText(props.message.content),
)

function formatSimilarity(v: number | undefined): string {
  if (v === undefined || v === null) return '-'
  const num = Number(v)
  // 兼容 0-1 与 0-100 两种量纲
  const pct = num > 1 ? num : num * 100
  return `${pct.toFixed(1)}%`
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

.avatar.user {
  background: #409eff;
}

.avatar.assistant {
  background: linear-gradient(135deg, #409eff, #79bbff);
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
