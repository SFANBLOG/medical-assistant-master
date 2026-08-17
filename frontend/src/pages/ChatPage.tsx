import { useEffect, useRef, useState } from 'react'
import {
  Button,
  Card,
  Input,
  Select,
  Space,
  Tag,
  Typography,
  App,
  Empty,
} from 'antd'
import { PlusOutlined, SendOutlined, RobotOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import ChatMessage from '../components/ChatMessage'
import { chatApi, kbApi } from '../api/endpoints'
import type { Citation, KnowledgeBase, Message } from '../types'

interface DisplayMessage {
  id: number | string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
}

export default function ChatPage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [kbId, setKbId] = useState<number | null>(null)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [streaming, setStreaming] = useState<DisplayMessage | null>(null)
  const [input, setInput] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [offline, setOffline] = useState(false)
  const [loading, setLoading] = useState(true)
  const [searchParams] = useSearchParams()
  const { message: toast } = App.useApp()
  const scrollRef = useRef<HTMLDivElement>(null)

  // 加载可见知识库
  useEffect(() => {
    kbApi
      .list()
      .then((items) => {
        setKbs(items)
        if (items.length) setKbId((prev) => prev ?? items[0].id)
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }, [toast])

  // 从历史记录带会话参数进入时加载会话
  const convFromUrl = searchParams.get('conversation')
  useEffect(() => {
    if (!convFromUrl) return
    chatApi
      .detail(convFromUrl)
      .then((detail) => {
        setConversationId(detail.conversation.id)
        setKbId(detail.conversation.kb_id)
        setMessages(
          detail.messages.map((m: Message) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            citations: m.citations ?? [],
          })),
        )
      })
      .catch((e) => toast.error((e as Error).message))
  }, [convFromUrl, toast])

  // 自动滚动到底部
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, streaming?.content])

  const send = async () => {
    const question = input.trim()
    if (!question || streaming) return
    if (!kbId) {
      toast.warning('请先选择知识库')
      return
    }
    setInput('')
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: 'user', content: question, citations: [] }])
    const placeholder: DisplayMessage = { id: 'streaming', role: 'assistant', content: '', citations: [] }
    setStreaming(placeholder)
    setOffline(false)

    const token = localStorage.getItem('mia_token')
    try {
      const resp = await fetch('/api/chat/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ conversation_id: conversationId, kb_id: kbId, question }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(body.error || `请求失败 (${resp.status})`)
      }
      if (!resp.body) throw new Error('响应不支持流式读取')

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let full = ''
      let doneCitations: Citation[] = []
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const frames = buf.split('\n\n')
        buf = frames.pop() ?? ''
        for (const frame of frames) {
          for (const line of frame.split('\n')) {
            if (!line.startsWith('data:')) continue
            const evt = JSON.parse(line.slice(5).trim())
            if (evt.type === 'meta') setOffline(evt.mode === 'offline')
            else if (evt.type === 'delta') {
              full += evt.content
              setStreaming({ ...placeholder, content: full })
            } else if (evt.type === 'done') {
              doneCitations = evt.citations ?? []
              setConversationId(evt.conversation_id)
            }
          }
        }
      }
      setMessages((prev) => [
        ...prev,
        { id: `d-${Date.now()}`, role: 'assistant', content: full, citations: doneCitations },
      ])
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setStreaming(null)
    }
  }

  const newChat = () => {
    setConversationId(null)
    setMessages([])
    setOffline(false)
  }

  return (
    <Card
      title={
        <Space>
          <RobotOutlined />
          <span>智能医疗咨询</span>
          {offline && <Tag color="orange">离线兜底模式</Tag>}
          {!offline && streaming && <Tag color="green">生成中</Tag>}
        </Space>
      }
      extra={
        <Space>
          <Select
            placeholder="选择知识库"
            style={{ width: 240 }}
            value={kbId}
            onChange={setKbId}
            options={kbs.map((k) => ({
              value: k.id,
              label: `${k.name}${k.visibility === 'public' ? '（公开）' : '（私有）'}`,
            }))}
            loading={loading}
          />
          <Button icon={<PlusOutlined />} onClick={newChat}>
            新建会话
          </Button>
        </Space>
      }
      styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}
    >
      <div
        ref={scrollRef}
        style={{ height: 'calc(100vh - 260px)', overflowY: 'auto', padding: 16, minHeight: 320 }}
      >
        {!messages.length && !streaming && (
          <Empty
            style={{ marginTop: 80 }}
            description="输入你的医疗问题，例如：高血压患者饮食需要注意什么？"
          />
        )}
        {messages.map((m) => (
          <ChatMessage key={m.id} role={m.role} content={m.content} citations={m.citations} />
        ))}
        {streaming && (
          <ChatMessage role="assistant" content={streaming.content} citations={streaming.citations} streaming />
        )}
      </div>
      <div style={{ padding: 12, borderTop: '1px solid #f0f0f0' }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            autoSize={{ minRows: 2, maxRows: 5 }}
            disabled={!!streaming}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={send}
            loading={!!streaming}
            style={{ height: 'auto' }}
          >
            发送
          </Button>
        </Space.Compact>
        {conversationId && (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            当前会话 ID：{conversationId.slice(0, 8)}…
          </Typography.Text>
        )}
      </div>
    </Card>
  )
}
