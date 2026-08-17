import { useEffect, useState } from 'react'
import { Button, Card, Space, Spin, Tag, Typography, App } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import ChatMessage from '../components/ChatMessage'
import { chatApi } from '../api/endpoints'
import type { Message } from '../types'

export default function ChatTranscriptPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)
  const { message: toast } = App.useApp()

  useEffect(() => {
    if (!id) return
    chatApi
      .detail(id)
      .then((detail) => setMessages(detail.messages))
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }, [id, toast])

  return (
    <Card
      title="咨询记录（只读）"
      extra={
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
      }
    >
      {loading ? (
        <Spin style={{ display: 'block', margin: '60px auto' }} />
      ) : (
        <div>
          <Space style={{ marginBottom: 12 }}>
            <Tag color="blue">{messages.length} 条消息</Tag>
            <Typography.Text type="secondary">注：回答基于知识库检索生成，仅作健康信息参考。</Typography.Text>
          </Space>
          {messages.map((m) => (
            <ChatMessage key={m.id} role={m.role} content={m.content} citations={m.citations ?? []} />
          ))}
        </div>
      )}
    </Card>
  )
}
