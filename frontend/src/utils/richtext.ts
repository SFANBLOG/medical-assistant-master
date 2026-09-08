/**
 * 富文本渲染工具：把后端返回的医疗回答文本转换为结构化的安全 HTML。
 *
 * 背景：后端 llm.py 会统一清洗掉 ** 加粗、# 标题、英文 -/* 列表等 Markdown 符号，
 * 并要求大模型用「一、二、三」或「第一、第二」等中文序号分点。因此前端拿到的是
 * 纯文本 + 中文序号，直接 white-space: pre-wrap 会丢失层级。
 *
 * 本工具把这类文本还原为有序列表 / 无序列表 / 段落，提升可读性。
 * 规则：
 *  - 以「一、/（一）/ 第一、/ 1.」等开头的行 → 有序列表项，其后续紧跟的非列表行
 *    作为该项的正文（同一 <li> 内，标题 + 正文两段式）；
 *  - 以「- / * / •」等开头的行 → 无序列表项；
 *  - 其余行 → 段落；空行会结束当前列表，后续文字另起段落。
 *
 * 安全说明（重要）：所有文本先经过 HTML 转义，只有在本工具判定为「结构标记」时
 * 才输出 <ol>/<ul>/<li>/<p> 等固定标签，绝不把原文中的任意标签写入 HTML，避免 XSS。
 */

// 中文序号前缀：一、 (一)、 一. 一，（括号与顿号/句号/逗号均可）
const RE_CN_ORDINAL = /^[（(]?[零一二三四五六七八九十百]+[)）]?\s*[、.．，]/
// 括号中文序号： （一） (一)
const RE_CN_PAREN = /^[（(][零一二三四五六七八九十百]+[)）]\s*/
// 第一、 第二、 第一，
const RE_CN_FIRST = /^第[零一二三四五六七八九十百]+[、.．，]/
// 阿拉伯数字序号：1. 1、 1．
const RE_NUM = /^\d{1,3}[、.．]/
// 无序列表符号：- * • · 等
const RE_BULLET = /^[-\*•·‣◦]/
// 残留 Markdown 标题（虽然后端已清洗，这里再防御一次；兼容无空格 ##标题 与 中间断开的 # #标题）
const RE_MD_HEADING = /^(?:#{1,6}\s*|#\s+#\s*)/

/** HTML 转义，防止 XSS。 */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

interface ListItem {
  title: string
  body: string[]
}

type Block =
  | { type: 'ol' | 'ul'; items: ListItem[] }
  | { type: 'p'; html: string }

interface DetectResult {
  kind: 'ol' | 'ul' | 'p'
  content: string
}

/** 判定一行文本是哪种结构，并返回去掉前缀后的内容。 */
function detect(line: string): DetectResult {
  const t = line.trim()
  if (
    RE_CN_ORDINAL.test(t) ||
    RE_CN_PAREN.test(t) ||
    RE_CN_FIRST.test(t) ||
    RE_NUM.test(t)
  ) {
    const content = t
      .replace(RE_CN_ORDINAL, '')
      .replace(RE_CN_PAREN, '')
      .replace(RE_CN_FIRST, '')
      .replace(RE_NUM, '')
      .trim()
    return { kind: 'ol', content }
  }
  if (RE_BULLET.test(t)) {
    return { kind: 'ul', content: t.replace(RE_BULLET, '').trim() }
  }
  return { kind: 'p', content: t }
}

/**
 * 将回答文本渲染为结构化 HTML 字符串。
 * 调用方应通过 v-html 注入，且仅在本组件内使用，内容已转义。
 */
export function renderRichText(raw: string): string {
  if (!raw) return ''

  // 1) 先去除可能残留的 Markdown 行内/块级符号（保留中文序号与列表符号，由后续解析处理）
  let text = raw
  text = text.replace(/```[\s\S]*?```/g, '') // 围栏代码块
  text = text.replace(/`([^`]+)`/g, '$1') // 行内代码
  text = text.replace(/\*\*([^*]+)\*\*/g, '$1') // 加粗 **
  text = text.replace(/__([^_]+)__/g, '$1') // 加粗 __
  text = text.replace(/(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)/g, '$1') // 斜体 *
  text = text.replace(RE_MD_HEADING, '') // 行首 # 标题（含无空格/断裂情况）
  // 防御 chunk 边界断裂产生的中间 # 团，如 "##肝硬化"、"# #肝硬化"、"病因##" 等
  text = text.replace(/(?:#{1,6}\s*)+/g, '')
  text = text.replace(/\n{3,}/g, '\n\n')

  const lines = text.split('\n')
  const blocks: Block[] = []
  let paraBuf: string[] = []

  const flushPara = () => {
    if (paraBuf.length) {
      blocks.push({ type: 'p', html: paraBuf.map(escapeHtml).join('<br>') })
      paraBuf = []
    }
  }

  for (const line of lines) {
    if (line.trim() === '') {
      // 空行：刷出段落；若当前处于列表中，插入一个空占位块（不渲染），
      // 用于区分「列表项之间的空行（序号连续）」与「列表后另起段落（列表结束）」
      flushPara()
      const last = blocks[blocks.length - 1]
      if (last && (last.type === 'ol' || last.type === 'ul')) {
        blocks.push({ type: 'p', html: '' })
      }
      continue
    }
    const { kind, content } = detect(line)
    if (kind === 'p') {
      // 段落：若当前正处于列表中，则作为该列表最后一项的正文；否则累积为段落
      const last = blocks[blocks.length - 1]
      if (last && (last.type === 'ol' || last.type === 'ul') && last.items.length) {
        last.items[last.items.length - 1].body.push(escapeHtml(content))
      } else {
        paraBuf.push(content)
      }
      continue
    }
    // 列表项：先刷出前面的段落
    flushPara()
    const last = blocks[blocks.length - 1]
    const prev = blocks[blocks.length - 2]
    // 若列表项被空行隔断（前一个是空占位块、再前一个是同类型列表），
    // 则移除占位块并合并回原列表，保证序号连续（否则会拆成多个 <ol>，
    // 浏览器编号会重置为 1. 1. 1.…）
    if (
      prev &&
      (prev.type === kind) &&
      (kind === 'ol' || kind === 'ul') &&
      last &&
      last.type === 'p' &&
      last.html === ''
    ) {
      blocks.pop()
      prev.items.push({ title: escapeHtml(content), body: [] })
      continue
    }
    if (last && (last.type === kind) && (kind === 'ol' || kind === 'ul')) {
      last.items.push({ title: escapeHtml(content), body: [] })
    } else {
      blocks.push({ type: kind, items: [{ title: escapeHtml(content), body: [] }] })
    }
  }
  flushPara()

  return blocks
    .map((b) => {
      if (b.type === 'p') {
        // 列表断开用的占位空段落不渲染
        return b.html.trim() === '' || b.html === ' ' ? '' : `<p>${b.html}</p>`
      }
      const tag = b.type
      const lis = b.items
        .map((it) => {
          const bodyHtml = it.body.length
            ? `<div class="li-body">${it.body.join('<br>')}</div>`
            : ''
          return `<li><div class="li-title">${it.title}</div>${bodyHtml}</li>`
        })
        .join('')
      return `<${tag} class="rich-list">${lis}</${tag}>`
    })
    .join('')
}

export default renderRichText
