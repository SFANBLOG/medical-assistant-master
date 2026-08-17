import { useEffect, useState } from 'react'
import { Card, Collapse, Empty, Spin, Tag, Typography, App } from 'antd'
import { FileTextOutlined, ReadOutlined } from '@ant-design/icons'
import { kbApi } from '../api/endpoints'
import type { DocumentItem, KnowledgeBase } from '../types'

export default function HealthInfoPage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [docsMap, setDocsMap] = useState<Record<number, DocumentItem[]>>({})
  const [loading, setLoading] = useState(true)
  const { message: toast } = App.useApp()

  useEffect(() => {
    kbApi
      .list()
      .then(async (kbs) => {
        setKbs(kbs)
        const entries = await Promise.all(
          kbs.map(async (kb) => {
            try {
              return [kb.id, await kbApi.documents(kb.id)] as const
            } catch {
              return [kb.id, [] as DocumentItem[]] as const
            }
          }),
        )
        setDocsMap(Object.fromEntries(entries))
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }, [toast])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  return (
    <Card title="健康资讯">
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        平台共建的疾病科普知识库，供群众了解常见疾病的病因、症状与处理建议。
      </Typography.Paragraph>
      {!kbs.length && <Empty description="暂无公开知识库" />}
      <Collapse
        items={kbs.map((kb) => ({
          key: String(kb.id),
          label: (
            <span>
              <ReadOutlined style={{ marginRight: 8 }} />
              {kb.name}
              <Tag style={{ marginLeft: 8 }}>{kb.doc_count ?? 0} 篇文档</Tag>
            </span>
          ),
          children: (
            <div>
              <Typography.Paragraph type="secondary">{kb.description}</Typography.Paragraph>
              {(docsMap[kb.id] ?? []).length ? (
                <ul style={{ paddingLeft: 20 }}>
                  {(docsMap[kb.id] ?? []).map((doc) => (
                    <li key={doc.id} style={{ marginBottom: 6 }}>
                      <FileTextOutlined style={{ marginRight: 8 }} />
                      {doc.filename.replace(/^seed_[a-f0-9]{8}_/, '')}
                      <Tag style={{ marginLeft: 8 }} color="blue">
                        {doc.file_type}
                      </Tag>
                      <Tag>{doc.chunk_count} 个知识切片</Tag>
                    </li>
                  ))}
                </ul>
              ) : (
                <Typography.Text type="secondary">该知识库暂无文档</Typography.Text>
              )}
            </div>
          ),
        }))}
      />
    </Card>
  )
}
