/**
 * 日期时间格式化工具
 * 兼容 ISO 格式（2026-08-26T15:39:45）与 MySQL 默认格式（Wed, 26 Aug 2026 15:39:45 GMT）
 */

function toDate(t?: string | null): Date | null {
  if (!t) return null
  const d = new Date(t)
  return isNaN(d.getTime()) ? null : d
}

const pad = (n: number) => String(n).padStart(2, '0')

/** 完整日期时间：2026-08-26 15:39 */
export function formatDateTime(t?: string | null): string {
  if (!t) return '-'
  const d = toDate(t)
  if (!d) return t
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}

/** 仅日期：2026-08-26 */
export function formatDate(t?: string | null): string {
  if (!t) return '-'
  const d = toDate(t)
  if (!d) return t.slice(0, 10)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
