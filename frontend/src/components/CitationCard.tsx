import { Tooltip, Tag } from 'antd'
import type { Citation } from '../types'

const TAG_COLORS = ['blue', 'cyan', 'geekblue', 'purple', 'magenta', 'orange', 'gold']

export default function CitationCard({ index, citation }: { index: number; citation: Citation }) {
  const color = TAG_COLORS[index % TAG_COLORS.length]
  return (
    <Tooltip
      title={
        <div style={{ maxWidth: 320, maxHeight: 240, overflow: 'auto' }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{citation.title}</div>
          <div style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{citation.source_text.slice(0, 400)}</div>
        </div>
      }
    >
      <Tag color={color} style={{ cursor: 'pointer' }}>
        [{index + 1}] {citation.title}
        <span style={{ opacity: 0.7, marginLeft: 6 }}>
          相似度 {citation.similarity.toFixed(2)}
        </span>
      </Tag>
    </Tooltip>
  )
}
