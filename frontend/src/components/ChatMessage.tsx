import { Space, Typography } from 'antd'
import MarkdownView from './MarkdownView'
import CitationCard from './CitationCard'
import type { Citation } from '../types'

interface Props {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  streaming?: boolean
}

export default function ChatMessage({ role, content, citations, streaming }: Props) {
  if (role === 'user') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <div
          style={{
            background: '#1677ff',
            color: '#fff',
            padding: '10px 14px',
            borderRadius: 12,
            maxWidth: '70%',
            whiteSpace: 'pre-wrap',
          }}
        >
          {content}
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', marginBottom: 16 }}>
      <div
        style={{
          background: '#fff',
          border: '1px solid #f0f0f0',
          borderRadius: 12,
          padding: '10px 14px',
          maxWidth: '85%',
        }}
      >
        {content ? (
          <MarkdownView content={content} />
        ) : (
          <Typography.Text type="secondary">思考中{streaming ? '…' : ''}</Typography.Text>
        )}
        {!!citations?.length && (
          <Space size={[8, 8]} wrap style={{ marginTop: 10 }}>
            {citations.map((c, i) => (
              <CitationCard key={i} index={i} citation={c} />
            ))}
          </Space>
        )}
      </div>
    </div>
  )
}
